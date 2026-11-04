"""BeanPay: the (self-hosted) payments provider Bean There Coffee Co. uses.

Only the APPLY step talks to BeanPay. Rehearsals get a recorder instead and can never reach it.
"""
import sqlite3
import uuid
from datetime import datetime, UTC

from . import config

SCHEMA = """CREATE TABLE IF NOT EXISTS refunds (id TEXT PRIMARY KEY, charge_id INTEGER NOT NULL,
  amount_cents INTEGER NOT NULL, reason TEXT, run_id TEXT, idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL)"""


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(config.BEANPAY_DB)
    db.execute(SCHEMA)
    return db


def refund(charge_id: int, amount_cents: int, reason: str, run_id: str, idempotency_key: str) -> dict:
    db = _db()
    with db:
        row = db.execute("SELECT id FROM refunds WHERE idempotency_key=? OR charge_id=?", (idempotency_key, charge_id)).fetchone()
        if row:  # one refund per charge, across every run
            return {"id": row[0], "status": "duplicate_ignored"}
        rid = "re_" + uuid.uuid4().hex[:14]
        db.execute("INSERT INTO refunds VALUES (?,?,?,?,?,?,?)", (rid, charge_id, amount_cents, reason, run_id,
                   idempotency_key, datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")))
    return {"id": rid, "status": "succeeded"}


def refunded_charges(charge_ids: list[int]) -> list[int]:
    """Charges that already have a refund in the ledger (from ANY run)."""
    if not charge_ids:
        return []
    db = _db()
    found = set()
    ids = list(dict.fromkeys(int(c) for c in charge_ids))
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        found |= {r[0] for r in db.execute(f"SELECT DISTINCT charge_id FROM refunds WHERE charge_id IN ({','.join('?' * len(chunk))})", chunk)}  # noqa: S608
    return sorted(found)


def ledger(limit: int = 200) -> dict:
    db = _db()
    rows = db.execute("SELECT id, charge_id, amount_cents, reason, run_id, created_at FROM refunds ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    total = db.execute("SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM refunds").fetchone()
    return {"count": total[0], "total_cents": total[1],
            "refunds": [dict(zip(["id", "charge_id", "amount_cents", "reason", "run_id", "created_at"], r, strict=False)) for r in rows]}


def reset() -> None:
    config.BEANPAY_DB.unlink(missing_ok=True)
