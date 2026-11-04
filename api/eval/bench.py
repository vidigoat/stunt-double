"""Rehearsal latency benchmark (no AI involved): how long does a full two-phase rehearsal take?

  python eval/bench.py --runs 30                # in-process, uses the local Docker daemon
Prints p50/p95 for: the correct refund plan, a destructive plan, and an empty plan.
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, sandbox, seed  # noqa: E402

PLANS = {
    "correct refund plan (104 refunds + emails)": '''def run(ctx):
    rows = ctx.db.execute("""SELECT id, customer_id, amount_cents FROM charges WHERE created_at >= '2026-10-26' AND status='succeeded'
      AND order_id IN (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1)
      AND id NOT IN (SELECT MIN(id) FROM charges GROUP BY order_id)""").fetchall()
    for cid, cust, amt in rows:
        ctx.db.execute("UPDATE charges SET status='refunded' WHERE id=?", (cid,))
        ctx.payments.refund(cid, amt, "duplicate charge")
        ctx.email.send(ctx.db.execute("SELECT email FROM customers WHERE id=?", (cust,)).fetchone()[0], "Refunded", "Sorry!")
''',
    "destructive plan (DELETE FROM customers)": 'def run(ctx):\n    ctx.db.execute("DELETE FROM customers")\n',
    "empty plan": "def run(ctx):\n    pass\n",
}


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    a = ap.parse_args()
    seed.seed(config.PROD_DB)
    print(f"runtime={config.SANDBOX_RUNTIME or 'runc'} · {a.runs} runs each · business: 1,300 customers, 5,290 charges\n")
    print(f"{'plan':48} {'p50':>8} {'p95':>8} {'run phase p50':>14}")
    for name, code in PLANS.items():
        walls, runs = [], []
        sandbox.rehearse(code)  # warm-up
        for _ in range(a.runs):
            t0 = time.time()
            c = sandbox.rehearse(code)["consequences"]
            walls.append(time.time() - t0)
            runs.append(c["sandbox"]["run_ms"] / 1000)
        print(f"{name:48} {statistics.median(walls):7.2f}s {pct(walls, .95):7.2f}s {statistics.median(runs):13.2f}s")


if __name__ == "__main__":
    main()
