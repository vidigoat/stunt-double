"""A learned rule must flag only the mistake: it is refused if it would block a rehearsal the AI judged correct."""
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from tests.conftest import needs_docker

PLANS = json.loads((Path(__file__).parent / "refund_plans.json").read_text())
OVER_BROAD = ("SELECT c.id FROM charges c WHERE c.status = 'refunded' AND "
              "(SELECT COUNT(*) FROM charges c2 WHERE c2.order_id = c.order_id AND c2.status = 'succeeded') < 2")
PRECISE = ("SELECT c.id FROM charges c WHERE c.status = 'refunded' AND "
           "(SELECT COUNT(*) FROM charges c2 WHERE c2.order_id = c.order_id) < 2")


def _run(api, plan):
    rid = api.post("/api/runs/manual", json={"task": plan["task"], "code": plan["code"]}).json()["id"]
    for _ in range(200):
        r = api.get(f"/api/runs/{rid}").json()
        if r["status"] in ("review", "failed") and r.get("verdict"):
            return r
        time.sleep(0.25)
    return r


def _verifier(monkeypatch, rule_sql):
    def fake(task, code, consequences, emit, models=None, vision=True):
        if "ONE order" in code or "order_id" in code and "GROUP BY" in code.upper():
            return {"verdict": "looks_right", "headline": "correct", "summary": "", "concerns": []}
        return {"verdict": "dangerous", "headline": "640 never double-charged", "summary": "", "concerns": [],
                "rule": {"title": "Refunds only for real double charges", "sql": rule_sql}}
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.agent, "verify", fake)
    monkeypatch.setattr(main, "_verify_budget", lambda: True)


@needs_docker
def test_an_over_broad_rule_that_would_block_a_correct_plan_is_not_offered(fresh_business, monkeypatch):
    _verifier(monkeypatch, OVER_BROAD)
    api = TestClient(main.app)
    good = _run(api, PLANS["good"])
    assert good["verdict"]["verdict"] == "looks_right"
    bad = _run(api, PLANS["bad"])
    assert bad["verdict"]["verdict"] == "dangerous" and not bad["verdict"].get("rule")      # not offered
    assert any("not offered" in e["title"] and good["id"] in (e.get("detail") or "") for e in bad["events"])


@needs_docker
def test_a_precise_rule_is_learned_and_then_blocks_the_mistake_without_ai(fresh_business, monkeypatch):
    _verifier(monkeypatch, PRECISE)
    api = TestClient(main.app)
    _run(api, PLANS["good"])
    bad = _run(api, PLANS["bad"])
    assert bad["verdict"]["rule"]["sql"]
    assert api.post(f"/api/runs/{bad['id']}/promote", json={}).status_code == 200
    calls = []
    monkeypatch.setattr(main.agent, "verify", lambda *a, **k: calls.append(1) or {"verdict": "looks_right", "headline": "x", "summary": "", "concerns": []})
    again = _run(api, PLANS["bad"])
    assert any("learned rule" in f["title"].lower() for f in again["attempts"][-1]["flags"]) and calls == []   # blocked, no AI
    assert _run(api, PLANS["good"])["attempts"][-1]["flags"] == [] or all("learned" not in f["title"].lower() for f in _run(api, PLANS["good"])["attempts"][-1]["flags"])
