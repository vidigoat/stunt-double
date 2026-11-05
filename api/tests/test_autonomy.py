"""Graduated autonomy: small, clean, AI-confirmed changes apply without a human; everything else waits."""
import time

from fastapi.testclient import TestClient

from app import main, policy
from tests.conftest import needs_docker

SMALL = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id = 9\")\n"
BIG = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id <= 60\")\n"


def _run(api, code):
    rid = api.post("/api/runs/manual", json={"task": "tidy a customer name", "code": code}).json()["id"]
    for _ in range(120):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "applied", "failed"):
            return run
        time.sleep(0.25)
    return run


@needs_docker
def test_small_clean_confirmed_change_applies_without_a_human(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.agent, "verify", lambda *a, **k: {"verdict": "looks_right", "headline": "fine", "summary": "", "concerns": []})
    monkeypatch.setattr(main, "_verify_budget", lambda: True)
    api = TestClient(main.app)
    assert _run(api, SMALL)["status"] == "review"                 # off by default: a human decides
    policy.save({"autonomy_enabled": True, "autonomy_max_rows": 20})
    run = _run(api, SMALL)
    assert run["status"] == "applied" and run["approval"]["auto"] and "Autonomy" in run["approval"]["approver"]
    assert _run(api, BIG)["status"] == "review"                   # 60 rows: over budget, a human decides


@needs_docker
def test_autonomy_never_applies_when_the_ai_objects(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.agent, "verify", lambda *a, **k: {"verdict": "concerns", "headline": "wrong customer", "summary": "", "concerns": []})
    monkeypatch.setattr(main, "_verify_budget", lambda: True)
    policy.save({"autonomy_enabled": True})
    assert _run(TestClient(main.app), SMALL)["status"] == "review"
