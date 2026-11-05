"""Learned rules: an AI catch, promoted by a human, becomes a deterministic check that runs on every future rehearsal.

A rule is one read-only SELECT that returns the rows that are wrong AFTER a plan ran (0 rows = fine). Rules run inside
phase 2 of the sandbox, read-only against the double's after-state: never on the host, never against production.
"""
import json
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import config, workspaces

PATH = config.DATA_DIR / "rules.json"
LOCK = threading.Lock()
MAX_RULES = 50


def _load() -> list[dict]:
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return []


def _save(rules: list[dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(rules, indent=2))


def all_rules(ws: str | None = None) -> list[dict]:
    return [r for r in _load() if ws is None or r["workspace"] == ws]


def check_sql(sql: str, ws: str) -> str:
    """A single read-only SELECT that runs on the workspace's current data (read-only, 2 s limit)."""
    s = " ".join(str(sql).split())
    if not s.lower().startswith(("select", "with")) or ";" in s.rstrip(";") or len(s) > 2000:
        raise ValueError("A rule is one read-only SELECT (no semicolons, at most 2,000 characters)")
    db = sqlite3.connect(f"file:{workspaces.db_path(ws)}?mode=ro", uri=True)
    deadline = time.time() + 2
    db.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10_000)
    try:
        db.execute("PRAGMA query_only = ON")
        hits = len(db.execute(s.rstrip(";")).fetchmany(1001))
    except sqlite3.Error as e:
        raise ValueError(f"The rule's SQL doesn't run: {e}") from e
    finally:
        db.close()
    if hits:  # a rule flags what a plan got WRONG: today's (approved) data must pass it
        raise ValueError(f"This rule would flag today's data ({hits:,}{'+' if hits > 1000 else ''} rows), so it isn't a valid check. "
                         "A rule must return 0 rows on the data as it is now.")
    return s.rstrip(";")


def add(ws: str, title: str, sql: str, source_run: str, by: str = "") -> dict:
    sql = check_sql(sql, ws)
    rule = {"id": "rule_" + uuid.uuid4().hex[:8], "workspace": ws, "title": " ".join(str(title).split())[:120] or "Learned rule",
            "sql": sql, "source_run": source_run, "by": " ".join(by.split())[:80], "created_at": time.time()}
    with LOCK:
        rules = _load()
        if any(r["workspace"] == ws and r["sql"] == sql for r in rules):
            raise ValueError("This rule already exists")
        if len(rules) >= MAX_RULES:
            raise ValueError("Rule limit reached on this demo server")
        rules.append(rule)
        _save(rules)
    return rule


def delete(rule_id: str) -> bool:
    with LOCK:
        rules = _load()
        keep = [r for r in rules if r["id"] != rule_id]
        _save(keep)
    return len(keep) != len(rules)


def reset() -> None:
    PATH.unlink(missing_ok=True)


def _q(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def check_against_good(sql: str, ws: str, good: list[tuple[str, dict]]) -> None:
    """Refuse a rule that would block a rehearsal the AI judged correct. Each good rehearsal's end state is rebuilt from
    today's data plus its recorded row changes (skipped if those rows drifted since), and the rule must return 0 rows."""
    for run_id, effects in good[:10]:
        changes = effects.get("changes") or {}
        if not changes or any(d.get("dropped") or d.get("created") for d in changes.values()):
            continue
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "after.db"
            shutil.copyfile(workspaces.db_path(ws), path)
            db = sqlite3.connect(path)
            try:
                drifted = False
                for table, ch in changes.items():
                    for item in ch.get("updated", []):
                        cols = list(item["before"].keys())
                        now = db.execute(f"SELECT {', '.join(_q(c) for c in cols)} FROM {_q(table)} WHERE rowid=?", (item["rowid"],)).fetchone()
                        if now is None or dict(zip(cols, now, strict=False)) != item["before"]:
                            drifted = True
                            break
                        if item.get("changed"):
                            db.execute(f"UPDATE {_q(table)} SET {', '.join(f'{_q(c)}=?' for c in item['changed'])} WHERE rowid=?",
                                       [item["after"][c] for c in item["changed"]] + [item["rowid"]])
                    for item in ch.get("deleted", []):
                        db.execute(f"DELETE FROM {_q(table)} WHERE rowid=?", (item["rowid"],))
                    for item in ch.get("inserted", []):
                        cols = list(item["after"].keys())
                        db.execute(f"INSERT OR REPLACE INTO {_q(table)} (rowid, {', '.join(_q(c) for c in cols)}) VALUES (?, {', '.join('?' * len(cols))})",
                                   [item["rowid"]] + [item["after"][c] for c in cols])
                    if drifted:
                        break
                if drifted:
                    continue
                db.commit()
                deadline = time.time() + 2
                db.set_progress_handler(lambda end=deadline: 1 if time.time() > end else 0, 10_000)
                hits = db.execute(sql.rstrip(";")).fetchmany(1)
            except sqlite3.Error:
                continue
            finally:
                db.close()
            if hits:
                raise ValueError(f"This rule would also block {run_id}, a rehearsal the AI judged correct, so it isn't specific enough to learn")
