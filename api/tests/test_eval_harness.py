"""Wiring test for eval/run_eval.py: route its HTTP calls through the in-process API with the scripted model.
(The real evaluation runs against Vultr Serverless Inference; this only checks the harness's code paths.)"""
import json

from fastapi.testclient import TestClient

from app import agent, main
from eval import run_eval
from tests.conftest import needs_docker
from tests.test_agent_loop import ScriptedModel


@needs_docker
def test_eval_harness_runs_end_to_end(fresh_business, monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "client", lambda: ScriptedModel())
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "test")
    api = TestClient(main.app)

    def call(_base, path, body=None):
        r = api.post(path, json=body) if body is not None else api.get(path)
        r.raise_for_status()
        return r.json()

    monkeypatch.setattr(run_eval, "call", call)
    monkeypatch.setattr(run_eval, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--api", "http://test", "--runs", "1"])
    run_eval.main()
    report = (tmp_path / "docs" / "EVAL.md").read_text()
    raw = json.loads((tmp_path / "docs" / "eval-results.json").read_text())
    assert "| Refund double charges |" in report and "| Handle support tickets |" in report and "| VIP thank-you promo |" in report
    r = raw["results"]["refund"][0]
    assert r["first_refunds"] == 104 and r["first_plan_wrong"] is False and r["verdict"] == "looks_right"
    assert raw["results"]["tickets"][0]["hijacked"] is False
