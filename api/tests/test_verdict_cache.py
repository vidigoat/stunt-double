"""A live AI verdict is reused only for the identical request, measured effects, data, policy and model, is labelled
as reused, and 'Re-check live' always runs the AI again."""
import sqlite3
import time

from fastapi.testclient import TestClient

from app import config, main
from tests.conftest import needs_docker

PLAN = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id <= 3\")\n"
TASK = "tidy three customer names"


def _wait(api, rid, done=("review", "applied", "failed")):
    for _ in range(160):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in done:
            return run
        time.sleep(0.25)
    return run


def _start(api):
    return api.post("/api/runs/manual", json={"task": TASK, "code": PLAN}).json()["id"]


@needs_docker
def test_identical_facts_reuse_the_live_verdict_and_recheck_runs_live(fresh_business, monkeypatch):
    calls = []

    def fake_verify(*a, **k):
        calls.append(1)
        return {"verdict": "concerns", "headline": f"live check #{len(calls)}", "summary": "", "concerns": []}

    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.agent, "verify", fake_verify)
    monkeypatch.setattr(main, "_verify_budget", lambda: True)
    api = TestClient(main.app)

    first = _wait(api, _start(api))
    assert first["verdict"]["headline"] == "live check #1" and not first["verdict"].get("cached")
    second = _wait(api, _start(api))
    assert second["verdict"]["headline"] == "live check #1" and second["verdict"]["cached"]["at"] > 0
    assert len(calls) == 1                                           # identical facts: no second AI call

    assert api.post(f"/api/runs/{first['id']}/recheck").status_code == 409  # a live verdict has nothing to replace
    assert api.post(f"/api/runs/{second['id']}/recheck").status_code == 200
    rechecked = None
    for _ in range(160):
        rechecked = api.get(f"/api/runs/{second['id']}").json()
        if rechecked["status"] == "review" and rechecked.get("verdict"):
            break
        time.sleep(0.25)
    assert rechecked["verdict"]["headline"] == "live check #2" and not rechecked["verdict"].get("cached")


@needs_docker
def test_any_change_in_the_data_means_a_fresh_live_check(fresh_business, monkeypatch):
    calls = []
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(main.agent, "verify", lambda *a, **k: calls.append(1) or {"verdict": "looks_right", "headline": "ok", "summary": "", "concerns": []})
    monkeypatch.setattr(main, "_verify_budget", lambda: True)
    api = TestClient(main.app)
    _wait(api, _start(api))
    con = sqlite3.connect(config.PROD_DB)
    con.execute("UPDATE tickets SET subject = subject || ' ' WHERE id = 1")  # unrelated to the plan, but the data changed
    con.commit(); con.close()
    run = _wait(api, _start(api))
    assert len(calls) == 2 and not run["verdict"].get("cached")
