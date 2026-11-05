"""Rebuild a rehearsal's after-state from its measured effects, on a private copy of the data.

The engine reasons about "what the data would look like" without ever running plan code again: it copies the
workspace and replays the measured row changes, exactly as approval would. If a row no longer holds the value the
rehearsal saw (someone changed it since), the replay stops: the engine never reasons about a world that isn't there.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path


class Drift(Exception):
    """A row changed since the rehearsal; reasoning about this copy would be reasoning about fiction."""


def _q(ident: str) -> str:
    return '"' + str(ident).replace('"', '""') + '"'


def materialize(base_db: str | Path, effects: dict, dest: str | Path) -> Path:
    """Copy `base_db` to `dest` and apply the effects' row changes. Raises Drift if any row moved since the rehearsal."""
    dest = Path(dest)
    shutil.copyfile(base_db, dest)
    db = sqlite3.connect(dest, isolation_level=None)
    try:
        db.execute("PRAGMA foreign_keys = OFF")
        if hasattr(sqlite3, "SQLITE_DBCONFIG_ENABLE_TRIGGER"):
            db.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)
        db.execute("BEGIN")
        for table, ch in (effects.get("changes") or {}).items():
            if ch.get("dropped") or ch.get("created") or ch.get("schema_changed"):
                raise Drift(f"{table}: schema change, not replayable")
            t = _q(table)
            for item in ch.get("updated", []):
                cols = list(item["before"].keys())
                now = db.execute(f"SELECT {', '.join(_q(c) for c in cols)} FROM {t} WHERE rowid = ?", (item["rowid"],)).fetchone()
                if now is None or dict(zip(cols, now, strict=False)) != item["before"]:
                    raise Drift(f"{table} row {item['rowid']} changed since the rehearsal")
                if item.get("changed"):
                    db.execute(f"UPDATE {t} SET {', '.join(f'{_q(c)} = ?' for c in item['changed'])} WHERE rowid = ?",
                               [item["after"][c] for c in item["changed"]] + [item["rowid"]])
            for item in ch.get("deleted", []):
                if db.execute(f"DELETE FROM {t} WHERE rowid = ?", (item["rowid"],)).rowcount != 1:
                    raise Drift(f"{table} row {item['rowid']} is already gone")
            for item in ch.get("inserted", []):
                cols = list(item["after"].keys())
                try:
                    db.execute(f"INSERT INTO {t} (rowid, {', '.join(_q(c) for c in cols)}) VALUES (?, {', '.join('?' * len(cols))})",
                               [item["rowid"]] + [item["after"][c] for c in cols])
                except sqlite3.IntegrityError as e:
                    raise Drift(f"{table} row {item['rowid']} can't be inserted: {e}") from e
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        db.close()
        dest.unlink(missing_ok=True)
        raise
    db.close()
    return dest
