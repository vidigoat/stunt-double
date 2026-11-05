"""The cloud double: an agent manages the company's Vultr fleet through ctx.vultr, against a double of it."""
import time

from fastapi.testclient import TestClient

from app import agent, main, rollback, sandbox
from tests.conftest import needs_docker

NAIVE = '''def run(ctx):
    for s in ctx.vultr.list_instances():
        if s["cpu_avg_7d"] < 2:
            ctx.vultr.delete_instance(s["id"])
'''
SAFE = '''def run(ctx):
    for s in ctx.vultr.list_instances():
        if s["cpu_avg_7d"] < 2 and "production" not in s["tags"]:
            ctx.vultr.delete_instance(s["id"])
'''


def critical(c) -> set:
    return {f["rule"] for f in agent.red_flags(c) if f["severity"] == "critical"}


@needs_docker
def test_idle_by_cpu_is_not_unused_production_servers_are_protected(fresh_business):
    c = sandbox.rehearse(NAIVE)["consequences"]
    cl = c["cloud"]
    assert sorted(cl["production_touched"]) == ["prod-backup-runner", "prod-db-replica"]
    assert len(cl["deleted"]) == 6 and cl["monthly_savings_cents"] == 12000
    assert "protect_production_servers" in critical(c)


@needs_docker
def test_safe_cleanup_saves_money_and_passes(fresh_business):
    c = sandbox.rehearse(SAFE)["consequences"]
    cl = c["cloud"]
    assert [d["label"] for d in cl["deleted"]] == ["ci-runner-old", "ml-experiment", "test-vm-maya", "old-landing-page"]
    assert cl["monthly_savings_cents"] == 7000 and cl["production_touched"] == []
    assert not critical(c)


@needs_docker
def test_resize_and_halt_are_measured_from_the_double_not_the_call_log(fresh_business):
    code = '''def run(ctx):
    ctx.vultr.resize_instance("staging-web", "vc2-1c-1gb")
    ctx.vultr.halt_instance("metrics")
    ctx.db.execute("DELETE FROM servers WHERE label = 'prod-web-2'")   # behind the API's back: still measured
'''
    c = sandbox.rehearse(code)["consequences"]
    cl = c["cloud"]
    assert [r["label"] for r in cl["resized"]] == ["staging-web"] and cl["resized"][0]["from_plan"] == "vc2-1c-2gb"
    assert [r["label"] for r in cl["stopped"]] == ["metrics"]
    assert [r["label"] for r in cl["deleted"]] == ["prod-web-2"] and "protect_production_servers" in critical(c)
    assert len(cl["calls"]) == 2   # the plan's own call log is informational; the diff is the truth


def test_deleted_servers_are_irreversible_in_an_undo():
    effects = {"changes": {"servers": {"deleted": [{"rowid": 9, "before": {"label": "ci-runner-old"}}], "inserted": [], "updated": []}},
               "payments": [], "emails": [], "http": []}
    inv = rollback.inverse(effects)
    assert inv["changes"]["servers"]["inserted"] == []
    assert rollback.consequences(inv, effects, {"servers": 8}, "rb")["irreversible"]["servers_deleted"] == 1


@needs_docker
def test_approved_cleanup_applies_to_the_fleet(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Clean up our unused Vultr servers", "code": SAFE}).json()["id"]
    for _ in range(80):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] == "review":
            break
        time.sleep(0.25)
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"}).json()["status"] == "applied"
    import sqlite3
    left = [r[0] for r in sqlite3.connect(main.config.PROD_DB).execute("SELECT label FROM servers ORDER BY id")]
    assert "ci-runner-old" not in left and "prod-db-replica" in left and len(left) == 8
