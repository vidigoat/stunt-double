"""Exercise the full agent -> rehearse -> verify -> review flow with a scripted stand-in for the model.

This checks OUR wiring (tool calls, message format, state machine). Real model behaviour is tested live
against Vultr Serverless Inference.
"""
import json
import time
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from app import agent, main
from tests.conftest import needs_docker
from tests.test_engine import CORRECT


def _tool_call(i, name, args):
    return NS(id=f"call_{i}", type="function", function=NS(name=name, arguments=json.dumps(args)),
              model_dump=lambda: {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}})


class ScriptedModel:
    """Plays the ops agent (schema -> query -> submit -> done) and the verifier (query -> verdict)."""
    def __init__(self):
        self.calls = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools, temperature):
        self.calls.append(model)
        names = {t["function"]["name"] for t in tools}
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        n = len(tool_msgs)
        if "verdict" in names:  # verifier
            if n == 0:
                msg = NS(content="", tool_calls=[_tool_call(n, "run_query", {"sql": "SELECT COUNT(*) FROM charges WHERE status='succeeded'"})])
            else:
                msg = NS(content="", tool_calls=[_tool_call(n, "verdict", {"verdict": "looks_right", "headline": "Refunds exactly the 104 double charges",
                                                                          "summary": "104 customers get $5,136 back.", "concerns": []})])
        else:  # ops agent
            script = [("get_schema", {}), ("run_query", {"sql": "SELECT COUNT(*) FROM orders"}), ("submit_plan", {"code": CORRECT, "summary": "refund duplicates"})]
            msg = NS(content="", tool_calls=[_tool_call(n, *script[n])]) if n < len(script) else NS(content="Done: refunds the duplicate charges.", tool_calls=None)
        return NS(choices=[NS(message=msg)])


@needs_docker
def test_full_agent_flow(fresh_business, monkeypatch):
    model = ScriptedModel()
    monkeypatch.setattr(agent, "client", lambda: model)
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "test")
    api = TestClient(main.app)
    rid = api.post("/api/runs", json={"task": "Refund everyone who was double-charged last week"}).json()["id"]
    for _ in range(120):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    assert run["status"] == "review", run.get("error")
    assert run["verdict"]["verdict"] == "looks_right" and run["final_message"].startswith("Done")
    assert run["attempts"][-1]["consequences"]["payments"]["count"] == 104
    assert "effects_path" not in run["attempts"][-1]                      # internal paths never leak to the browser
    kinds = [e["kind"] for e in run["events"]]
    assert kinds.index("agent") < kinds.index("sandbox") < kinds.index("verify")
    assert set(model.calls) == {agent.config.AGENT_MODEL, agent.config.VERIFIER_MODEL}
    applied = api.post(f"/api/runs/{rid}/approve").json()
    assert applied["status"] == "applied" and applied["apply_result"]["refunds"] == 104


@needs_docker
def test_policy_blocks_critical_approval(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "clean up", "code": "def run(ctx):\n    ctx.db.execute('DELETE FROM customers')\n"}).json()["id"]
    for _ in range(80):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    r = api.post(f"/api/runs/{rid}/approve")
    assert r.status_code == 409 and "policy" in r.json()["detail"]
