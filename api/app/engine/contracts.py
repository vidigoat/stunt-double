"""Intent Contracts: what the request means, written down before any plan exists.

From the person's request, the business glossary and the schema (and nothing else: never the plan), a model on Vultr
Serverless Inference writes 2-4 promises any correct plan must keep. Each is a plain sentence a manager can read, and
one read-only SQL query over the engine's view of the world (engine/state.py) that returns the rows breaking it.

Run on today's data, each promise sorts itself:

    guard        0 rows today: must still be 0 after the plan ("no other charge is touched")
    obligation   rows today: the work to be done, which must be 0 after ("104 extra charges still to refund")

The contract is written before the plan, so nothing the plan does can bend it, and checking it needs no AI at all.
A promise that would fail a plan the jury already judged correct for the same request is withdrawn, never enforced.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from . import state
from .materialize import Drift, materialize

MAX_PROMISES = 4
_LOCK = threading.Lock()

TOOL = {"type": "function", "function": {
    "name": "contract", "description": "The promises any correct plan for this request must keep",
    "parameters": {"type": "object", "properties": {"promises": {"type": "array", "items": {"type": "object", "properties": {
        "text": {"type": "string", "description": "One plain sentence a non-technical approver understands. No SQL words."},
        "sql": {"type": "string", "description": "ONE SQLite SELECT returning the rows that break the promise (0 rows when kept)."},
    }, "required": ["text", "sql"]}}}, "required": ["promises"]}}}

PROMPT = """A person asked an AI agent to do this:

    "{task}"

Today is {today}. Before ANY plan exists, write 2-{n} promises that every correct plan for this request must keep.
You will never see the plan: write what the person meant, using the business's own definitions.

Business glossary:
{glossary}

The data (table: columns · row count):
{schema}

How each promise is checked, after the plan runs:
- the plain tables (charges, customers, ...) are the database AFTER the plan;
- before.<table> is the same table BEFORE the plan, untouched (so before.charges is the charges table as it is now);
- sent.refunds, sent.emails and sent.requests hold what the plan did outside the database (empty before it runs).

Rules for each promise:
- "text": one plain sentence a manager can read. Name the business concept, not the SQL.
- "sql": ONE SQLite SELECT returning the rows that BREAK the promise (0 rows when kept). Read-only, no hard-coded ids.
- Decide WHICH rows the request is about from before.<table>, using the glossary exactly. The plan is expected to
  change some columns (a status, a timestamp), so a definition read from the after-state stops matching the very rows
  the plan fixed. Then check what happened to those rows in the plain tables or in sent.*, joined by id.
- Write every date as a literal ('2026-01-31'), worked out from today's date. Never use 'now'.
- Write one promise that limits the change to exactly what was asked (no row outside it is touched), and, if the
  request asks for work to be done, one promise that is broken until that work is done.
Call the contract tool."""


@dataclass
class Promise:
    text: str
    sql: str
    kind: str          # "guard" | "obligation"
    today: int         # rows returned on today's data

    def public(self) -> dict:
        return dict(self.__dict__)


def _single_select(sql: str) -> str:
    s = " ".join(str(sql).split()).rstrip(";").strip()
    if not s.lower().startswith(("select", "with")) or ";" in s or len(s) > 4000:
        raise ValueError("not one read-only SELECT")
    if re.search(r"'\s*now\s*'|current_(date|time)", s, re.I):
        raise ValueError("depends on the clock: a promise must mean the same thing tomorrow")
    return s


def _count(view: sqlite3.Connection, sql: str, cap: int = 100_000) -> int:
    return len(state.run_check(view, sql, cap, seconds=3)[1])


def schema_text(db_path: str | Path) -> tuple[str, str]:
    """A compact schema for the prompt, and its signature (so a changed schema means a fresh contract)."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        lines = []
        for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            qt = '"' + t.replace('"', '""') + '"'
            cols = ", ".join(f"{r[1]} {r[2]}".strip() for r in db.execute(f"PRAGMA table_info({qt})"))
            lines.append(f"{t}({cols}) · {db.execute(f'SELECT COUNT(*) FROM {qt}').fetchone()[0]:,} rows")
    finally:
        db.close()
    sig = hashlib.sha256(re.sub(r"· [\d,]+ rows", "", "\n".join(lines)).encode()).hexdigest()
    return "\n".join(lines + list(state.SENT_SCHEMA)), sig


def classify(raw: list[dict], db_path: str | Path) -> list[Promise]:
    """Keep only promises that are one valid SELECT running on today's data, sorted into guards and obligations."""
    out = []
    view = state.open_view(db_path)
    try:
        for p in raw[:MAX_PROMISES * 2]:
            if not isinstance(p, dict) or not str(p.get("text", "")).strip():
                continue
            try:
                sql = _single_select(p.get("sql", ""))
                today = _count(view, sql)
            except (ValueError, sqlite3.Error):
                continue
            out.append(Promise(" ".join(str(p["text"]).split())[:240], sql, "obligation" if today else "guard", today))
            if len(out) >= MAX_PROMISES:
                break
    finally:
        view.close()
    return out


def _parse(message) -> list[dict]:
    """The promises from a tool call, or (some models answer in prose) from the first JSON object in the content."""
    if message.tool_calls:
        return json.loads(message.tool_calls[0].function.arguments).get("promises") or []
    m = re.search(r"\{.*\}", message.content or "", re.S)
    return (json.loads(m.group(0)).get("promises") or []) if m else []


def _cache_path(data_dir: Path) -> Path:
    return data_dir / "contract-cache.json"


def compile_contract(task: str, glossary: list[dict], db_path: str | Path, models: list[str], client, data_dir: Path,
                     today: str | None = None) -> dict:
    """The contract for a request: from the cache when the request, glossary, schema, models and date are identical."""
    schema, sig = schema_text(db_path)
    gloss = "\n".join(f"- {g.get('term')}: {g.get('definition')}" for g in glossary) or "- (none)"
    today = today or datetime.now(UTC).strftime("%A %Y-%m-%d")
    key = hashlib.sha256(json.dumps([task.strip(), gloss, sig, models, today, PROMPT]).encode()).hexdigest()
    cache = _cache_path(data_dir)
    with _LOCK:
        try:
            hit = json.loads(cache.read_text()).get(key)
        except (OSError, ValueError):
            hit = None
    if hit:
        promises = classify(hit["raw"], db_path)        # re-sorted on today's data: obligations shrink as work is done
        return {"promises": [p.public() for p in promises], "model": hit["model"], "today": today,
                "cached": {"at": hit["at"], "ms": hit.get("ms")}, "key": key[:16]}
    prompt = PROMPT.format(task=task.replace('"', "'"), today=today, n=MAX_PROMISES, glossary=gloss, schema=schema)
    last_err = "no model answered"
    for model in models:
        t0 = time.time()
        try:
            r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], tools=[TOOL],
                                               tool_choice="required", max_tokens=16000, timeout=150)
            raw = _parse(r.choices[0].message)
        except Exception as e:  # noqa: BLE001 - try the next model
            last_err = f"{model}: {type(e).__name__}"
            continue
        promises = classify(raw, db_path)
        if not promises:
            last_err = f"{model} wrote no valid promises"
            continue
        ms = int((time.time() - t0) * 1000)
        with _LOCK:
            try:
                data = json.loads(cache.read_text())
            except (OSError, ValueError):
                data = {}
            data[key] = {"raw": [{"text": p.text, "sql": p.sql} for p in promises], "model": model, "at": time.time(), "ms": ms}
            data = dict(sorted(data.items(), key=lambda kv: kv[1]["at"])[-200:])
            cache.write_text(json.dumps(data))
        return {"promises": [p.public() for p in promises], "model": model, "today": today, "ms": ms, "key": key[:16]}
    raise RuntimeError(last_err)


def evaluate(promises: list[dict], base_db: str | Path, effects: dict) -> list[dict]:
    """Check each promise against the plan's after-state, rebuilt from its measured effects. No AI."""
    with tempfile.TemporaryDirectory() as d:
        try:
            after = materialize(base_db, effects, Path(d) / "after.db")
        except Drift as e:
            return [{**p, "status": "unknown", "after": None, "why": str(e)} for p in promises]
        view = state.open_view(after, base_db, effects)
        out = []
        try:
            for p in promises:
                try:
                    n = _count(view, p["sql"])
                except sqlite3.Error as e:
                    out.append({**p, "status": "unknown", "after": None, "why": str(e)[:200]})
                    continue
                if p["kind"] == "guard":
                    status = "kept" if n == 0 else "broken"
                else:
                    status = "met" if n == 0 else "unmet"
                out.append({**p, "after": n, "status": status})
        finally:
            view.close()
        return out


def withdraw_unfair(promises: list[dict], base_db: str | Path, good: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split promises into (enforced, withdrawn): a promise a known-correct plan for this same request fails is the
    contract's mistake, not the plan's. `good` holds the effects of rehearsals the jury judged correct."""
    bad: set[int] = set()
    for effects in good[:5]:
        for i, r in enumerate(evaluate(promises, base_db, effects)):
            if r["status"] in ("broken", "unmet"):
                bad.add(i)
    return [p for i, p in enumerate(promises) if i not in bad], [p for i, p in enumerate(promises) if i in bad]
