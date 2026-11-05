"""Catch -> rule: an AI catch, promoted by a human, becomes a deterministic check in phase 2 of every rehearsal."""
import time

import pytest
from fastapi.testclient import TestClient

from app import agent, main, rules, sandbox
from tests.conftest import needs_docker

GOOD_RULE = ("SELECT c.id FROM charges c WHERE c.status = 'refunded' AND NOT EXISTS "
             "(SELECT 1 FROM charges d WHERE d.order_id = c.order_id AND d.id <> c.id AND d.status = 'succeeded')")
NAIVE = '''def run(ctx):
    rows = ctx.db.execute("""
        SELECT c.id FROM charges c JOIN (SELECT customer_id, amount_cents, date(created_at) d FROM charges
          WHERE created_at >= '2026-10-26' AND status = 'succeeded' GROUP BY customer_id, amount_cents, d HAVING COUNT(*) > 1) dup
          ON c.customer_id = dup.customer_id AND c.amount_cents = dup.amount_cents AND date(c.created_at) = dup.d
        WHERE c.id NOT IN (SELECT MIN(id) FROM charges WHERE created_at >= '2026-10-26' GROUP BY customer_id, amount_cents, date(created_at))
    """).fetchall()
    for (cid,) in rows:
        ctx.db.execute("UPDATE charges SET status = 'refunded' WHERE id = ?", (cid,))
'''


@pytest.fixture(autouse=True)
def clean_rules():
    rules.reset()
    yield
    rules.reset()


def test_a_rule_must_pass_todays_data(fresh_business):
    with pytest.raises(ValueError, match="would flag today's data"):
        rules.check_sql("SELECT id FROM charges WHERE status = 'succeeded'", "demo")   # flags normal data: refused
    with pytest.raises(ValueError, match="one read-only SELECT"):
        rules.check_sql("DELETE FROM charges", "demo")
    with pytest.raises(ValueError, match="one read-only SELECT"):
        rules.check_sql("SELECT 1; DROP TABLE charges", "demo")
    assert rules.check_sql(GOOD_RULE, "demo")


@needs_docker
def test_a_learned_rule_blocks_the_mistake_without_ai(fresh_business):
    rules.add("demo", "Refunds need a second charge on the same order", GOOD_RULE, "run_x")
    c = sandbox.rehearse(NAIVE)["consequences"]
    hit = [r for r in c["rules"] if r["violations"]]
    assert hit and hit[0]["violations"] == 640
    assert "learned_rule" in {f["rule"] for f in agent.red_flags(c) if f["severity"] == "critical"}


@needs_docker
def test_promote_turns_the_verifiers_check_into_a_rule_and_reset_clears_it(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "refund double charges", "code": NAIVE}).json()["id"]
    for _ in range(80):
        if api.get(f"/api/runs/{rid}").json()["status"] == "review":
            break
        time.sleep(0.25)
    assert api.post(f"/api/runs/{rid}/promote").status_code == 409            # no verdict, no rule
    main.RUNS[rid]["verdict"] = {"verdict": "dangerous", "headline": "x", "rule": {"title": "Refunds need a sibling", "sql": GOOD_RULE}}
    r = api.post(f"/api/runs/{rid}/promote", json={"by": "Priya"}).json()
    assert r["title"] == "Refunds need a sibling" and api.get("/api/rules").json()["rules"][0]["by"] == "Priya"
    assert api.post(f"/api/runs/{rid}/promote").status_code == 422            # duplicate
    api.post("/api/demo/reset")
    assert api.get("/api/rules").json()["rules"] == []
