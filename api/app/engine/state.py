"""One read-only view of a plan's world, for every check the engine runs.

    main.*      the database AFTER the plan (rebuilt from its measured effects)
    before.*    the same database BEFORE the plan, untouched
    sent.*      what the plan did outside the database: refunds, emails, API requests

A check written against this view can say what a person means: "every order that WAS double-charged now has its
extra charge refunded, and its customer got exactly one email". Each part of the view is opened read-only.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SENT_SCHEMA = (
    "sent.refunds(charge_id INTEGER, amount_cents INTEGER, reason TEXT)",
    "sent.emails(recipient TEXT, subject TEXT, body TEXT, kind TEXT)",
    "sent.requests(method TEXT, url TEXT, body TEXT)",
)


def open_view(after: str | Path, before: str | Path | None = None, effects: dict | None = None) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{after}?mode=ro", uri=True, check_same_thread=False)
    db.execute("ATTACH DATABASE ? AS before", (f"file:{before or after}?mode=ro",))
    db.execute("ATTACH DATABASE ':memory:' AS sent")
    db.execute("CREATE TABLE sent.refunds (charge_id INTEGER, amount_cents INTEGER, reason TEXT)")
    db.execute("CREATE TABLE sent.emails (recipient TEXT, subject TEXT, body TEXT, kind TEXT)")
    db.execute("CREATE TABLE sent.requests (method TEXT, url TEXT, body TEXT)")
    e = effects or {}
    db.executemany("INSERT INTO sent.refunds VALUES (?, ?, ?)",
                   [(p.get("charge_id"), p.get("amount_cents"), p.get("reason")) for p in e.get("payments") or [] if isinstance(p, dict)])
    db.executemany("INSERT INTO sent.emails VALUES (?, ?, ?, ?)",
                   [(m.get("to"), m.get("subject"), m.get("body"), m.get("kind")) for m in e.get("emails") or [] if isinstance(m, dict)])
    db.executemany("INSERT INTO sent.requests VALUES (?, ?, ?)",
                   [(c.get("method"), c.get("url"), json.dumps(c.get("json"), default=str)) for c in e.get("http") or [] if isinstance(c, dict)])
    db.execute("PRAGMA query_only = ON")
    return db


def run_check(view: sqlite3.Connection, sql: str, cap: int, seconds: float = 5) -> tuple[list[str], list[tuple], bool]:
    """Run one read-only SELECT with a deadline. Returns (columns, up to `cap` rows, whether there were more)."""
    deadline = time.time() + seconds
    view.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10_000)
    cur = view.execute(sql.strip().rstrip(";"))
    cols = [c[0] for c in cur.description or []]
    rows = cur.fetchmany(cap + 1)
    return cols, rows[:cap], len(rows) > cap
