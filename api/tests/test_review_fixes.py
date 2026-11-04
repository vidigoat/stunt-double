"""Regression tests for the findings of the independent security review (Nov 4)."""
import json
import sqlite3
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import agent, apply as applier, main, sandbox
from tests.conftest import needs_docker
from tests.test_engine import CORRECT


def rehearse(body: str) -> dict:
    code = "def run(ctx):\n" + "\n".join("    " + line for line in body.strip().splitlines()) + "\n"
    return sandbox.rehearse(code)


def critical(c) -> set:
    return {f["rule"] for f in agent.red_flags(c) if f["severity"] == "critical"}


@needs_docker
def test_1_column_name_injection_is_blocked_and_never_applied(fresh_business):
    res = rehearse('''ctx.db.execute('ALTER TABLE customers ADD COLUMN "name""=?, ""marketing_opt_in""=1, ""vip""=1 WHERE ?<>0 OR 1 --" DEFAULT \\'hi\\'')''')
    c = res["consequences"]
    assert c["tables"]["customers"]["schema_changed"] is True
    assert "block_schema_changes" in critical(c)
    with pytest.raises(ValueError, match="never auto-applied"):
        applier.apply("run_x", res["effects_path"])
    assert sqlite3.connect(fresh_business).execute("SELECT SUM(vip) FROM customers").fetchone()[0] == 14


def test_1_apply_refuses_unknown_identifiers_even_if_effects_are_forged(fresh_business, tmp_path):
    forged = {"changes": {"customers": {"dropped": False, "created": False, "deleted": [], "inserted": [], "updated": [
        {"rowid": 1, "before": {"name": "x"}, "after": {'name"=?, "vip"=1 --': "y"}, "changed": ['name"=?, "vip"=1 --']}]}},
        "payments": [], "emails": []}
    p = tmp_path / "effects.json"
    p.write_text(json.dumps(forged))
    with pytest.raises(ValueError, match="unknown columns"):
        applier.apply("run_x", str(p))


@needs_docker
def test_2_3_header_injection_and_multi_recipient_are_blocked(fresh_business):
    for to in ['c1@example.com\\nBcc: everyone@example.com', 'Alice <ava.patel1@example.com>', 'ava.patel1@example.com, attacker@evil.com']:
        c = rehearse(f'ctx.email.send({to!r}, "Hi", "Hello")')["consequences"]
        assert "invalid_recipients" in critical(c), to


@needs_docker
def test_3_promo_labelled_transactional_still_respects_unsubscribes(fresh_business):
    c = rehearse('''
for email, name in ctx.db.execute("SELECT email, name FROM customers WHERE marketing_opt_in=0 LIMIT 3").fetchall():
    ctx.email.send(email, "Order update", "Use code BEANS10 for 10% off!", kind="transactional")
''')["consequences"]
    assert "block_marketing_to_opted_out" in critical(c)


@needs_docker
def test_4_fifo_cannot_hang_the_host(fresh_business):
    t0 = time.time()
    c = rehearse('import os\nos.remove("/work/work.db")\nos.mkfifo("/work/work.db")')["consequences"]
    assert time.time() - t0 < 30 and not c["ok"] and "replaced or removed" in c["error"]["message"]


@needs_docker
def test_4_symlinked_out_dir_is_refused(fresh_business):
    c = rehearse('import os, shutil\nshutil.rmtree("/work/out")\nos.symlink("/etc", "/work/out")')["consequences"]
    assert "killed before it could finish" in c["error"]["message"] or not c["ok"]


@needs_docker
def test_5_concurrent_approvals_apply_once(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "refund", "code": CORRECT}).json()["id"]
    for _ in range(80):
        if api.get(f"/api/runs/{rid}").json()["status"] == "review":
            break
        time.sleep(0.25)
    codes = []
    threads = [threading.Thread(target=lambda: codes.append(api.post(f"/api/runs/{rid}/approve").status_code)) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes).count(200) == 1 and api.get("/api/beanpay/ledger").json()["count"] == 104


@needs_docker
def test_6_refunds_already_in_the_ledger_are_refused(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    refund_only = "def run(ctx):\n    ctx.payments.refund(8, 1800, 'dup')\n"   # never marks the charge refunded
    ids = []
    for _ in range(2):
        rid = api.post("/api/runs/manual", json={"task": "refund", "code": refund_only}).json()["id"]
        for _ in range(80):
            if api.get(f"/api/runs/{rid}").json()["status"] == "review":
                break
            time.sleep(0.25)
        ids.append(rid)
    assert api.post(f"/api/runs/{ids[0]}/approve").status_code == 200
    r = api.post(f"/api/runs/{ids[1]}/approve")
    assert r.status_code == 409 and "already refunded" in r.json()["detail"]


@needs_docker
def test_7_mass_update_of_protected_table_is_blocked(fresh_business):
    c = rehearse('ctx.db.execute("UPDATE customers SET email = \'x\' || id || \'@evil.com\', marketing_opt_in = 1")')["consequences"]
    assert "max_update_pct_protected" in critical(c)


def test_8_reject_only_while_awaiting_review_and_query_timeout(fresh_business):
    api = TestClient(main.app)
    run = main._new_run("t", "manual")
    run["status"] = "applied"
    assert api.post(f"/api/runs/{run['id']}/reject").status_code == 409
    t0 = time.time()
    r = agent.run_query("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n")
    assert "error" in r and time.time() - t0 < 15


# ---- second review round -----------------------------------------------------------------------------
@needs_docker
def test_r2_address_whitespace_and_case_cannot_dodge_consent(fresh_business):
    db = sqlite3.connect(fresh_business)
    email = db.execute("SELECT email FROM customers WHERE marketing_opt_in = 0 LIMIT 1").fetchone()[0]
    for to in [email + " ", " " + email]:
        c = rehearse(f'ctx.email.send({to!r}, "Hi", "Use code BEANS10 for 10% off")')["consequences"]
        assert "invalid_recipients" in critical(c), repr(to)
    c = rehearse(f'ctx.email.send({email.upper()!r}, "Hi", "Use code BEANS10 for 10% off")')["consequences"]
    assert "block_marketing_to_opted_out" in critical(c)
    c = rehearse('ctx.email.send("stranger@example.net", "Hi", "Hello")')["consequences"]
    assert "unknown_recipients" in critical(c)


@needs_docker
def test_r2_unicode_line_breaks_in_headers_are_blocked(fresh_business):
    for subject in ["Hi Bcc: x@y.z", "Hi\x0bthere", "Hi\x85there", "Hi\x1cthere"]:
        c = rehearse(f'ctx.email.send("ava.patel1@example.com", {subject!r}, "Hello")')["consequences"]
        assert "invalid_recipients" in critical(c), repr(subject)


def test_r2_apply_builds_emails_before_touching_the_database(fresh_business, tmp_path):
    bad = {"changes": {"charges": {"dropped": False, "created": False, "deleted": [], "inserted": [], "updated": [
        {"rowid": 8, "before": dict(zip(["id", "order_id", "customer_id", "amount_cents", "status", "created_at", "refunded_at"],
                                        sqlite3.connect(fresh_business).execute("SELECT * FROM charges WHERE rowid=8").fetchone())),
         "after": {}, "changed": ["status"]}]}},
        "payments": [{"charge_id": 8, "amount_cents": 1, "reason": "x"}], "emails": [{"to": "a@b.c", "subject": "x y", "body": "b"}]}
    bad["changes"]["charges"]["updated"][0]["after"] = {**bad["changes"]["charges"]["updated"][0]["before"], "status": "refunded"}
    p = tmp_path / "effects.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        applier.apply("run_x", str(p))
    assert sqlite3.connect(fresh_business).execute("SELECT status FROM charges WHERE rowid=8").fetchone()[0] == "succeeded"
    from app import beanpay
    assert beanpay.ledger()["count"] == 0


def test_r2_beanpay_refunds_each_charge_once_across_runs(fresh_business):
    from app import beanpay
    assert beanpay.refund(8, 1800, "dup", "run_a", "run_a:0")["status"] == "succeeded"
    assert beanpay.refund(8, 1800, "dup", "run_b", "run_b:0")["status"] == "duplicate_ignored"
    assert beanpay.ledger()["count"] == 1
