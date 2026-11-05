"""Export a rehearsal's measured data changes as a portable SQL script (PostgreSQL / MySQL / SQLite).

Teams that apply database changes through their own migration or change-management pipeline can take exactly what was
rehearsed and approved. Every UPDATE carries the whole rehearsed row in its WHERE clause (like apply's drift check), so
it changes nothing if the row drifted since the rehearsal; every statement says how many rows it must touch.
"""
from __future__ import annotations

import time

UNCOMPARABLE = {"json", "xml", "bytea", "point", "polygon", "line", "box", "circle", "path"}


def ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def lit(v, pgtype: str | None = None) -> str:
    if pgtype == "boolean" and v in (0, 1, True, False):
        return "TRUE" if v else "FALSE"
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _key(row: dict, rowid, pk: list[str] | None = None) -> list[tuple[str, object]]:
    if pk and all(c in row for c in pk):
        return [(c, row[c]) for c in pk]
    return [("id", row["id"])] if "id" in row else [("rowid", rowid)]


def _eq(col: str, v, pgtype: str | None = None) -> str:
    return f"{ident(col)} IS NULL" if v is None else f"{ident(col)} = {lit(v, pgtype)}"


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
        pk, ty = (meta.get("pks") or {}).get(table), (meta.get("types") or {}).get(table) or {}
        for item in ch.get("updated", []):
            after, before = item["after"], item["before"]
            cols = item.get("changed") or [c for c in after if after.get(c) != before.get(c)]
            sets = ", ".join(f"{ident(c)} = {lit(after[c], ty.get(c))}" for c in cols)
            keys = _key(before, item["rowid"], pk)
            # Like apply's drift check, the WHERE clause holds the whole rehearsed row (types without '=' are skipped).
            whole = [c for c in before if c not in {k for k, _ in keys} and ty.get(c) not in UNCOMPARABLE]
            guard = " AND ".join([*(_eq(k, kv, ty.get(k)) for k, kv in keys), *(_eq(c, before.get(c), ty.get(c)) for c in whole)])
            out.append(f"UPDATE {t} SET {sets} WHERE {guard};  -- expect 1 row"); n += 1
        for item in ch.get("deleted", []):
            out.append(f"DELETE FROM {t} WHERE {' AND '.join(_eq(k, kv, ty.get(k)) for k, kv in _key(item['before'], item['rowid'], pk))};  -- expect 1 row"); n += 1
        for item in ch.get("inserted", []):
            cols = list(item["after"].keys())
            out.append(f"INSERT INTO {t} ({', '.join(ident(c) for c in cols)}) VALUES ({', '.join(lit(item['after'][c], ty.get(c)) for c in cols)});"); n += 1
    if not n:
        out.append("-- No row changes.")
    side = [(len(effects.get("payments") or []), "refunds through the payments provider"), (len(effects.get("emails") or []), "emails"),
            (len(effects.get("http") or []), "API calls")]
    notes = [f"{c} {what}" for c, what in side if c]
    out += ["", "COMMIT;", ""]
    if notes:
        out.append(f"-- Not SQL, and not in this script: {', '.join(notes)}. Stunt Double replays those itself after approval.")
    return "\n".join(out) + "\n"
