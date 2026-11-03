"""Host side of the rehearsal: clone -> dispatch into an isolated container -> collect -> destroy."""
import json
import os
import shutil
import sqlite3
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
    "--env", "PYTHONDONTWRITEBYTECODE=1",
]


def clone_db(dest: Path) -> None:
    """Consistent online copy of the production database (SQLite backup API)."""
    src = sqlite3.connect(f"file:{config.PROD_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


def rehearse(plan_code: str) -> dict:
    """Run plan_code on a throwaway copy of the business. Returns consequences + where effects live."""
    rid = "sd-" + uuid.uuid4().hex[:8]
    work = config.RUNS_DIR / rid
    (work / "out").mkdir(parents=True)
    clone_db(work / "business.db")
    (work / "plan.py").write_text(plan_code)
    os.chmod(work, 0o777)
    os.chmod(work / "out", 0o777)
    os.chmod(work / "business.db", 0o666)

    host_work = Path(config.RUNS_DIR_HOST) / rid
    cmd = ["docker", "run", "--rm", "--name", rid, *GUARD_FLAGS]
    if config.SANDBOX_RUNTIME:
        cmd += ["--runtime", config.SANDBOX_RUNTIME]
    cmd += ["-v", f"{host_work}:/work", config.SANDBOX_IMAGE]

    t0 = time.time()
    killed_reason = None
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=config.SANDBOX_TIMEOUT_S, env={"PATH": os.environ.get("PATH", "")})
        exit_code = proc.returncode
        stderr = proc.stderr[-2000:]
        if exit_code == 137:
            killed_reason = f"memory cap ({config.SANDBOX_MEMORY}) hit - process killed"
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", rid], capture_output=True)
        exit_code, stderr = -1, ""
        killed_reason = f"time cap ({config.SANDBOX_TIMEOUT_S}s) hit - sandbox killed"
    wall_ms = int((time.time() - t0) * 1000)

    cpath = work / "out" / "consequences.json"
    if cpath.exists():
        consequences = json.loads(cpath.read_text())
    else:
        consequences = {"ok": False, "error": {"message": killed_reason or f"sandbox exited {exit_code}", "traceback": stderr},
                        "tables": {}, "row_counts": {}, "payments": {"count": 0, "total_cents": 0, "samples": []},
                        "emails": {"count": 0, "samples": []}, "blocked": [], "guards": {}}
    consequences["sandbox"] = {
        "id": rid, "runtime": config.SANDBOX_RUNTIME or "runc", "network": "none", "memory": config.SANDBOX_MEMORY,
        "timeout_s": config.SANDBOX_TIMEOUT_S, "read_only_root": True, "exit_code": exit_code,
        "killed": killed_reason, "wall_ms": wall_ms, "destroyed": True,
    }
    # Keep only the outputs; the cloned database is destroyed with the sandbox.
    (work / "business.db").unlink(missing_ok=True)
    return {"id": rid, "consequences": consequences, "effects_path": str(work / "out" / "effects.json")}


def build_image() -> None:
    root = Path(__file__).resolve().parents[2]
    subprocess.run(["docker", "build", "-t", config.SANDBOX_IMAGE, "-f", str(root / "sandbox" / "Dockerfile"), str(root)], check=True)


def cleanup(run_id: str) -> None:
    shutil.rmtree(config.RUNS_DIR / run_id, ignore_errors=True)
