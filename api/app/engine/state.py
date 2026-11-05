"""One read-only view of a plan's world, for every check the engine runs.

    main.*      the database AFTER the plan (rebuilt from its measured effects)
    before.*    the same database BEFORE the plan, untouched
    sent.*      what the plan did outside the database: refunds, emails, API requests

A check written against this view can say what a person means: "every order that WAS double-charged now has its
extra charge refunded, and its customer got exactly one email". Each part of the view is opened read-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

_CACHE = Path(tempfile.gettempdir()) / "sd-engine"
_LOCK = threading.Lock()

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


def _q(ident: str) -> str:
    return '"' + str(ident).replace('"', '""') + '"'


def indexed(base_db: str | Path) -> Path:
    """A private, indexed copy of the data, made once per version of it (path, size, modification time).

    Checks written by a model join tables on ids and filter on dates; on the raw data each one scans, and on a small
    VM four of them took 40 s. Indexing every *_id, *_at and email column of our own copy made them about 100x
    faster. The copy is never written to after it is made, and the real data is never touched."""
    src = Path(base_db)
    st = src.stat()
    wal = Path(f"{src}-wal")
    ws = wal.stat() if wal.exists() else None
    key = hashlib.sha256(f"{src.resolve()}|{st.st_size}|{st.st_mtime_ns}|{ws and (ws.st_size, ws.st_mtime_ns)}".encode()).hexdigest()[:24]
    dest = _CACHE / f"{key}.db"
    if dest.exists():
        return dest
    with _LOCK:
        if dest.exists():
            return dest
        _CACHE.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE / f".{key}.{os.getpid()}.tmp"
        with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as s_db, sqlite3.connect(tmp) as t_db:
            s_db.backup(t_db)                            # a consistent copy, whatever the journal mode
        s_db.close()
        t_db.close()
        db = sqlite3.connect(tmp)
        try:
            for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                for col in [r[1] for r in db.execute(f"PRAGMA table_info({_q(t)})")]:
                    c = str(col).lower()
                    if c.endswith(("_id", "_at")) or c == "email":
                        db.execute(f"CREATE INDEX IF NOT EXISTS {_q(f'sd_{t}_{col}')} ON {_q(t)}({_q(col)})")
            db.commit()
        finally:
            db.close()
        for old in _CACHE.glob("*.db"):                  # keep the cache small: one copy per data file is plenty
            if old.name != dest.name and old.stat().st_mtime < time.time() - 3600:
                old.unlink(missing_ok=True)
        os.replace(tmp, dest)
    return dest
