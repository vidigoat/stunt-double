"""Surgical approval, end to end: the bad refund plan becomes exactly the right 104 refunds, re-rehearsed, verified,
approved and applied. And the engine refuses to cut when it can't prove the cut."""
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from tests.conftest import needs_docker

PLANS = json.loads((Path(__file__).parent / "refund_plans.json").read_text())
JURY_CHECK = ("SELECT c.id FROM charges c WHERE c.status = 'refunded' AND "
              "(SELECT COUNT(*) FROM charges c2 WHERE c2.order_id = c.order_id) < 2")


def _wait(api, rid, done=("review", "failed", "applied")):
    for _ in range(400):
        r = api.get(f"/api/runs/{rid}").json()
        if r["status"] in done and (r["status"] != "review" or r.get("verdict")):
            return r
        time.sleep(0.25)
    return r


def _jury(monkeypatch, rule_sql=JURY_CHECK):
    def fake(task, code, consequences, emit, models=None, vision=True):
        if consequences.get("payments", {}).get("count") == 104:
            return {"verdict": "looks_right", "headline": "exactly the 104 double charges", "summary": "", "concerns": []}
        return {"verdict": "dangerous", "headline": "640 never double-charged", "summary": "", "concerns": [],
                "rule": {"title": "Refunds only for real double charges", "sql": rule_sql}}
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.agent, "verify", fake)
    monkeypatch.setattr(main, "_verify_budget", lambda: True)


@needs_docker
def test_the_wrong_plan_becomes_the_right_outcome(fresh_business, monkeypatch):
    _jury(monkeypatch)
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    run = _wait(api, rid)
    offer = run["surgical"]["offer"]
    assert (offer["units_total"], offer["units_kept"], offer["units_dropped"]) == (744, 104, 640)
    assert offer["kept"]["money_cents"] == 513600 and offer["dropped"]["money_cents"] == 3226800

    assert api.post(f"/api/runs/{rid}/surgical").status_code == 200
    run = _wait(api, rid)
    sub = run["attempts"][-1]
    assert sub["surgical_of"] == 1 and sub["consequences"]["sandbox"]["profile"] == "subset"
    assert sub["code"].startswith("# SURGICAL SUBSET of attempt 1. THIS CODE DOES NOT RUN AGAIN.")   # so the jury judges effects, not code
    assert sub["consequences"]["payments"]["count"] == 104 and sub["consequences"]["emails"]["count"] == 104
    assert sub["consequences"]["graph"]["units"] == 104
    assert run["verdict"]["verdict"] == "looks_right" and not any(f["severity"] == "critical" for f in sub["flags"])

    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya", "note": "the 104 real double charges"})
    assert r.json()["status"] == "applied", r.json()
    ledger = api.get("/api/beanpay/ledger").json()
    assert ledger["count"] == 104 and ledger["total_cents"] == 513600


@needs_docker
def test_no_cut_when_a_flagged_row_cant_be_traced(fresh_business, monkeypatch):
    # a check that flags rows of a table the plan never touched: nothing in the graph explains them
    _jury(monkeypatch, rule_sql="SELECT id FROM customers WHERE vip = 1 AND id IN (SELECT customer_id FROM charges WHERE status = 'refunded')")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    run = _wait(api, rid)
    assert "offer" not in (run.get("surgical") or {})
    assert api.post(f"/api/runs/{rid}/surgical").status_code == 409


@needs_docker
def test_a_subset_is_never_cut_again_and_needs_review(fresh_business, monkeypatch):
    _jury(monkeypatch)
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    _wait(api, rid)
    api.post(f"/api/runs/{rid}/surgical")
    _wait(api, rid)
    assert api.post(f"/api/runs/{rid}/surgical").status_code == 409             # one cut, then a person decides
    applied_before = api.get("/api/beanpay/ledger").json()["count"]
    assert applied_before == 0                                                   # nothing applied without approval


@needs_docker
def test_one_unit_of_work_comes_with_the_reasons_its_parts_belong_together(fresh_business, monkeypatch):
    _jury(monkeypatch)
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    _wait(api, rid)
    u = api.get(f"/api/runs/{rid}/graph", params={"attempt": 1, "unit": 0}).json()
    assert u["units"] == 744 and {n["kind"] for n in u["nodes"]} >= {"row", "refund", "email", "context"}
    whys = {e[2] for e in u["edges"]}
    assert "charges.customer_id → customers" in whys and any("refund" in w for w in whys) and any("email" in w for w in whys), whys
    assert api.get(f"/api/runs/{rid}/graph", params={"unit": 744}).status_code == 404
