"""The Python SDK, driven against the real API in-process."""
import sys
import threading
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdk" / "python"))

from stunt_double import StuntDouble  # noqa: E402

from app import main  # noqa: E402
from tests.conftest import needs_docker  # noqa: E402


@needs_docker
def test_sdk_decorator_rehearse_and_wait_for_human(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    http = TestClient(main.app)
    sd = StuntDouble("https://demo.example", http=http)
    assert "charges" in sd.describe()["tables"] and {c["name"] for c in sd.connectors()} >= {"slack"}

    @sd.plan("Refund everyone who was double-charged last week")
    def refund_duplicates(ctx):
        rows = ctx.db.execute("""SELECT id, amount_cents FROM charges WHERE created_at >= '2026-10-26' AND status='succeeded'
          AND order_id IN (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1)
          AND id NOT IN (SELECT MIN(id) FROM charges GROUP BY order_id)""").fetchall()
        for charge_id, amount in rows:
            ctx.db.execute("UPDATE charges SET status='refunded' WHERE id=?", (charge_id,))
            ctx.payments.refund(charge_id, amount, "duplicate charge")

    r = refund_duplicates.rehearse()
    assert r.status == "review" and not r.blocked and r.refunds == 104 and r.money_out_usd == 5136.0
    assert r.approval_url == f"https://demo.example/app?run={r.run_id}" and "104 refunds" in r.summary
    assert not hasattr(sd, "approve")                                   # agents can't approve
    threading.Timer(0.5, lambda: http.post(f"/api/runs/{r.run_id}/approve", json={"approver": "Human"})).start()
    assert sd.wait_for_decision(r.run_id, timeout=30, poll=0.2) == "applied"


@needs_docker
def test_sdk_reports_policy_blocks(fresh_business, monkeypatch):
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    sd = StuntDouble("https://demo.example", http=TestClient(main.app))
    r = sd.rehearse("clean up", "def run(ctx):\n    ctx.db.execute('DELETE FROM customers')\n")
    assert r.blocked and any("protected table" in b for b in r.blocked_by_policy)
