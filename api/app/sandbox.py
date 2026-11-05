"""Host side of the rehearsal: clone -> dispatch into an isolated container -> collect -> destroy."""
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import time
import uuid
from pathlib import Path

from . import config

GUARD_FLAGS = [
    "--network", "none",              # no network at all
    "--read-only",                    # root filesystem is read-only
    "--memory", config.SANDBOX_MEMORY, "--memory-swap", config.SANDBOX_MEMORY,
    "--cpus", "1", "--pids-limit", "64",
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
    "--tmpfs", "/tmp:rw,size=16m",
    "--ulimit", "fsize=67108864",    # no file over 64 MB: a plan can't fill the disk through its workspace
    "--ulimit", "nofile=256:256",
    "--env", "PYTHONDONTWRITEBYTECODE=1",
]


def clone_db(dest: Path) -> None:
    """Consistent online copy of the production database (SQLite backup API)."""
    from . import workspaces
    src = sqlite3.connect(f"file:{workspaces.db_path()}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


def _copy_regular_file(src: Path, dst: Path, max_bytes: int = 512 * 1024 * 1024) -> bool:
    """Copy a file the PLAN controlled. The parent directory is opened without following symlinks and the file is
    opened relative to it, non-blocking: symlinks, FIFOs, devices and symlinked folders are all refused."""
    try:
        dfd = os.open(src.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        st = os.lstat(src.name, dir_fd=dfd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > max_bytes:
            return False
        fd = os.open(src.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
    except OSError:
        return False
    finally:
        os.close(dfd)
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > max_bytes:
            return False
        with open(dst, "wb") as out:
            shutil.copyfileobj(f, out)
    return True


def _browser_flags() -> list[str]:
    """Same guards, sized for a real Chromium: more memory, processes and /tmp; no address-space rlimit (it breaks Chromium)."""
    f = list(GUARD_FLAGS)
    for key, val in (("--memory", config.BROWSER_MEMORY), ("--memory-swap", config.BROWSER_MEMORY), ("--pids-limit", "512"), ("--tmpfs", "/tmp:rw,size=512m")):
        f[f.index(key) + 1] = val
    f[f.index("nofile=256:256")] = "nofile=4096:4096"
    return [*f, "--shm-size", "256m"]


def _docker(name: str, mount: str, mode: str, extra: list[str] | None = None, browser: bool = False) -> tuple[int, str, str | None]:
    cmd = ["docker", "run", "--rm", "--name", name, *(_browser_flags() if browser else GUARD_FLAGS), *(extra or [])]
    if config.SANDBOX_RUNTIME:
        cmd += ["--runtime", config.SANDBOX_RUNTIME]
    cmd += [*mount.split(" "), config.BROWSER_IMAGE if browser else config.SANDBOX_IMAGE, mode]
    timeout = config.BROWSER_TIMEOUT_S if browser else config.SANDBOX_TIMEOUT_S
    mem = config.BROWSER_MEMORY if browser else config.SANDBOX_MEMORY
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env={"PATH": os.environ.get("PATH", "")})
        killed = f"memory cap ({mem}) hit - process killed" if p.returncode == 137 else None
        return p.returncode, p.stderr[-2000:], killed
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        return -1, "", f"time cap ({timeout}s) hit - sandbox killed"


def uses_browser(plan_code: str) -> bool:
    return "ctx.browser" in plan_code or ".browser." in plan_code


def _copy_shots(src: Path, dst: Path) -> int:
    """Screenshots the plan's browser produced: only N.png names, real PNGs, at most 12, each at most 2 MB."""
    if not src.is_dir():
        return 0
    dst.mkdir(exist_ok=True)
    n = 0
    for i in range(1, 13):
        target = dst / f"{i}.png"
        if _copy_regular_file(src / f"{i}.png", target, max_bytes=2 * 1024 * 1024):
            if target.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                target.unlink()
                continue
            os.chmod(target, 0o644)
            n += 1
    return n


def rehearse(plan_code: str) -> dict:
    """Phase 1 runs the plan on a clone; phase 2 (a fresh container, trusted code only) measures what it did."""
    rid = "sd-" + uuid.uuid4().hex[:8]
    root = config.RUNS_DIR / rid
    work, inp, out = root / "work", root / "in", root / "out"
    for d in (work / "out", inp, out):
        d.mkdir(parents=True)
    clone_db(inp / "before.db")
    shutil.copyfile(inp / "before.db", work / "work.db")
    (work / "plan.py").write_text(plan_code)
    for d in (root, work, work / "out", inp, out):
        os.chmod(d, 0o777)
    for f in (work / "work.db", inp / "before.db"):
        os.chmod(f, 0o666)
    host = Path(config.RUNS_DIR_HOST) / rid

    t0 = time.time()
    browser = uses_browser(plan_code)
    code1, err1, killed = _docker(rid, f"-v {host / 'work'}:/work", "run", browser=browser)
    run_ms = int((time.time() - t0) * 1000)
    # Hand phase 1's outputs to phase 2 as plain files (never symlinks), then throw phase 1's directory away.
    have_after = _copy_regular_file(work / "work.db", inp / "after.db")
    if not have_after:
        shutil.copyfile(inp / "before.db", inp / "after.db")
    _copy_regular_file(work / "out" / "intents.json", inp / "intents.json")
    shots = _copy_shots(work / "out" / "shots", out / "shots") if browser else 0
    shutil.rmtree(work, ignore_errors=True)
    for f in inp.iterdir():
        os.chmod(f, 0o644)

    code2, err2, killed2 = _docker(rid + "-m", f"-v {host / 'in'}:/in:ro -v {host / 'out'}:/out", "measure")
    wall_ms = int((time.time() - t0) * 1000)

    cpath = out / "consequences.json"
    if code2 == 0 and cpath.exists():
        consequences = json.loads(cpath.read_text())
    else:
        consequences = {"ok": False, "error": {"message": f"measurement failed: {killed2 or err2[-300:] or code2}"}, "tables": {}, "row_counts": {},
                        "payments": {"count": 0, "total_cents": 0, "samples": []}, "emails": {"count": 0, "samples": []}, "http": {"count": 0, "samples": []},
                        "blocked": [], "guards": {}, "audit": {}}
    if killed and consequences.get("ok"):
        consequences["ok"] = False
    if killed:
        consequences["error"] = {"message": f"{killed}. " + ((consequences.get("error") or {}).get("message") or "")}
    if not have_after:
        consequences["ok"], consequences["error"] = False, {"message": "The plan's database copy was replaced or removed (symlinks and special files are refused)"}
        consequences["tables"], consequences["row_counts"] = {}, {}
    consequences["sandbox"] = {
        "id": rid, "runtime": config.SANDBOX_RUNTIME or "runc", "network": "none", "memory": config.SANDBOX_MEMORY,
        "timeout_s": config.SANDBOX_TIMEOUT_S, "read_only_root": True, "exit_code": code1, "killed": killed,
        "run_ms": run_ms, "wall_ms": wall_ms, "destroyed": True, "measured_separately": True,
        **({"profile": "browser", "memory": config.BROWSER_MEMORY, "timeout_s": config.BROWSER_TIMEOUT_S, "screenshots": shots} if browser else {}),
    }
    # The clones are destroyed; only the measured outputs are kept for the approval and the audit trail.
    for f in ("before.db", "after.db"):
        (inp / f).unlink(missing_ok=True)
    return {"id": rid, "consequences": consequences, "effects_path": str(out / "effects.json")}


def build_image() -> None:
    root = Path(__file__).resolve().parents[2]
    subprocess.run(["docker", "build", "-t", config.SANDBOX_IMAGE, "-f", str(root / "sandbox" / "Dockerfile"), str(root)], check=True)


def cleanup_orphans(keep: set[str] | None = None, max_age_s: int = 24 * 3600) -> dict:
    """On startup: kill sandbox containers left by a crash, delete stale run folders (keep those still awaiting approval)."""
    names = subprocess.run(["docker", "ps", "-aq", "--filter", "name=^sd-"], capture_output=True, text=True).stdout.split()
    if names:
        subprocess.run(["docker", "rm", "-f", *names], capture_output=True)
    removed = 0
    now = time.time()
    for d in config.RUNS_DIR.glob("sd-*"):
        if keep and d.name in keep:
            continue
        if now - d.stat().st_mtime > max_age_s:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return {"containers": len(names), "folders": removed}


def cleanup(run_id: str) -> None:
    shutil.rmtree(config.RUNS_DIR / run_id, ignore_errors=True)
