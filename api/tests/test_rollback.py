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
    first = api.post(f"/api/runs/{rb}/approve", json={"approver": "Priya"}).json()
    assert first["status"] == "review"                                         # rollbacks need two people
    assert api.post(f"/api/runs/{rb}/approve", json={"approver": "Marco"}).json()["status"] == "applied"
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
    api.post(f"/api/runs/{rb}/approve", json={"approver": "Priya"})
    assert api.post(f"/api/runs/{rb}/approve", json={"approver": "Marco"}).json()["status"] == "drifted"


def test_only_applied_runs_can_be_rolled_back(fresh_business):
    api = TestClient(main.app)
    run = main._new_run("t", "manual")
    run["status"] = "review"
    assert api.post(f"/api/runs/{run['id']}/rollback").status_code == 409


# ---- two-person rule --------------------------------------------------------------------------------
@needs_docker
def test_two_person_rule_for_big_payouts(fresh_business, monkeypatch):
    from app import policy
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    policy.save({"two_person_over_usd": 1000})
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]   # $5,136 > $1,000
    run = wait(api, rid)
    att = run["attempts"][-1]
    assert att["approvals_required"] == 2 and "payout over $1,000" in att["approval_reasons"]
    assert api.post(f"/api/runs/{rid}/approve", json={}).status_code == 422                    # needs a name
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"}).json()
    assert r["status"] == "review" and len(r["approvals"]) == 1
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "priya"}).status_code == 409   # same person
    assert sqlite3.connect(fresh_business).execute("SELECT COUNT(*) FROM charges WHERE status='refunded'").fetchone()[0] == 0
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Marco"}).json()
    assert r["status"] == "applied" and r["approval"]["approvers"] == ["Priya", "Marco"]
    policy.reset()


@needs_docker
def test_stats_count_what_was_stopped(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "clean up", "code": "def run(ctx):\n    ctx.db.execute('DELETE FROM customers')\n"}).json()["id"]
    wait(api, rid)
    st = api.get("/api/stats").json()
    assert st["stopped"] >= 1 and st["rows_protected"] >= 1300 and st["rehearsals"] >= 1
