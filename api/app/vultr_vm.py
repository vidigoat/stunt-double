"""Dedicated Vultr VM isolation: phase 1 of a high-risk rehearsal runs on its own brand-new Vultr Cloud Compute instance,
created through the Vultr API for this one rehearsal and destroyed straight after.

Trust model (unchanged from the container path): the VM is just where the untrusted plan runs. It sends back only the
modified database copy and the plan's recorded intents; the measurement (phase 2) still happens on our server, in a fresh
gVisor container running only our code. So the plan still can't lie about what it did.

On the VM the plan runs as an unprivileged user whose outbound traffic is rejected by the firewall, with an empty
environment and a time cap. The VM fetches its bundle and returns its result over HTTPS with a one-time token.

Spend is capped in code: one rehearsal VM at a time, a daily limit, the smallest plan, a reaper that destroys any
rehearsal VM older than ten minutes, and no new VM once the account's pending charges pass a ceiling.
"""
from __future__ import annotations

import base64
import io
import secrets
import tarfile
import threading
import time
from pathlib import Path
from collections.abc import Callable

import httpx

from . import config

API = "https://api.vultr.com/v2"
TAG = "sd-rehearsal"
PLAN, REGION, OS_ID = config.VM_PLAN, config.VM_REGION, 2284  # Ubuntu 24.04 LTS x64
MAX_RESULT_BYTES = 64 * 1024 * 1024
BOOT_TIMEOUT_S = 300
MAX_AGE_S = 600

_lock = threading.Lock()           # one rehearsal VM at a time
_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}        # token -> {"bundle": bytes | None, "result": bytes | None, "exp": float}
_day: dict[str, int] = {}


def configured() -> bool:
    return bool(config.VULTR_API_KEY and config.PUBLIC_URL)


def _h() -> dict:
    return {"Authorization": f"Bearer {config.VULTR_API_KEY}", "Content-Type": "application/json"}


def _api(method: str, path: str, **kw) -> httpx.Response:
    return httpx.request(method, API + path, headers=_h(), timeout=30, **kw)


def pending_charges() -> float:
    return float(_api("GET", "/account").json()["account"]["pending_charges"])


def reap(max_age_s: int = MAX_AGE_S) -> list[str]:
    """Destroy any rehearsal VM older than max_age_s (a crash or a lost result must never leave one running)."""
    gone = []
    try:
        for inst in _api("GET", f"/instances?tag={TAG}&per_page=100").json().get("instances", []):
            created = time.mktime(time.strptime(inst["date_created"][:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
            if time.time() - created > max_age_s:
                _api("DELETE", f"/instances/{inst['id']}")
                gone.append(inst["id"])
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    return gone


def _user_data(token: str) -> str:
    base = config.PUBLIC_URL.rstrip("/")
    script = f"""#!/bin/bash
# Stunt Double rehearsal VM: run one untrusted plan with no outbound network, send back the outputs, nothing else.
set -u
useradd -M -s /usr/sbin/nologin sdplan 2>/dev/null || true
iptables -A OUTPUT -m owner --uid-owner sdplan -j REJECT
ip6tables -A OUTPUT -m owner --uid-owner sdplan -j REJECT
mkdir -p /work/out && cd /work
curl -fsS --retry 5 --retry-delay 2 {base}/api/vm/{token}/bundle -o /root/b.tgz && tar xzf /root/b.tgz -C /work && rm -f /root/b.tgz
chown -R sdplan /work
timeout 60 runuser -u sdplan -- env -i PATH=/usr/bin:/bin HOME=/tmp SD_PLAN_MEM_MB=160 python3 -I -B /work/runner.py run
echo $? > /root/exit
rm -f /work/runner.py /work/plan.py
tar czf /root/r.tgz -C /work work.db out -C /root exit
curl -fsS --retry 5 --retry-delay 2 -X POST --data-binary @/root/r.tgz {base}/api/vm/{token}/result
"""
    return base64.b64encode(script.encode()).decode()


def take_bundle(token: str) -> bytes | None:
    """One-time download of the plan, the database copy and the harness."""
    with _jobs_lock:
        job = _jobs.get(token)
        if not job or time.time() > job["exp"] or job["bundle"] is None:
            return None
        b, job["bundle"] = job["bundle"], None
        return b


def put_result(token: str, data: bytes) -> bool:
    with _jobs_lock:
        job = _jobs.get(token)
        if not job or time.time() > job["exp"] or job["result"] is not None or len(data) > MAX_RESULT_BYTES:
            return False
        job["result"] = data
        return True


def _bundle(work: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(work / "plan.py", "plan.py")
        t.add(work / "work.db", "work.db")
        t.add(Path(__file__).parent / "harness" / "runner.py", "runner.py")
    return buf.getvalue()


def _unpack(data: bytes, work: Path) -> int:
    """Only regular files with expected names, sizes capped. Returns the plan's exit code (or -1)."""
    allowed = {"work.db": work / "work.db", "out/intents.json": work / "out" / "intents.json", "exit": work / "exit"}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
        for m in t.getmembers():
            name = m.name.lstrip("./")
            if name in allowed and m.isreg() and m.size <= MAX_RESULT_BYTES:
                allowed[name].parent.mkdir(parents=True, exist_ok=True)
                allowed[name].write_bytes(t.extractfile(m).read())
    try:
        return int((work / "exit").read_text().strip())
    except (OSError, ValueError):
        return -1


def run_phase1(rid: str, work: Path, emit: Callable[[str], None] = lambda s: None) -> tuple[int, str, str | None, dict]:
    """Run the plan in `work` on a brand-new Vultr VM. Returns (exit_code, stderr, killed_reason, vm_info)."""
    if not configured():
        raise RuntimeError("Dedicated Vultr VMs are not configured on this server")
    day = time.strftime("%Y-%m-%d")
    if _day.get(day, 0) >= config.VM_DAILY_LIMIT:
        raise RuntimeError("Today's dedicated-VM rehearsals for this public demo are used up")
    if not _lock.acquire(blocking=False):
        raise RuntimeError("Another dedicated-VM rehearsal is running; try again in a minute")
    info: dict = {"kind": "vultr_vm", "plan": PLAN, "region": REGION}
    iid = None
    try:
        reap()
        if pending_charges() > config.VM_SPEND_CEILING_USD:
            raise RuntimeError("Spend ceiling reached: no new rehearsal VMs")
        _day[day] = _day.get(day, 0) + 1
        token = secrets.token_urlsafe(24)
        _jobs[token] = {"bundle": _bundle(work), "result": None, "exp": time.time() + BOOT_TIMEOUT_S + 60}
        t0 = time.time()
        r = _api("POST", "/instances", json={"region": REGION, "plan": PLAN, "os_id": OS_ID, "label": f"stunt-double {rid}",
                                              "hostname": rid, "tags": [TAG], "user_data": _user_data(token),
                                              "backups": "disabled", "enable_ipv6": False, "activation_email": False})
        if r.status_code >= 300:
            raise RuntimeError(f"Vultr refused to create the VM: {r.text[:200]}")
        iid = r.json()["instance"]["id"]
        info.update(instance_id=iid, created_at=time.time())
        emit(f"Created Vultr VM {iid[:8]} ({PLAN}, {REGION}) for this rehearsal only")
        said_boot = False
        while time.time() - t0 < BOOT_TIMEOUT_S:
            job = _jobs[token]
            if job["result"] is not None:
                break
            if job["bundle"] is None and not said_boot:
                emit("The VM booted and fetched the plan; running it with outbound network blocked")
                said_boot = True
            time.sleep(2)
        info["vm_ms"] = int((time.time() - t0) * 1000)
        data = _jobs.pop(token, {}).get("result")
        if data is None:
            return -1, "", f"the rehearsal VM did not report back within {BOOT_TIMEOUT_S}s", info
        return _unpack(data, work), "", None, info
    finally:
        if iid:
            for _ in range(3):
                try:
                    if _api("DELETE", f"/instances/{iid}").status_code < 300:
                        info["destroyed_at"] = time.time()
                        emit(f"Destroyed Vultr VM {iid[:8]}")
                        break
                except httpx.HTTPError:
                    time.sleep(2)
        _lock.release()
