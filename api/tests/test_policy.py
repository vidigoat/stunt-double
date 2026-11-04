"""Deterministic safety checks + the editable approval policy."""
import pytest
from fastapi.testclient import TestClient

from app import agent, main, policy, sandbox
from tests.conftest import needs_docker


def plan(body: str) -> str:
    return "def run(ctx):\n" + "\n".join("    " + line for line in body.strip().splitlines()) + "\n"


def flags_for(body: str):
    c = sandbox.rehearse(plan(body))["consequences"]
    return c, agent.red_flags(c)


def rules(flags, severity=None):
    return {f["rule"] for f in flags if severity is None or f["severity"] == severity}


@pytest.fixture(autouse=True)
def default_policy():
    policy.reset()
    yield
    policy.reset()


@needs_docker
def test_broken_template_is_blocked(fresh_business):
    c, flags = flags_for('''
for cid, email in ctx.db.execute("SELECT id, email FROM customers LIMIT 3").fetchall():
    ctx.email.send(email, "Thanks!", "Hi {{first_name}}, thanks for being a customer.")
''')
    assert c["audit"]["emails"]["templated_count"] == 3
    assert "block_broken_templates" in rules(flags, "critical")


@needs_docker
def test_vip_emails_warn_but_do_not_block(fresh_business):
    c, flags = flags_for('''
for email, name in ctx.db.execute("SELECT email, name FROM customers WHERE vip=1").fetchall():
    ctx.email.send(email, "A thank-you", f"Hi {name.split()[0]}, thank you!")
''')
    assert c["audit"]["emails"]["vip_count"] > 0
    assert "warn_vip_emails" in rules(flags) and not rules(flags, "critical")


@needs_docker
def test_over_refund_and_double_refund_are_blocked(fresh_business):
    _, flags = flags_for('''
cid, amt = ctx.db.execute("SELECT id, amount_cents FROM charges LIMIT 1").fetchone()
ctx.payments.refund(cid, amt * 10, "oops")
cid2, amt2 = ctx.db.execute("SELECT id, amount_cents FROM charges LIMIT 1 OFFSET 1").fetchone()
ctx.payments.refund(cid2, amt2, "first")
ctx.payments.refund(cid2, amt2, "again")
ctx.payments.refund(999999, 100, "ghost")
''')
    titles = " | ".join(f["title"] for f in flags if f["severity"] == "critical")
    assert "exceed the original charge" in titles and "already refunded" in titles and "don't exist" in titles


@needs_docker
def test_data_leak_is_blocked(fresh_business):
    _, flags = flags_for('''
rows = ctx.db.execute("SELECT email FROM customers LIMIT 2").fetchall()
ctx.email.send(rows[0][0], "FYI", "We also contacted " + rows[1][0])
''')
    assert "block_data_leaks" in rules(flags, "critical")


@needs_docker
def test_protected_table_and_policy_changes(fresh_business):
    one_delete = 'ctx.db.execute("DELETE FROM customers WHERE id = 1")'
    _, flags = flags_for(one_delete)
    assert "protected_tables" in rules(flags, "critical")
    policy.save({"protected_tables": []})
    _, flags = flags_for(one_delete)
    assert not rules(flags, "critical")               # 1 of 1,300 is under the 5% limit once unprotected


def test_policy_api_validates():
    api = TestClient(main.app)
    assert api.get("/api/policy").json()["policy"]["max_delete_pct"] == 5
    assert api.put("/api/policy", json={"max_delete_pct": 2}).json()["policy"]["max_delete_pct"] == 2
    assert api.put("/api/policy", json={"max_delete_pct": -1}).status_code == 422
    assert api.put("/api/policy", json={"nope": 1}).status_code == 422
    assert api.put("/api/policy", json={"protected_tables": ["x; DROP TABLE y"]}).status_code == 422


@needs_docker
def test_marketing_to_opted_out_is_blocked_but_transactional_is_fine(fresh_business):
    _, flags = flags_for('''
for email, name in ctx.db.execute("SELECT email, name FROM customers WHERE vip=1").fetchall():
    ctx.email.send(email, "A thank-you from Bean There", f"Hi {name.split()[0]}, use code BEANS10 for 10% off your next box.")
''')
    assert "block_marketing_to_opted_out" in rules(flags, "critical")
    _, flags = flags_for('''
for email, name in ctx.db.execute("SELECT email, name FROM customers WHERE vip=1 AND marketing_opt_in=1").fetchall():
    ctx.email.send(email, "A thank-you from Bean There", f"Hi {name.split()[0]}, use code BEANS10 for 10% off your next box.", kind="marketing")
''')
    assert "block_marketing_to_opted_out" not in rules(flags)
    _, flags = flags_for('''
for email, name in ctx.db.execute("SELECT email, name FROM customers WHERE marketing_opt_in=0 LIMIT 5").fetchall():
    ctx.email.send(email, "Your refund", f"Hi {name.split()[0]}, we refunded your duplicate charge.", kind="transactional")
''')
    assert "block_marketing_to_opted_out" not in rules(flags)
