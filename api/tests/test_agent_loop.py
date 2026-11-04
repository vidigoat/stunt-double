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

    def create(self, model, messages, tools, temperature, **kw):
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
    def first(m):
        return m.split(",")[0].strip()
    assert set(model.calls) == {first(agent.config.AGENT_MODEL), first(agent.config.VERIFIER_MODEL)}
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


# ---- robustness: odd model behaviour must not break the run -------------------------------------------
class NotFound(Exception):
    status_code = 404


class QuirkyModel:
    """First model 'does not exist'. The fallback model: chats instead of calling a tool (needs a nudge), then emits
    a tool call as TEXT with fenced code, then finishes. The verifier forgets the verdict once."""
    def __init__(self):
        self.models = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools, temperature, **kw):
        self.models.append(model)
        if model == "missing-model":
            raise NotFound("model not found")
        names = {t["function"]["name"] for t in tools}
        last = messages[-1]
        if "verdict" in names:
            if "not called `verdict`" in str(last.get("content")):
                return NS(choices=[NS(message=NS(content="", tool_calls=[_tool_call(9, "verdict", {"verdict": "weird", "headline": "ok", "summary": "s",
                                                                                                    "concerns": [{"title": "t"}, "junk"]})]))])
            return NS(choices=[NS(message=NS(content="Looks fine to me.", tool_calls=None))])
        if last["role"] == "user" and "not called `submit_plan`" in last["content"]:
            fenced = "```python\n" + CORRECT + "\n```"
            text = "<tool_call>" + json.dumps({"name": "submit_plan", "arguments": {"code": fenced, "summary": "refund dupes"}}) + "</tool_call>"
            return NS(choices=[NS(message=NS(content=text, tool_calls=None))])
        if last["role"] == "user" and last["content"].startswith("Result of submit_plan"):
            return NS(choices=[NS(message=NS(content="Done.", tool_calls=None))])
        return NS(choices=[NS(message=NS(content="I think we should refund people.", tool_calls=None))])


@needs_docker
def test_agent_survives_quirky_models(fresh_business, monkeypatch):
    model = QuirkyModel()
    monkeypatch.setattr(agent, "client", lambda: model)
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    events = []
    rehearsals = []

    def rehearse(code, summary):
        rehearsals.append(code)
        from app import sandbox
        return sandbox.rehearse(code)["consequences"]

    monkeypatch.setattr(agent.config, "AGENT_MODEL", "missing-model,fallback-model")
    final, _ = agent.ops_agent("Refund double charges", rehearse, lambda *a: events.append(a))
    assert final == "Done." and len(rehearsals) == 1
    assert rehearsals[0].startswith("\ndef run(ctx):") or rehearsals[0].lstrip().startswith("def run(ctx):")
    assert "```" not in rehearsals[0]
    assert "missing-model" in model.models and "fallback-model" in model.models
    assert any("unavailable" in e[1] for e in events)

    from app import sandbox
    c = sandbox.rehearse(rehearsals[0])["consequences"]
    monkeypatch.setattr(agent.config, "VERIFIER_MODEL", "fallback-model")
    v = agent.verify("Refund double charges", rehearsals[0], c, lambda *a: None)
    assert v["verdict"] == "concerns"                      # invalid enum is normalised, never trusted
    assert v["concerns"] == [{"title": "t", "detail": "", "severity": "medium"}]


def test_parse_helpers():
    assert agent._parse_args('{"a": 1}') == {"a": 1}
    assert agent._parse_args(json.dumps(json.dumps({"a": 1}))) == {"a": 1}   # double-encoded
    assert agent._parse_args("not json") == {}
    assert agent.clean_code("```py\ndef run(ctx):\n    pass\n```").startswith("def run(ctx):")
    calls = agent._calls_from_text('sure ```json\n{"name": "run_query", "arguments": {"sql": "SELECT 1"}}\n```')
    assert calls and calls[0]["name"] == "run_query" and calls[0]["arguments"] == {"sql": "SELECT 1"}


@needs_docker
def test_history_audit_and_stream(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
    with api.stream("GET", f"/api/runs/{rid}/stream") as s:          # SSE ends once the run leaves the active states
        frames = [json.loads(line[6:]) for line in s.iter_lines() if line.startswith("data: ")]
    assert frames[-1]["status"] == "review" and len(frames) >= 2
    run = api.post(f"/api/runs/{rid}/approve").json()
    assert run["status"] == "applied"
    appr = run["approval"]
    assert len(appr["plan_sha256"]) == 64 and appr["effects_sha256"] == run["attempts"][-1]["effects_sha256"]
    hist = {h["id"]: h for h in api.get("/api/runs").json()}
    assert hist[rid]["money_cents"] == 513_600 and hist[rid]["approval"]["approver"] == "Demo approver"
    assert (main.HISTORY_DIR / f"{rid}.json").exists()               # persisted for restarts


@needs_docker
def test_tampered_effects_are_refused(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
    for _ in range(80):
        if api.get(f"/api/runs/{rid}").json()["status"] == "review":
            break
        time.sleep(0.25)
    path = main.RUNS[rid]["attempts"][-1]["effects_path"]
    data = json.loads(open(path).read()); data["payments"][0]["amount_cents"] = 999_999
    import os
    tmp = path + ".forged"
    open(tmp, "w").write(json.dumps(data))
    os.replace(tmp, path)          # swap the file in (works even when the sandbox user owns the original)
    r = api.post(f"/api/runs/{rid}/approve")
    assert r.status_code == 409 and "Integrity" in r.json()["detail"]


@needs_docker
def test_named_approval_and_evidence_bundle(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
    for _ in range(80):
        if api.get(f"/api/runs/{rid}").json()["status"] == "review":
            break
        time.sleep(0.25)
    run = api.post(f"/api/runs/{rid}/approve", json={"approver": "  Priya   Patel (Finance Ops) "}).json()
    assert run["approval"]["approver"] == "Priya Patel (Finance Ops)"
    r = api.get(f"/api/runs/{rid}/evidence")
    assert "attachment" in r.headers["content-disposition"]
    ev = r.json()
    a = ev["attempts"][0]
    assert a["plan"] == CORRECT and len(a["plan_sha256"]) == 64 and ev["approval"]["plan_sha256"] == a["plan_sha256"]
    assert ev["apply_result"]["refunds"] == 104
    assert a["consequences"]["payments"]["count"] == 104 and a["consequences"]["measured_by"] == "trusted-phase-2"
