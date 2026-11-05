"""The AI jury: other labs' models check the same facts in parallel; the jury can make a verdict stricter, never looser."""
import time

import pytest
from fastapi.testclient import TestClient

from app import config, main
from tests.conftest import needs_docker

PLAN = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id <= 2\")\n"


def _run(api):
    rid = api.post("/api/runs/manual", json={"task": "tidy two customer names", "code": PLAN}).json()["id"]
    for _ in range(160):
        r = api.get(f"/api/runs/{rid}").json()
        if r["status"] in ("review", "failed") and r.get("verdict"):
            return r
        time.sleep(0.25)
    return r


def _jury(monkeypatch, primary, deepseek, minimax, seen=None):
    def fake(task, code, consequences, emit, models=None, vision=True):
        name = (models or ["glm"])[0]
        if seen is not None:
            seen.append((name, vision))
        v = primary if name == "glm" else deepseek if name.startswith("deepseek") else minimax
        return {"verdict": v, "headline": f"{name} says {v}", "summary": "", "concerns": []}
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.config, "VERIFIER_MODEL", "glm")
    monkeypatch.setattr(main.config, "JURY_MODELS", ["deepseek-v4.1-flash-1017", "minimax-m3.1-flash"])
    monkeypatch.setattr(main.agent, "verify", fake)
    monkeypatch.setattr(main, "_verify_budget", lambda: True)


@needs_docker
@pytest.mark.parametrize("primary,deepseek,minimax,final,agree", [
    ("looks_right", "concerns", "concerns", "concerns", 2),     # two objections: no longer "looks right"
    ("looks_right", "concerns", "looks_right", "looks_right", 2),  # one objection is shown, not decisive
    ("looks_right", "dangerous", "looks_right", "concerns", 1),  # any "dangerous" rules out "looks right"
    ("dangerous", "looks_right", "looks_right", "dangerous", 1),  # the jury never loosens a verdict
    ("concerns", "dangerous", "dangerous", "dangerous", 3),     # two jurors say dangerous: escalate
])
def test_jury_only_makes_verdicts_stricter(fresh_business, monkeypatch, primary, deepseek, minimax, final, agree):
    seen = []
    _jury(monkeypatch, primary, deepseek, minimax, seen)
    run = _run(TestClient(main.app))
    v = run["verdict"]
    assert v["verdict"] == final
    assert v["jury"]["cast"] == 3 and v["jury"]["agree"] == agree
    assert [x["lab"] for x in v["jury"]["votes"]] == ["Zhipu GLM", "DeepSeek", "MiniMax"]
    assert sorted(seen) == sorted([("glm", True), ("deepseek-v4.1-flash-1017", False), ("minimax-m3.1-flash", False)])  # jurors: no images
    if final != primary:
        assert v["concerns"][0]["title"].startswith("The AI jury objected")


@needs_docker
def test_a_juror_that_cannot_finish_abstains(fresh_business, monkeypatch):
    _jury(monkeypatch, "looks_right", "looks_right", "looks_right")
    real = main.agent.verify

    def flaky(task, code, consequences, emit, models=None, vision=True):
        if models and models[0].startswith("minimax"):
            return {"verdict": "concerns", "headline": "Verifier could not finish", "summary": "", "concerns": []}
        return real(task, code, consequences, emit, models=models, vision=vision)
    monkeypatch.setattr(main.agent, "verify", flaky)
    v = _run(TestClient(main.app))["verdict"]
    assert v["verdict"] == "looks_right" and v["jury"]["cast"] == 2
    assert any(x["verdict"] is None and "abstained" in x["headline"] for x in v["jury"]["votes"])
