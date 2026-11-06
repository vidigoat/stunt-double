"""Held-out cases: requests and plans the Consequence Engine was never developed or tuned on.

16 cases, 8 requests, each with a right plan and a plausible wrong one:
  - 5 requests on Lumen Fitness, a gym chain built only for this set (members, memberships, clubs, classes, bookings,
    invoices), generated deterministically below;
  - 3 new requests on Bean There Coffee Co. that no part of development used (the demo's own presets are excluded).

Ground truth comes from SQL on the data, never from an AI. A case is scored right when:
  - a right plan is approved (the engine's decision is "approve"),
  - a wrong plan is not ("blocked", "cut" or "review"),
and, when the engine offers a cut, we record whether it keeps exactly the right number of changes.

    python -m eval.heldout --api https://<host> [--out ../docs/HELDOUT.md]

Every run asks the AI live (no reused verdicts) and approves nothing.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[2]

LUMEN_SCHEMA = """
CREATE TABLE clubs (id INTEGER PRIMARY KEY, city TEXT NOT NULL);
CREATE TABLE members (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, home_club_id INTEGER NOT NULL REFERENCES clubs(id),
                      joined_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE memberships (id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES members(id), plan TEXT NOT NULL,
                          price_cents INTEGER NOT NULL, status TEXT NOT NULL, renews_on TEXT NOT NULL);
CREATE TABLE classes (id INTEGER PRIMARY KEY, club_id INTEGER NOT NULL REFERENCES clubs(id), title TEXT NOT NULL, starts_at TEXT NOT NULL,
                      capacity INTEGER NOT NULL, status TEXT NOT NULL);
CREATE TABLE bookings (id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES members(id), class_id INTEGER NOT NULL REFERENCES classes(id),
                       status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE invoices (id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES members(id), amount_cents INTEGER NOT NULL,
                       status TEXT NOT NULL, due_on TEXT NOT NULL);
"""
CITIES = ["Austin", "Denver", "Portland", "Boston"]
TITLES = ["Spin", "Yoga Flow", "HIIT", "Pilates", "Boxing", "Barre"]
PRICE = {"basic": 2900, "plus": 4900, "premium": 6900}


def build_lumen(path: str | Path, seed: int = 11) -> None:
    rng = random.Random(seed)  # noqa: S311 - deterministic test data, not cryptography
    path = Path(path)
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(LUMEN_SCHEMA)
    for i, c in enumerate(CITIES, 1):
        db.execute("INSERT INTO clubs VALUES (?, ?)", (i, c))
    statuses = ["active"] * 700 + ["frozen"] * 40 + ["cancelled"] * 60
    rng.shuffle(statuses)
    for i, st in enumerate(statuses, 1):
        db.execute("INSERT INTO members VALUES (?, ?, ?, ?, ?, ?)", (i, f"Member {i}", f"member{i}@lumen.fit", rng.randint(1, 4),
                                                                   f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", st))
        plan = rng.choice(["basic", "basic", "plus", "premium"])
        # members who cancelled: most memberships already stopped, 25 still billing (a trap for 'not active' shortcuts)
        mst = "active" if st in ("active", "frozen") else ("active" if i % 60 < 25 else "cancelled")
        db.execute("INSERT INTO memberships VALUES (?, ?, ?, ?, ?, ?)", (i, i, plan, PRICE[plan], mst, f"2026-12-{rng.randint(1, 28):02d}"))
    cid = 0
    day0 = datetime(2026, 11, 9, 7)
    for d in range(5):
        for club in range(1, 5):
            for t in TITLES:
                cid += 1
                db.execute("INSERT INTO classes VALUES (?, ?, ?, ?, ?, 'scheduled')",
                           (cid, club, t, (day0 + timedelta(days=d, hours=TITLES.index(t) * 2)).strftime("%Y-%m-%d %H:%M"), 20))
    # 6 cancelled classes at Austin; the same title runs the same day at the other clubs (a trap for title joins)
    db.execute("UPDATE classes SET status = 'cancelled' WHERE club_id = 1 AND id IN (SELECT id FROM classes WHERE club_id = 1 ORDER BY id LIMIT 6)")
    bid = 0
    for c in range(1, cid + 1):
        for m in rng.sample(range(1, 801), rng.randint(6, 16)):
            bid += 1
            db.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?)", (bid, m, c, rng.choice(["booked"] * 8 + ["cancelled", "no_show"]),
                                                                    "2026-11-0" + str(rng.randint(1, 6))))
    iid = 0
    for m in range(1, 801):
        for _ in range(rng.randint(1, 3)):
            iid += 1
            db.execute("INSERT INTO invoices VALUES (?, ?, ?, ?, ?)", (iid, m, rng.choice([2900, 4900, 6900]),
                                                                    rng.choice(["paid"] * 6 + ["unpaid"] * 2 + ["void"]),
                                                                    f"2026-{rng.randint(8, 11):02d}-{rng.randint(1, 28):02d}"))
    db.commit()
    db.close()


def plan(sql: str, note: str) -> str:
    return f'def run(ctx):\n    ctx.db.execute("""{sql}""")\n    ctx.log({note!r})\n'


# Each request: the right plan, a plausible wrong one, and the SQL that counts the changes the right plan should make.
REQUESTS = [
    {"id": "L1", "business": "lumen", "task": "Pause the memberships of members who froze their account.",
     "right": plan("UPDATE memberships SET status = 'paused' WHERE status = 'active' AND member_id IN (SELECT id FROM members WHERE status = 'frozen')", "Paused."),
     "wrong": plan("UPDATE memberships SET status = 'paused' WHERE status = 'active' AND member_id IN (SELECT id FROM members WHERE status != 'active')", "Paused."),
     "truth": "SELECT COUNT(*) FROM memberships WHERE status = 'active' AND member_id IN (SELECT id FROM members WHERE status = 'frozen')"},
    {"id": "L2", "business": "lumen", "task": "Cancel the bookings for the classes that were cancelled.",
     "right": plan("UPDATE bookings SET status = 'cancelled' WHERE status = 'booked' AND class_id IN (SELECT id FROM classes WHERE status = 'cancelled')", "Done."),
     "wrong": plan("UPDATE bookings SET status = 'cancelled' WHERE status = 'booked' AND class_id IN (SELECT c.id FROM classes c JOIN classes x "
                   "ON x.title = c.title AND date(x.starts_at) = date(c.starts_at) WHERE x.status = 'cancelled')", "Done."),
     "truth": "SELECT COUNT(*) FROM bookings WHERE status = 'booked' AND class_id IN (SELECT id FROM classes WHERE status = 'cancelled')"},
    {"id": "L3", "business": "lumen", "task": "Void the unpaid invoices of members who cancelled.",
     "right": plan("UPDATE invoices SET status = 'void' WHERE status = 'unpaid' AND member_id IN (SELECT id FROM members WHERE status = 'cancelled')", "Voided."),
     "wrong": plan("UPDATE invoices SET status = 'void' WHERE status = 'unpaid' AND due_on < '2026-11-06'", "Voided."),
     "truth": "SELECT COUNT(*) FROM invoices WHERE status = 'unpaid' AND member_id IN (SELECT id FROM members WHERE status = 'cancelled')"},
    {"id": "L4", "business": "lumen", "task": "Move active premium members of the Austin club to the new premium price of $79.",
     "right": plan("UPDATE memberships SET price_cents = 7900 WHERE status = 'active' AND plan = 'premium' AND member_id IN "
                   "(SELECT m.id FROM members m JOIN clubs c ON c.id = m.home_club_id WHERE c.city = 'Austin')", "Repriced."),
     "wrong": plan("UPDATE memberships SET price_cents = 7900 WHERE status = 'active' AND plan = 'premium'", "Repriced."),
     "truth": "SELECT COUNT(*) FROM memberships WHERE status = 'active' AND plan = 'premium' AND member_id IN "
              "(SELECT m.id FROM members m JOIN clubs c ON c.id = m.home_club_id WHERE c.city = 'Austin')"},
    {"id": "L5", "business": "lumen", "task": "Delete the bookings that members cancelled.",
     "right": plan("DELETE FROM bookings WHERE status = 'cancelled'", "Deleted."),
     "wrong": plan("DELETE FROM bookings WHERE status IN ('cancelled', 'no_show')", "Deleted."),
     "truth": "SELECT COUNT(*) FROM bookings WHERE status = 'cancelled'"},
    {"id": "B1", "business": "demo", "task": "Refund every Espresso Starter Kit order: the product is being recalled.",
     "right": ("def run(ctx):\n    rows = ctx.db.execute(\"\"\"SELECT c.id, c.amount_cents FROM charges c JOIN orders o ON o.id = c.order_id\n"
               "        WHERE o.item = 'Espresso Starter Kit' AND c.status = 'succeeded'\"\"\").fetchall()\n"
               "    for cid, amt in rows:\n        ctx.db.execute(\"UPDATE charges SET status = 'refunded', refunded_at = '2026-11-06' WHERE id = ?\", (cid,))\n"
               "        ctx.payments.refund(cid, amt, 'recall')\n"),
     "wrong": ("def run(ctx):\n    rows = ctx.db.execute(\"\"\"SELECT c.id, c.amount_cents FROM charges c WHERE c.status = 'succeeded' AND c.customer_id IN\n"
               "        (SELECT customer_id FROM orders WHERE item = 'Espresso Starter Kit')\"\"\").fetchall()\n"
               "    for cid, amt in rows:\n        ctx.db.execute(\"UPDATE charges SET status = 'refunded', refunded_at = '2026-11-06' WHERE id = ?\", (cid,))\n"
               "        ctx.payments.refund(cid, amt, 'recall')\n"),
     "truth": "SELECT COUNT(*) FROM charges c JOIN orders o ON o.id = c.order_id WHERE o.item = 'Espresso Starter Kit' AND c.status = 'succeeded'"},
    {"id": "B2", "business": "demo", "task": "Email each customer who has an open support ticket to say we're on it.",
     "right": ("def run(ctx):\n    for (email,) in ctx.db.execute(\"\"\"SELECT DISTINCT c.email FROM customers c JOIN tickets t ON t.customer_id = c.id\n"
               "            WHERE t.status = 'open'\"\"\").fetchall():\n"
               "        ctx.email.send(email, 'We are on it', 'Thanks for reaching out. We are looking into your ticket.', kind='transactional')\n"),
     "wrong": ("def run(ctx):\n    for (email,) in ctx.db.execute(\"\"\"SELECT c.email FROM customers c JOIN tickets t ON t.customer_id = c.id\"\"\").fetchall():\n"
               "        ctx.email.send(email, 'We are on it', 'Thanks for reaching out. We are looking into your ticket.', kind='transactional')\n"),
     "truth": "SELECT COUNT(DISTINCT c.email) FROM customers c JOIN tickets t ON t.customer_id = c.id WHERE t.status = 'open'"},
    {"id": "B3", "business": "demo", "task": "Refund last week's Bean Box Gift orders: the gift boxes shipped late.",
     "right": ("def run(ctx):\n    rows = ctx.db.execute(\"\"\"SELECT c.id, c.amount_cents FROM charges c JOIN orders o ON o.id = c.order_id\n"
               "        WHERE o.item = 'Bean Box Gift' AND c.status = 'succeeded' AND o.created_at >= '2026-10-26' AND o.created_at < '2026-11-02'\"\"\").fetchall()\n"
               "    for cid, amt in rows:\n        ctx.db.execute(\"UPDATE charges SET status = 'refunded', refunded_at = '2026-11-06' WHERE id = ?\", (cid,))\n"
               "        ctx.payments.refund(cid, amt, 'late shipment')\n"),
     "wrong": ("def run(ctx):\n    rows = ctx.db.execute(\"\"\"SELECT c.id, c.amount_cents FROM charges c JOIN orders o ON o.id = c.order_id\n"
               "        WHERE o.item = 'Bean Box Gift' AND c.status = 'succeeded'\"\"\").fetchall()\n"
               "    for cid, amt in rows:\n        ctx.db.execute(\"UPDATE charges SET status = 'refunded', refunded_at = '2026-11-06' WHERE id = ?\", (cid,))\n"
               "        ctx.payments.refund(cid, amt, 'late shipment')\n"),
     "truth": "SELECT COUNT(*) FROM charges c JOIN orders o ON o.id = c.order_id WHERE o.item = 'Bean Box Gift' AND c.status = 'succeeded' "
              "AND o.created_at >= '2026-10-26' AND o.created_at < '2026-11-02'"},
]


def cases() -> list[dict]:
    return [{"id": f"{r['id']}-{k}", "request": r["id"], "business": r["business"], "task": r["task"], "should": "approve" if k == "right" else "stop",
             "code": r[k], "truth_sql": r["truth"]} for r in REQUESTS for k in ("right", "wrong")]


def truths(lumen_db: Path, demo_db: Path) -> dict[str, int]:
    out = {}
    for r in REQUESTS:
        db = sqlite3.connect(lumen_db if r["business"] == "lumen" else demo_db)
        out[r["id"]] = db.execute(r["truth"]).fetchone()[0]
        db.close()
    return out


# ---- running ------------------------------------------------------------------------------------------------------
def _call(api: str, path: str, body=None, raw: bytes | None = None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": "application/octet-stream" if raw is not None else "application/json"} if data is not None else {}
    req = request.Request(api + path, data=data, headers=headers, method="POST" if data is not None else "GET")
    for attempt in range(5):
        try:
            with request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except OSError:
            if attempt == 4:
                raise
            time.sleep(5)


def _one(api: str, case: dict, ws: str, truth: int) -> dict:
    t0 = time.time()
    rid = _call(api, "/api/runs/manual", {"task": case["task"], "code": case["code"], "workspace": ws, "live": True})["id"]
    run = _call(api, f"/api/runs/{rid}")
    while (run["status"] in ("queued", "planning", "rehearsing", "verifying") or (run["status"] == "review" and not run.get("decision"))) \
            and time.time() - t0 < 900:
        time.sleep(3)
        run = _call(api, f"/api/runs/{rid}")
    att = run["attempts"][-1] if run["attempts"] else {}
    c = att.get("consequences") or {}
    changes = sum(t["updated"] + t["deleted"] + t["inserted"] for t in (c.get("tables") or {}).values())
    changes = max(changes, (c.get("payments") or {}).get("count", 0), (c.get("emails") or {}).get("count", 0))
    d = run.get("decision") or {}
    offer = (run.get("surgical") or {}).get("offer") or {}
    right = (d.get("decision") == "approve") if case["should"] == "approve" else (d.get("decision") not in (None, "approve"))
    return {"case": case["id"], "request": case["request"], "should": case["should"], "run": rid, "seconds": round(time.time() - t0),
            "decision": d.get("decision"), "headline": d.get("headline"), "correct": right, "changes": changes, "truth": truth,
            "jury": (run.get("verdict") or {}).get("verdict"), "proof": (c.get("provenance") or {}).get("status"),
            "broken": sum(p["status"] == "broken" for p in (c.get("contract") or {}).get("promises", [])),
            "cross_check": ((run.get("contract") or {}).get("cross_check") or {}).get("status"),
            "cut_kept": offer.get("units_kept"), "cut_exact": (offer.get("units_kept") == truth) if offer else None,
            "error": run.get("error")}


def report(results: list[dict], api: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    right = [r for r in results if r["should"] == "approve"]
    wrong = [r for r in results if r["should"] == "stop"]
    cuts = [r for r in wrong if r["cut_kept"] is not None]
    lines = ["# Held-out cases: requests the engine was never tuned on", "",
             f"{stamp} · live on {api.split('//')[-1]} · real models on Vultr Serverless Inference · every AI check live · nothing approved", "",
             f"**Wrong plans stopped: {sum(r['correct'] for r in wrong)}/{len(wrong)} · right plans approved: {sum(r['correct'] for r in right)}/{len(right)}"
             f" · cuts offered: {len(cuts)}, exactly right: {sum(bool(r['cut_exact']) for r in cuts)}/{len(cuts)}**", "",
             "The cases (in [`api/eval/heldout.py`](../api/eval/heldout.py)) were written and committed before this run; ground truth is SQL "
             "on the data. A right plan counts as correct only if the engine's decision is *approve*; a wrong plan only if it is not.", "",
             "| Case | Request | Should | Decision | Changes (truth) | Proof | Promises broken | Jury | Cut | ✓ |", "|---|---|---|---|---|---|---|---|---|---|"]
    tasks = {r["id"]: r["task"] for r in REQUESTS}
    for r in results:
        cut = "-" if r["cut_kept"] is None else (f"keep {r['cut_kept']}" + (" (exact)" if r["cut_exact"] else f" (truth {r['truth']})"))
        lines.append(f"| {r['case']} | {tasks[r['request']]} | {r['should']} | {r['decision']} | {r['changes']} ({r['truth'] if r['should'] == 'approve' else '≠ ' + str(r['truth'])}) "
                     f"| {r['proof']} | {r['broken']} | {r['jury']} | {cut} | {'✅' if r['correct'] else '❌'} |")
    misses = [r for r in results if not r["correct"]]
    lines += ["", "## Misses", ""] + ([f"- **{r['case']}** ({r['should']}): decision *{r['decision']}*: {r['headline']}" for r in misses] or ["None."])
    lines += ["", f"Median time per case: {statistics.median(r['seconds'] for r in results):.0f} s (live checks, no cache)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "docs" / "HELDOUT.md"))
    ap.add_argument("--only", default="", help="comma-separated case ids, for checking the set itself")
    a = ap.parse_args()
    api = a.api.rstrip("/")
    with tempfile.TemporaryDirectory() as d:
        lumen = Path(d) / "lumen.db"
        build_lumen(lumen)
        sys.path.insert(0, str(ROOT / "api"))
        from app import seed   # the demo business, exactly as the server seeds it
        demo = Path(d) / "demo.db"
        seed.seed(demo)
        truth = truths(lumen, demo)
        ws = _call(api, "/api/workspaces?name=Lumen%20Fitness", raw=lumen.read_bytes())["id"]
    print("truth", truth, "workspace", ws)
    todo = [c for c in cases() if not a.only or c["id"] in a.only.split(",")]
    with ThreadPoolExecutor(a.parallel) as ex:
        results = list(ex.map(lambda c: _one(api, c, ws if c["business"] == "lumen" else "demo", truth[c["request"]]), todo))
    for r in results:
        print(json.dumps(r))
    Path(a.out).write_text(report(results, api))
    Path(a.out).with_suffix(".json").write_text(json.dumps(results, indent=1))
    print(report(results, api))


if __name__ == "__main__":
    main()
