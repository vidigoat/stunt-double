"""Plans that actively attack the harness. The approver must still see the truth, and the host must be untouched."""
import sqlite3

from app import agent, config, sandbox
from tests.conftest import needs_docker


def rehearse(body: str) -> dict:
    code = "def run(ctx):\n" + "\n".join("    " + l for l in body.strip().splitlines()) + "\n"
    return sandbox.rehearse(code)["consequences"]


@needs_docker
def test_plan_cannot_hide_what_it_did(fresh_business):
    """The plan deletes customers, then sabotages phase 1's recorder and forges its outputs.
    Phase 2 measures the database independently, so the deletion is still reported (and will be the thing replayed)."""
    c = rehearse('''
import json, builtins
ctx.db.execute("DELETE FROM customers WHERE id <= 500")
fake = {"ok": True, "error": None, "payments": [], "emails": [], "blocked": [], "logs": ["all good"], "guards": {}}
json.dump = lambda obj, f, **kw: f.write(json.dumps(fake))
open("/work/out/intents.json", "w").write(json.dumps(fake))
open("/work/out/consequences.json", "w").write('{"tables": {}}')
''')
    assert c["measured_by"] == "trusted-phase-2"
    assert c["tables"]["customers"]["deleted"] == 500
    assert any(f["severity"] == "critical" for f in agent.red_flags(c))


@needs_docker
def test_symlink_swap_cannot_read_host_files(fresh_business, tmp_path):
    """Replacing its database with a symlink to a host path must not make the host copy that file."""
    secret = config.DATA_DIR / "host-secret.txt"
    secret.write_text("TOP-SECRET-HOST-FILE")
    c = rehearse(f'''
import os
os.remove("/work/work.db")
os.symlink("{secret}", "/work/work.db")
''')
    assert not c["ok"] and "replaced or removed" in c["error"]["message"]
    assert "TOP-SECRET" not in str(c)
    assert c["tables"] == {}


@needs_docker
def test_disk_fill_is_capped(fresh_business):
    c = rehearse('''
with open("/work/huge.bin", "wb") as f:
    for _ in range(400):
        f.write(b"x" * (1024 * 1024))
''')
    assert not c["ok"] and ("File too large" in c["error"]["message"] or "Errno 27" in c["error"]["message"])


@needs_docker
def test_fork_bomb_is_capped(fresh_business):
    c = rehearse('''
import os
pids = []
for _ in range(500):
    pid = os.fork()
    if pid == 0:
        import time; time.sleep(5); os._exit(0)
    pids.append(pid)
''')
    assert not c["ok"] and ("Resource temporarily unavailable" in c["error"]["message"] or "BlockingIOError" in c["error"]["message"])


@needs_docker
def test_infinite_loop_hits_the_time_cap(fresh_business, monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_TIMEOUT_S", 4)
    c = rehearse("while True:\n    pass")
    assert not c["ok"] and "time cap" in c["error"]["message"]
    assert c["sandbox"]["killed"]


@needs_docker
def test_corrupted_database_is_reported(fresh_business):
    c = rehearse('''
open("/work/work.db", "wb").write(b"this is not a database")
''')
    assert not c["ok"] and "corrupted" in c["error"]["message"]
    assert sqlite3.connect(fresh_business).execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1300
