"""Surgical approval: cut the wrong units of work out of a plan and keep the right ones.

Given a rehearsal's effects, its Effect Graph and the checks that flag what is wrong (learned rules, intent-contract
promises, the AI jury's own check), the engine:

    1. rebuilds the plan's after-state on a private copy (no plan code runs again)
    2. runs every check there and maps each flagged row to a node of the graph
    3. drops every unit of work that contains a flagged node, whole (a refund never leaves without its email)
    4. rebuilds the after-state of what is left and runs every check again: each must now find nothing

A required check (a learned rule, a broken promise) must hold on what is left, whatever happens; if it doesn't, there
is no offer. The engine never guesses.
The subset that survives is then re-measured in a fresh sandbox by the caller, like any rehearsal.
"""
from __future__ import annotations

import re
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import state
from .graph import Graph
from .materialize import Drift, materialize

MAX_FLAGGED = 20_000
_TABLE_REF = re.compile(r'\b(?:from|join)\s+(?:main\.|before\.)?("?)([A-Za-z_][A-Za-z0-9_]*)\1(?![\w.])', re.I)


@dataclass
class Offer:
    check_title: str
    units_total: int
    units_kept: int
    units_dropped: int
    flagged_rows: int
    kept: dict = field(default_factory=dict)       # counts of what the subset still does
    dropped: dict = field(default_factory=dict)    # counts of what it no longer does
    effects: dict = field(default_factory=dict)    # the subset itself
    dropped_units: list[int] = field(default_factory=list)   # which units were cut (for drawing the plan)
    caused_by: list[dict] = field(default_factory=list)      # Proof of Effect: the statements that produced the cut rows
    checks: list[dict] = field(default_factory=list)         # every check the subset was cut by, and passes

    def public(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "effects"}


class NoOffer(Exception):
    """Why no subset is offered (always a reason a person can read)."""


def _run_check(db_path: Path, sql: str, before: str | Path, effects: dict) -> tuple[list[str], list[tuple]]:
    view = state.open_view(db_path, before, effects)
    try:
        cols, rows, more = state.run_check(view, sql, MAX_FLAGGED)
        if more:
            raise NoOffer(f"the check flags more than {MAX_FLAGGED:,} rows")
        return cols, rows
    except sqlite3.Error as e:
        raise NoOffer(f"the check doesn't run on the rehearsed data: {e}") from e
    finally:
        view.close()


def _candidate_tables(col: str, referenced: list[str]) -> list[str]:
    c = col.lower().split(".")[-1]
    if c in ("id", "rowid"):
        return referenced
    if c.endswith("_id"):
        base = c[:-3]
        return [base + "s", base + "es", base, *referenced]
    return []


def flagged_nodes(g: Graph, cols: list[str], rows: list[tuple], sql: str,
                  recipients: dict[str, list[str]] | None = None) -> tuple[set[str], int]:
    """Map each flagged result row to the graph. Returns (node ids, rows that could not be mapped).
    A row maps by id to a changed row, else to the context row that ties a unit together, else (a check over
    sent.emails) by recipient address to the emails sent to it."""
    referenced = [m.group(2) for m in _TABLE_REF.finditer(sql)]
    nodes, unmapped = set(), 0
    for row in rows:
        hit = None
        mails = [n for v in row if isinstance(v, str) and "@" in v for n in (recipients or {}).get(v.strip().lower(), [])]
        if mails:
            nodes.update(mails)
            continue
        for col, val in zip(cols, row, strict=False):
            if isinstance(val, bool) or not isinstance(val, int):
                continue
            for t in _candidate_tables(col, referenced):
                if f"row:{t}:{val}" in g.nodes:     # a changed row: the most precise match
                    hit = f"row:{t}:{val}"
                    break
            if hit:
                break
        if hit is None:                              # fall back to an unchanged row that ties a unit together
            for col, val in zip(cols, row, strict=False):
                if isinstance(val, int) and not isinstance(val, bool):
                    for t in _candidate_tables(col, referenced):
                        if f"ctx:{t}:{val}" in g.unit_of:
                            hit = f"ctx:{t}:{val}"
                            break
                if hit:
                    break
        if hit is None:
            unmapped += 1
        else:
            nodes.add(hit)
    return nodes, unmapped


def cut(effects: dict, g: Graph, keep_units: set[int]) -> dict:
    """The effects of the kept units only."""
    keep = {nid for i in keep_units for nid in g.units[i]}
    changes = {}
    for table, ch in (effects.get("changes") or {}).items():
        sub = {k: v for k, v in ch.items() if k not in ("deleted", "inserted", "updated")}
        for op in ("deleted", "inserted", "updated"):
            sub[op] = [it for it in ch.get(op, []) if f"row:{table}:{it['rowid']}" in keep]
        if sub["deleted"] or sub["inserted"] or sub["updated"]:
            changes[table] = sub
    return {"changes": changes,
            "payments": [p for i, p in enumerate(effects.get("payments") or []) if f"refund:{i}" in keep],
            "emails": [e for i, e in enumerate(effects.get("emails") or []) if f"email:{i}" in keep],
            "http": [c for i, c in enumerate(effects.get("http") or []) if f"http:{i}" in keep]}


def _counts(effects: dict) -> dict:
    rows = sum(len(ch.get(op, [])) for ch in (effects.get("changes") or {}).values() for op in ("deleted", "inserted", "updated"))
    pays = effects.get("payments") or []
    return {"rows": rows, "refunds": len(pays), "money_cents": sum(int(p.get("amount_cents") or 0) for p in pays),
            "emails": len(effects.get("emails") or []), "api_calls": len(effects.get("http") or [])}


def propose(effects: dict, g: Graph, base_db: str | Path, checks: list[dict]) -> Offer:
    """Find the largest part of the plan that passes every check. Raises NoOffer with a readable reason.

    `checks` are dicts with title, sql and required. Required checks (learned rules that fired, contract promises the
    plan broke) must all hold on the subset, whatever happens. An optional check (the AI jury's own) joins the cut only
    when every row it flags can be traced to this plan; otherwise it is left to the jury's re-check of the subset."""
    if not g.units:
        raise NoOffer("the plan has no consequences to keep")
    if not checks:
        raise NoOffer("nothing flags specific rows of this plan")
    recipients: dict[str, list[str]] = {}
    for i, m in enumerate(effects.get("emails") or []):
        recipients.setdefault(str(m.get("to", "")).strip().lower(), []).append(f"email:{i}")
    with tempfile.TemporaryDirectory() as d:
        try:
            after = materialize(base_db, effects, Path(d) / "after.db")
        except Drift as e:
            raise NoOffer(f"the data changed since the rehearsal ({e})") from e
        nodes: set[str] = set()
        used, flagged = [], 0
        for chk in checks:
            try:
                cols, rows = _run_check(after, chk["sql"], base_db, effects)
            except NoOffer:
                if chk.get("required"):
                    raise
                continue
            if not rows:
                continue
            found, unmapped = flagged_nodes(g, cols, rows, chk["sql"], recipients)
            if unmapped and not chk.get("required"):
                continue                      # a required check with untraced rows still has to hold on the subset
            nodes |= found
            used.append(chk)
            flagged += len(rows)
        if not used:
            raise NoOffer("the checks that fired can't be traced to specific consequences of this plan")
        drop = g.units_touching(nodes)
        keep = set(range(len(g.units))) - drop
        if not drop:
            raise NoOffer("no consequence of this plan can be traced to what the checks flag")
        if not keep:
            raise NoOffer("every part of the plan breaks a check")
        sub = cut(effects, g, keep)
        try:
            sub_after = materialize(base_db, sub, Path(d) / "subset.db")
        except Drift as e:
            raise NoOffer(f"the subset can't be rebuilt ({e})") from e
        for chk in used:
            _, still = _run_check(sub_after, chk["sql"], base_db, sub)
            if still:
                raise NoOffer(f"even without the flagged parts, “{chk['title']}” still finds {len(still):,} problems")
    full, kept = _counts(effects), _counts(sub)
    return Offer(check_title=used[0]["title"], units_total=len(g.units), units_kept=len(keep), units_dropped=len(drop),
                 flagged_rows=flagged, kept=kept, dropped={k: full[k] - kept[k] for k in full}, effects=sub,
                 dropped_units=sorted(drop)[:5000], checks=[{"title": c["title"], "source": c.get("source")} for c in used])
