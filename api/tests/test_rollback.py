"""Rollback: undo an applied run's data changes through the same review + drift-checked apply."""
import sqlite3
import time

from fastapi.testclient import TestClient

from app import main
from tests.conftest import needs_docker
from tests.test_engine import CORRECT


def wait(api, rid, states=("review", "failed")):
    for _ in range(80):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in states:
            return run
        time.sleep(0.25)
    return run


@needs_docker
def test_rollback_restores_data_and_reports_irreversible_effects(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    db = lambda: sqlite3.connect(fresh_business)  # noqa: E731
    snapshot = db().execute("SELECT id, status, refunded_at FROM charges ORDER BY id").fetchall()
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
    wait(api, rid)
    assert api.post(f"/api/runs/{rid}/approve").json()["status"] == "applied"
    assert db().execute("SELECT COUNT(*) FROM charges WHERE status='refunded'").fetchone()[0] == 104

    rb = api.post(f"/api/runs/{rid}/rollback").json()["id"]
    run = api.get(f"/api/runs/{rb}").json()
    assert run["mode"] == "rollback" and run["status"] == "review" and run["rollback_of"] == rid
    c = run["attempts"][0]["consequences"]
    assert c["tables"]["charges"]["updated"] == 104 and c["irreversible"]["refunds"] == 104 and c["irreversible"]["emails"] == 104
    assert any(f["rule"] == "irreversible" for f in run["flags"])
    assert api.post(f"/api/runs/{rid}/rollback").status_code == 409            # one pending rollback at a time
    assert api.post(f"/api/runs/{rb}/approve").json()["status"] == "applied"
    assert db().execute("SELECT id, status, refunded_at FROM charges ORDER BY id").fetchall() == snapshot
    assert api.get(f"/api/runs/{rid}").json()["rolled_back_by"] == rb


@needs_docker
def test_rollback_refuses_rows_that_changed_after_the_apply(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
    wait(api, rid)
    api.post(f"/api/runs/{rid}/approve")
    rb = api.post(f"/api/runs/{rid}/rollback").json()["id"]
    conn = sqlite3.connect(fresh_business)
    conn.execute("UPDATE charges SET refunded_at='someone else touched this' WHERE status='refunded' AND id = (SELECT MIN(id) FROM charges WHERE status='refunded')")
    conn.commit()
    assert api.post(f"/api/runs/{rb}/approve").json()["status"] == "drifted"


def test_only_applied_runs_can_be_rolled_back(fresh_business):
    api = TestClient(main.app)
    run = main._new_run("t", "manual")
    run["status"] = "review"
    assert api.post(f"/api/runs/{run['id']}/rollback").status_code == 409
