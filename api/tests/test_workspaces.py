"""Bring your own database: rehearse, approve and undo against an uploaded SQLite workspace."""
import sqlite3
import time

from fastapi.testclient import TestClient

from app import main
from tests.conftest import needs_docker


def crm_db(path) -> bytes:
    db = sqlite3.connect(path)
    db.executescript("""
      CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, plan TEXT, mrr_cents INTEGER, churn_risk REAL);
      CREATE TABLE deals (id INTEGER PRIMARY KEY, account_id INTEGER, stage TEXT, value_cents INTEGER);
    """)
    db.executemany("INSERT INTO accounts VALUES (?,?,?,?,?)", [(i, f"Acct {i}", "pro" if i % 3 else "free", 4900 if i % 3 else 0, (i % 10) / 10) for i in range(1, 201)])
    db.executemany("INSERT INTO deals VALUES (?,?,?,?)", [(i, (i % 200) + 1, "open", 100000) for i in range(1, 51)])
    db.commit(); db.close()
    return open(path, "rb").read()


def wait(api, rid):
    for _ in range(80):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] not in ("queued", "planning", "rehearsing", "verifying", "applying"):
            return run
        time.sleep(0.25)
    return run


@needs_docker
def test_upload_rehearse_apply_and_undo_in_your_own_workspace(fresh_business, tmp_path, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    up = api.post("/api/workspaces?name=Acme%20CRM", content=crm_db(tmp_path / "crm.db"), headers={"content-type": "application/octet-stream"})
    assert up.status_code == 200, up.text
    ws = up.json()["id"]
    assert any(w["id"] == ws for w in api.get("/api/workspaces").json()["workspaces"])
    assert "deals" in api.get(f"/api/schema?ws={ws}").json()["tables"]

    plan = "def run(ctx):\n    ctx.db.execute(\"UPDATE deals SET stage='lost' WHERE value_cents >= 100000 AND id <= 10\")\n"
    rid = api.post("/api/runs/manual", json={"task": "Close the 10 oldest stale deals", "code": plan, "workspace": ws}).json()["id"]
    run = wait(api, rid)
    c = run["attempts"][-1]["consequences"]
    assert run["workspace"] == ws and c["tables"]["deals"]["updated"] == 10 and "customers" not in c["tables"]
    demo_before = sqlite3.connect(main.config.PROD_DB).execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Dana"}).json()["status"] == "applied"
    from app import workspaces
    wsdb = sqlite3.connect(workspaces.db_path(ws))
    assert wsdb.execute("SELECT COUNT(*) FROM deals WHERE stage='lost'").fetchone()[0] == 10
    assert sqlite3.connect(main.config.PROD_DB).execute("SELECT COUNT(*) FROM customers").fetchone()[0] == demo_before

    rb = api.post(f"/api/runs/{rid}/rollback").json()["id"]
    api.post(f"/api/runs/{rb}/approve", json={"approver": "Dana"})
    assert api.post(f"/api/runs/{rb}/approve", json={"approver": "Lee"}).json()["status"] == "applied"
    assert wsdb.execute("SELECT COUNT(*) FROM deals WHERE stage='lost'").fetchone()[0] == 0


@needs_docker
def test_mass_delete_in_an_uploaded_workspace_is_still_contained(fresh_business, tmp_path, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    ws = api.post("/api/workspaces?name=CRM", content=crm_db(tmp_path / "crm2.db")).json()["id"]
    rid = api.post("/api/runs/manual", json={"task": "clean up", "code": "def run(ctx):\n    ctx.db.execute('DELETE FROM accounts')\n", "workspace": ws}).json()["id"]
    run = wait(api, rid)
    assert any(f["severity"] == "critical" for f in run["attempts"][-1]["flags"])          # > 5% of a table
    from app import workspaces
    assert sqlite3.connect(workspaces.db_path(ws)).execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 200


def test_bad_uploads_are_refused(tmp_path):
    api = TestClient(main.app)
    assert api.post("/api/workspaces?name=x", content=b"not a database at all").status_code == 422
    p = tmp_path / "wr.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID")
    db.commit(); db.close()
    r = api.post("/api/workspaces?name=wr", content=p.read_bytes())
    assert r.status_code == 422 and "WITHOUT ROWID" in r.json()["detail"]
    assert api.post("/api/runs/manual", json={"task": "noop plan", "code": "def run(ctx):\n    pass\n", "workspace": "ws-nope"}).status_code == 404
