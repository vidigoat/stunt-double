"""Regression tests for security review 3 (connectors, workspaces, two-person rule, rollback, notifications)."""
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app import agent, connectors, main, policy, workspaces
from app.harness import runner
from tests.conftest import needs_docker


def wait(api, rid, states=("review", "failed", "rejected")):
    for _ in range(120):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in states:
            return run
        time.sleep(0.25)
    return run


def make_db(path, script: str) -> bytes:
    db = sqlite3.connect(path)
    db.executescript(script)
    db.commit()
    db.close()
    return open(path, "rb").read()


# ---- uploaded workspaces can't move demo money or send mail -----------------------------------------
@needs_docker
def test_uploaded_workspace_cannot_refund_or_email(fresh_business, tmp_path, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    data = make_db(tmp_path / "x.db", """
      CREATE TABLE charges (id INTEGER PRIMARY KEY, amount_cents INTEGER, status TEXT);
      CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT);
      INSERT INTO charges VALUES (1, 900000000, 'succeeded');
      INSERT INTO customers VALUES (1, 'victim@external.example');""")
    ws = api.post("/api/workspaces?name=evil", content=data).json()["id"]
    code = ("def run(ctx):\n    ctx.payments.refund(1, 900000000)\n"
            "    ctx.email.send('victim@external.example', 'Your refund', 'Hello there, your refund is on its way.')\n")
    rid = api.post("/api/runs/manual", json={"task": "refund charge 1", "code": code, "workspace": ws}).json()["id"]
    run = wait(api, rid)
    rules = {f["rule"] for f in run["attempts"][-1]["flags"] if f["severity"] == "critical"}
    assert "workspace_side_effects" in rules
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "A"})
    assert r.status_code == 409


def test_apply_refuses_side_effects_outside_demo(tmp_path):
    import json
    from app import apply as applier
    p = tmp_path / "effects.json"
    p.write_text(json.dumps({"changes": {}, "payments": [{"charge_id": 1, "amount_cents": 1}], "emails": [], "http": []}))
    with pytest.raises(ValueError, match="demo business"):
        applier.apply("r", str(p), "ws-deadbeef")


# ---- two-person rule: lookalike names are the same person ------------------------------------------
@pytest.mark.parametrize("second", ["Alice​", "Ａlice", "Al­ice", " ALICE ", "alice"])
def test_lookalike_names_are_one_person(second):
    assert main._person("Alice") == main._person(second)


def test_distinct_people_stay_distinct():
    assert main._person("Alice") != main._person("Alicia")
    assert main._person("​") == ""


# ---- uploads: triggers, generated columns, size, eviction, delete ------------------------------------
def test_upload_rejects_triggers(tmp_path):
    data = make_db(tmp_path / "t.db", """
      CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER); CREATE TABLE counters (n INTEGER);
      CREATE TRIGGER bump AFTER UPDATE ON t BEGIN UPDATE counters SET n = n + 1; END;""")
    with pytest.raises(ValueError, match="trigger"):
        workspaces.create("t", data)


def test_upload_rejects_generated_columns(tmp_path):
    data = make_db(tmp_path / "g.db", "CREATE TABLE t (a INTEGER, g INTEGER GENERATED ALWAYS AS (a * 100) VIRTUAL, c TEXT);")
    with pytest.raises(ValueError, match="generated"):
        workspaces.create("g", data)


def test_chunked_upload_over_limit_is_refused_while_streaming(monkeypatch):
    monkeypatch.setattr(workspaces, "MAX_BYTES", 1024)
    api = TestClient(main.app)

    def body():
        for _ in range(64):
            yield b"x" * 1024
    r = api.post("/api/workspaces?name=big", content=body())
    assert r.status_code == 413


def test_full_server_evicts_oldest_upload_and_delete_works(tmp_path, monkeypatch):
    monkeypatch.setattr(workspaces, "MAX_WORKSPACES", 2)
    data = make_db(tmp_path / "s.db", "CREATE TABLE t (id INTEGER PRIMARY KEY); INSERT INTO t VALUES (1);")
    for ws in [w["id"] for w in workspaces.all_workspaces() if w["kind"] == "upload"]:
        workspaces.delete(ws)
    a, b, c = (workspaces.create(n, data)["id"] for n in "abc")
    ids = [w["id"] for w in workspaces.all_workspaces()]
    assert a not in ids and b in ids and c in ids
    api = TestClient(main.app)
    assert api.delete(f"/api/workspaces/{b}").status_code == 200
    assert api.delete("/api/workspaces/demo").status_code == 404
    assert b not in [w["id"] for w in workspaces.all_workspaces()]


# ---- connectors: no path escapes, no plan-chosen routing headers -------------------------------------
@pytest.mark.parametrize("path", ["/../../admin/users", "/api/%2e%2e/admin", "/a/%252e%252e/b", "/a\\..\\b", "/ok/./x"])
def test_dot_segments_never_pass_the_connector_check(path):
    call = {"method": "POST", "url": "https://api.beancrm.example" + path, "host": "api.beancrm.example", "scheme": "https", "path": path}
    assert connectors.check(call) and runner.unsafe_path(path)


def test_real_delivery_forwards_only_allowlisted_headers(monkeypatch):
    seen = {}

    class R:
        status_code = 200

    def fake(method, url, json=None, headers=None, timeout=None):
        seen.update(url=url, headers=headers)
        return R()
    monkeypatch.setenv("SD_CRM_BASE_URL", "https://crm.real/api/v1")
    monkeypatch.setenv("SD_CRM_TOKEN", "t0k")
    monkeypatch.setenv("SD_CONNECTORS", '{"crm": {"host": "api.beancrm.example", "methods": ["POST"], "url_env": "SD_CRM_BASE_URL", '
                       '"token_env": "SD_CRM_TOKEN", "append_path": true}}')
    monkeypatch.setattr(connectors.httpx, "request", fake)
    call = {"method": "POST", "url": "https://api.beancrm.example/notes?x=1", "host": "api.beancrm.example", "scheme": "https",
            "path": "/notes?x=1", "json": {}, "headers": {"Host": "evil", "X-Forwarded-For": "1.2.3.4", "Content-Type": "application/json"}}
    assert connectors.deliver(call, "r")["ok"]
    assert seen["url"] == "https://crm.real/api/v1/notes?x=1"
    assert set(seen["headers"]) == {"Content-Type", "Authorization"}


def test_customer_data_spread_over_many_calls_is_still_a_leak():
    before = {"customers": {"rows": {i: {"email": f"c{i}@x.example"} for i in range(10)}}}
    calls = [{"method": "POST", "url": "https://hooks.slack.com/x", "host": "hooks.slack.com", "scheme": "https", "path": "/x",
              "json": {"text": f"c{i}@x.example"}, "headers": {}} for i in range(10)]
    h = runner.audit_http(before, calls)
    assert h["bulk_personal_data_count"] == 1 and h["customers_in_payloads"] == 10


def test_oversized_payloads_block():
    c = {"tables": {}, "payments": {}, "emails": {}, "http": {"count": 1},
         "audit": {"http": {"routes": [], "oversized_count": 1, "oversized": [{"url": "https://hooks.slack.com/x", "bytes": 70000}]}}}
    assert any(f["severity"] == "critical" and "too large" in f["title"] for f in agent.red_flags(c))


# ---- policy changes reach runs already awaiting approval ---------------------------------------------
@needs_docker
def test_tightened_policy_blocks_pending_run(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    code = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET marketing_opt_in = 0 WHERE id <= 30\")\n"
    rid = api.post("/api/runs/manual", json={"task": "opt out 30 customers", "code": code}).json()["id"]
    assert wait(api, rid)["status"] == "review"
    policy.save({"two_person_over_rows": 10})
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"}).json()
    assert r["status"] == "review"  # now needs a second person, though the rehearsal said one was enough
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Marco"}).json()["status"] == "applied"


# ---- notifications escape Slack markup ---------------------------------------------------------------
def test_slack_markup_is_escaped():
    assert main._slack("<!channel> <https://evil|Review> & co") == "&lt;!channel&gt; &lt;https://evil|Review&gt; &amp; co"


# ---- a rollback that can't be built never leaves a stuck run -----------------------------------------
@needs_docker
def test_unbuildable_rollback_creates_no_run(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    code = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '' WHERE id = 1\")\n"
    rid = api.post("/api/runs/manual", json={"task": "touch customer 1", "code": code}).json()["id"]
    wait(api, rid)
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"}).json()["status"] == "applied"
    main.RUNS[rid]["attempts"][-1]["effects_sha256"] = "0" * 64  # effects on disk no longer match what was approved
    n = len(main.RUNS)
    r = api.post(f"/api/runs/{rid}/rollback")
    assert r.status_code == 409 and len(main.RUNS) == n
    assert api.post("/api/demo/reset").status_code == 200


# ---- decision notes, rejection reasons, CSV audit export ---------------------------------------------
@needs_docker
def test_notes_reasons_and_csv_export(fresh_business, monkeypatch):
    import csv
    import io
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    code = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id = 2\")\n"
    a = api.post("/api/runs/manual", json={"task": "fix customer 2 name", "code": code}).json()["id"]
    b = api.post("/api/runs/manual", json={"task": "fix customer 2 name again", "code": code}).json()["id"]
    wait(api, a), wait(api, b)
    ok = api.post(f"/api/runs/{a}/approve", json={"approver": "Priya", "note": "Checked with support, ticket #88"}).json()
    assert ok["status"] == "applied" and ok["approval"]["notes"] == ["Priya: Checked with support, ticket #88"]
    no = api.post(f"/api/runs/{b}/reject", json={"approver": "Marco", "reason": "Duplicate of the run above"}).json()
    assert no["status"] == "rejected" and no["rejection"]["by"] == "Marco" and no["rejection"]["reason"] == "Duplicate of the run above"
    r = api.get("/api/runs.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = {x["run_id"]: x for x in csv.DictReader(io.StringIO(r.text))}
    assert rows[a]["approvers"] == "Priya" and "ticket #88" in rows[a]["approval_notes"] and len(rows[a]["effects_sha256"]) == 64
    assert rows[b]["status"] == "rejected" and rows[b]["rejection_reason"] == "Duplicate of the run above"


# ---- rehearsals expire ---------------------------------------------------------------------------------
@needs_docker
def test_old_rehearsals_cannot_be_approved(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    code = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id = 4\")\n"
    rid = api.post("/api/runs/manual", json={"task": "fix customer 4 name", "code": code}).json()["id"]
    wait(api, rid)
    main.RUNS[rid]["attempts"][-1]["created_at"] -= 25 * 3600
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"})
    assert r.status_code == 409 and "expired" in r.json()["detail"]
    policy.save({"approval_expires_hours": 0})  # 0 = never expire
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"}).json()["status"] == "applied"
