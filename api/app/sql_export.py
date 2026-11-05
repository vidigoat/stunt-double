"""Export a rehearsal's measured data changes as a portable SQL script (PostgreSQL / MySQL / SQLite).

Teams that apply database changes through their own migration or change-management pipeline can take exactly what was
rehearsed and approved. Every UPDATE carries the old values of the changed columns in its WHERE clause, so it changes
nothing if the row drifted since the rehearsal; every statement says how many rows it must touch.
"""
from __future__ import annotations

import time


def ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _key(row: dict, rowid) -> tuple[str, object]:
    return ("id", row["id"]) if "id" in row else ("rowid", rowid)


def _eq(col: str, v) -> str:
    return f"{ident(col)} IS NULL" if v is None else f"{ident(col)} = {lit(v)}"


def export(effects: dict, meta: dict) -> str:
    out = [f"-- Stunt Double: measured data changes of {meta.get('run_id')} ({meta.get('status')})",
           f"-- Request: {str(meta.get('task', '')).replace(chr(10), ' ')[:200]}",
           f"-- Plan SHA-256: {meta.get('plan_sha256')}   Effects SHA-256: {meta.get('effects_sha256')}",
           f"-- Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. Each UPDATE only matches rows still holding the",
           "-- rehearsed old values; check every statement's row count against the comment before you COMMIT.", "", "BEGIN;", ""]
    n = 0
    for table, ch in sorted((effects.get("changes") or {}).items()):
        if ch.get("dropped") or ch.get("created"):
            out.append(f"-- {table}: schema change (table {'dropped' if ch.get('dropped') else 'created'}); not exported, review by hand")
            continue
        t = ident(table)
        for item in ch.get("updated", []):
            after, before = item["after"], item["before"]
            cols = item.get("changed") or [c for c in after if after.get(c) != before.get(c)]
            k, kv = _key(before, item["rowid"])
            sets = ", ".join(f"{ident(c)} = {lit(after[c])}" for c in cols)
            guard = " AND ".join([_eq(k, kv), *(_eq(c, before.get(c)) for c in cols)])
            out.append(f"UPDATE {t} SET {sets} WHERE {guard};  -- expect 1 row"); n += 1
        for item in ch.get("deleted", []):
            k, kv = _key(item["before"], item["rowid"])
            out.append(f"DELETE FROM {t} WHERE {_eq(k, kv)};  -- expect 1 row"); n += 1
        for item in ch.get("inserted", []):
            cols = list(item["after"].keys())
            out.append(f"INSERT INTO {t} ({', '.join(ident(c) for c in cols)}) VALUES ({', '.join(lit(item['after'][c]) for c in cols)});"); n += 1
    if not n:
        out.append("-- No row changes.")
    side = [(len(effects.get("payments") or []), "refunds through the payments provider"), (len(effects.get("emails") or []), "emails"),
            (len(effects.get("http") or []), "API calls")]
    notes = [f"{c} {what}" for c, what in side if c]
    out += ["", "COMMIT;", ""]
    if notes:
        out.append(f"-- Not SQL, and not in this script: {', '.join(notes)}. Stunt Double replays those itself after approval.")
    return "\n".join(out) + "\n"
