"""Apply an APPROVED rehearsal to the real business.

The agent's code is never executed against production. We replay the exact effects the
human approved (row changes, refunds, emails), after checking that every row we are about
to touch still looks exactly like it did in the rehearsal (drift check).
"""
import json
import smtplib
import sqlite3
from email.message import EmailMessage

from . import beanpay, config, connectors


class DriftError(Exception):
    def __init__(self, drifted: list[dict]):
        super().__init__(f"{len(drifted)} rows changed since the rehearsal")
        self.drifted = drifted


def q(name: str) -> str:
    """Quote an SQL identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def _schema(db: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {t: [r[1] for r in db.execute(f"PRAGMA table_info({q(t)})")] for t in tables}


def _check_identifiers(schema: dict[str, list[str]], changes: dict) -> None:
    """Every table and column we are about to touch must already exist in PRODUCTION."""
    for table, d in changes.items():
        if table not in schema:
            raise ValueError(f"Refusing to apply: table {table!r} does not exist in production")
        allowed = set(schema[table])
        for item in d["updated"] + d["deleted"] + d["inserted"]:
            row = item.get("after") or item.get("before") or {}
            bad = [c for c in list(row) + item.get("changed", []) if c not in allowed]
            if bad:
                raise ValueError(f"Refusing to apply: unknown columns {bad!r} in {table!r}")


def _row(db: sqlite3.Connection, table: str, rowid: int, cols: list[str]) -> dict | None:
    r = db.execute(f'SELECT {", ".join(q(c) for c in cols)} FROM {q(table)} WHERE rowid=?', (rowid,)).fetchone()
    return dict(zip(cols, r, strict=False)) if r else None


def drift_check(db: sqlite3.Connection, changes: dict) -> list[dict]:
    drifted = []
    for table, d in changes.items():
        for item in d["updated"] + d["deleted"]:
            cols = list(item["before"].keys())
            now = _row(db, table, item["rowid"], cols)
            if now != item["before"]:
                drifted.append({"table": table, "rowid": item["rowid"], "expected": item["before"], "found": now})
        for item in d["inserted"]:
            if _row(db, table, item["rowid"], list(item["after"].keys())) is not None:
                drifted.append({"table": table, "rowid": item["rowid"], "expected": None, "found": "row exists"})
    return drifted


def apply(run_id: str, effects_path: str, workspace: str | None = None) -> dict:
    effects = json.loads(open(effects_path).read())
    changes = effects["changes"]
    if any(d.get("dropped") or d.get("created") or d.get("schema_changed") for d in changes.values()):
        raise ValueError("Schema changes (CREATE/DROP/ALTER TABLE) are never auto-applied")

    # Every API call must be replayable through a connector, checked BEFORE anything changes.
    calls = effects.get("http", [])
    for c in calls:
        why = connectors.check(c)
        if why:
            raise ValueError(f"Refusing to apply: {why}")
    # Build every email BEFORE touching the database: a malformed header must fail while nothing has changed.
    messages = []
    for e in effects["emails"]:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = "Bean There Coffee Co. <hello@beanthere.example>", e["to"], e["subject"]
        msg.set_content(e["body"])
        messages.append(msg)

    from . import workspaces
    if (workspace or workspaces.DEMO) != workspaces.DEMO and (effects["payments"] or effects["emails"]):
        raise ValueError("Refusing to apply: payments and email are only connected for the demo business, not uploaded workspaces")
    db = sqlite3.connect(workspaces.db_path(workspace), isolation_level=None)
    if hasattr(sqlite3, "SQLITE_DBCONFIG_ENABLE_TRIGGER"):  # apply replays exactly the measured rows: no trigger writes on top
        db.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)
    db.execute("BEGIN IMMEDIATE")  # lock: nothing can change between the drift check and the write
    try:
        _check_identifiers(_schema(db), changes)
        drifted = drift_check(db, changes)
        if drifted:
            raise DriftError(drifted)
        n = 0
        for table, d in changes.items():
            for item in d["deleted"]:
                db.execute(f"DELETE FROM {q(table)} WHERE rowid=?", (item["rowid"],)); n += 1
            for item in d["updated"]:
                cols = item["changed"]
                if not cols:
                    continue
                db.execute(f'UPDATE {q(table)} SET {", ".join(f"{q(c)}=?" for c in cols)} WHERE rowid=?',
                           [item["after"][c] for c in cols] + [item["rowid"]]); n += 1
            for item in d["inserted"]:
                cols = list(item["after"].keys())
                db.execute(f'INSERT INTO {q(table)} (rowid, {", ".join(q(c) for c in cols)}) VALUES (?, {", ".join("?" * len(cols))})',
                           [item["rowid"]] + [item["after"][c] for c in cols]); n += 1
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()

    refunds = [beanpay.refund(p["charge_id"], p["amount_cents"], p.get("reason", ""), run_id, f"{run_id}:{i}")
               for i, p in enumerate(effects["payments"])]
    sent, failed = 0, 0
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            for msg in messages:
                try:
                    smtp.send_message(msg); sent += 1
                except Exception:  # noqa: BLE001
                    failed += 1
    except OSError:
        failed = len(effects["emails"])
    deliveries = [connectors.deliver(c, run_id) for c in calls]
    return {"rows_written": n, "refunds": len(refunds), "http_delivered": sum(1 for d in deliveries if d.get("ok")),
            "http_failed": sum(1 for d in deliveries if not d.get("ok")), "refund_total_cents": sum(p["amount_cents"] for p in effects["payments"]),
            "emails_sent": sent, "emails_failed": failed}
