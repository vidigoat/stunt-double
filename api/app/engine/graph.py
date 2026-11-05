"""The Effect Graph.

A rehearsal's consequences are not a list. A refund belongs to a charge, the charge belongs to a customer, and the
apology email goes to that same customer. The Effect Graph makes those relationships explicit:

    nodes   every measured consequence (a changed row, a refund, an email, an API call), plus the unchanged rows
            that connect them ("context", e.g. the customer a refund and an email both point at)
    edges   foreign keys declared by the database, refunds to their charge (charge_id), emails to the row that owns
            the recipient address
    units   connected groups of consequences: one unit is one indivisible piece of work ("refund Ana's duplicate
            charge and email her"). Units are what surgical approval keeps or cuts.

Built only from trusted inputs: the effects measured by phase 2 and the host's own "before" copy of the data.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

MAX_NODES = 50_000
HUB_DEGREE = 25   # a context row linked to more consequences than this (a shared store, a plan tier) doesn't join units


def _q(ident: str) -> str:
    return '"' + str(ident).replace('"', '""') + '"'


@dataclass
class Node:
    id: str
    kind: str                 # "row" | "refund" | "email" | "http" | "context"
    label: str
    table: str | None = None
    rowid: int | None = None
    op: str | None = None     # row nodes: "updated" | "inserted" | "deleted"
    index: int | None = None  # refund/email/http nodes: position in the effects list
    money_cents: int = 0

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None and not (k == "money_cents" and not v)}


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)   # (from, to, why)
    units: list[list[str]] = field(default_factory=list)               # node ids per unit, consequence nodes only
    unit_of: dict[str, int] = field(default_factory=dict)
    hubs: list[str] = field(default_factory=list)
    truncated: bool = False

    # ---- queries ------------------------------------------------------------------------------------------------
    def row_node(self, table: str, rowid: int) -> str | None:
        nid = f"row:{table}:{rowid}"
        return nid if nid in self.nodes else None

    def units_touching(self, node_ids: set[str]) -> set[int]:
        """The units that contain any of these nodes (context nodes map to every unit they connect)."""
        out = set()
        for nid in node_ids:
            if nid in self.unit_of:
                out.add(self.unit_of[nid])
        return out

    def summary(self) -> dict:
        kinds = defaultdict(int)
        for n in self.nodes.values():
            if n.kind != "context":
                kinds[n.kind] += 1
        sizes = [len(u) for u in self.units]
        return {"nodes": sum(kinds.values()), "by_kind": dict(kinds), "units": len(self.units),
                "largest_unit": max(sizes, default=0), "edges": len(self.edges), "hubs": len(self.hubs), "truncated": self.truncated}

    def as_dict(self, max_units: int = 2000) -> dict:
        units = self.units[:max_units]
        keep = {nid for u in units for nid in u}
        keep |= {b for a, b, _ in self.edges if a in keep and self.nodes[b].kind == "context"}
        return {
            "summary": self.summary(),
            "units": [{"index": i, "nodes": u} for i, u in enumerate(units)],
            "nodes": {nid: self.nodes[nid].as_dict() for nid in keep},
            "edges": [list(e) for e in self.edges if e[0] in keep and e[1] in keep],
        }


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _row_label(table: str, row: dict | None, rowid: int) -> str:
    row = row or {}
    for key in ("name", "label", "email", "title", "subject", "plan"):
        if row.get(key):
            return f"{table} #{rowid} · {str(row[key])[:40]}"
    return f"{table} #{rowid}"


def build(effects: dict, before_db: str | None) -> Graph:
    """Build the Effect Graph from measured effects. `before_db` is the trusted pre-plan copy (used to resolve links
    to rows the plan did not change); without it, only links between changed rows are drawn."""
    g = Graph()
    changes = effects.get("changes") or {}
    db = sqlite3.connect(f"file:{before_db}?mode=ro", uri=True) if before_db else None
    try:
        # 1. a node for every changed row --------------------------------------------------------------------------
        values: dict[str, dict] = {}
        for table, ch in changes.items():
            if ch.get("dropped") or ch.get("schema_changed"):
                continue
            for op in ("updated", "inserted", "deleted"):
                for item in ch.get(op, []):
                    if len(g.nodes) >= MAX_NODES:
                        g.truncated = True
                        break
                    row = item.get("after") or item.get("before") or {}
                    nid = f"row:{table}:{item['rowid']}"
                    g.nodes[nid] = Node(nid, "row", _row_label(table, row, item["rowid"]), table=table, rowid=int(item["rowid"]), op=op)
                    values[nid] = {**(item.get("before") or {}), **(item.get("after") or {})}

        def context(table: str, rowid: int) -> str:
            nid = f"row:{table}:{rowid}"
            if nid in g.nodes:
                return nid
            cid = f"ctx:{table}:{rowid}"
            if cid not in g.nodes:
                row = None
                if db is not None:
                    try:
                        cur = db.execute(f"SELECT * FROM {_q(table)} WHERE rowid = ?", (rowid,))
                        r = cur.fetchone()
                        row = dict(zip([c[0] for c in cur.description], r, strict=False)) if r else None
                    except sqlite3.Error:
                        row = None
                g.nodes[cid] = Node(cid, "context", _row_label(table, row, rowid), table=table, rowid=rowid)
            return cid

        def lookup(table: str, column: str, value) -> int | None:
            if db is None or value is None:
                return None
            try:
                r = db.execute(f"SELECT rowid FROM {_q(table)} WHERE {_q(column)} = ? LIMIT 2", (value,)).fetchall()
            except sqlite3.Error:
                return None
            return r[0][0] if len(r) == 1 else None   # ambiguous or missing: no edge (never guess)

        # 2. foreign keys declared by the database -----------------------------------------------------------------
        fks: dict[str, list[tuple[str, str, str]]] = {}
        if db is not None:
            for table in changes:
                try:
                    fks[table] = [(r[3], r[2], r[4] or "rowid") for r in db.execute(f"PRAGMA foreign_key_list({_q(table)})")]
                except sqlite3.Error:
                    fks[table] = []
        for nid, row in list(values.items()):
            table = g.nodes[nid].table
            for col, parent, pcol in fks.get(table, []):
                prow = row.get(col) if pcol == "rowid" else lookup(parent, pcol, row.get(col))
                if prow is None:
                    continue
                g.edges.append((nid, context(parent, int(prow)), f"{table}.{col} → {parent}"))

        # 3. refunds belong to their charge ------------------------------------------------------------------------
        charge_table = "charges" if (db is not None and _has_table(db, "charges")) or "charges" in changes else None
        for i, p in enumerate(effects.get("payments") or []):
            nid = f"refund:{i}"
            g.nodes[nid] = Node(nid, "refund", f"refund ${p.get('amount_cents', 0) / 100:,.2f} · charge {p.get('charge_id')}",
                                index=i, money_cents=int(p.get("amount_cents") or 0))
            if charge_table and p.get("charge_id") is not None:
                target = g.row_node(charge_table, int(p["charge_id"]))
                if target is None and db is not None and lookup(charge_table, "id", p["charge_id"]) is not None:
                    target = context(charge_table, int(p["charge_id"]))
                if target:
                    g.edges.append((nid, target, "refund.charge_id"))

        # 4. emails belong to the row that owns the recipient address ------------------------------------------------
        email_tables = _email_tables(db) if db is not None else []
        for i, e in enumerate(effects.get("emails") or []):
            nid = f"email:{i}"
            g.nodes[nid] = Node(nid, "email", f"email to {str(e.get('to', ''))[:60]}", index=i)
            for table in email_tables:
                rid = lookup(table, "email", e.get("to"))
                if rid is not None:
                    g.edges.append((nid, context(table, rid), f"email → {table}.email"))
                    break

        # 5. API calls: their own units (nothing to link them by, reliably) ------------------------------------------
        for i, c in enumerate(effects.get("http") or []):
            nid = f"http:{i}"
            g.nodes[nid] = Node(nid, "http", f"{c.get('method', 'POST')} {str(c.get('url', ''))[:60]}", index=i)
    finally:
        if db is not None:
            db.close()

    # 6. units of work: connected components, counting only consequence nodes ----------------------------------------
    degree: dict[str, int] = defaultdict(int)
    for _, b, _why in g.edges:
        degree[b] += 1
    hubs = {nid for nid, d in degree.items() if d > HUB_DEGREE and g.nodes[nid].kind == "context"}
    uf = _UnionFind()
    for nid in g.nodes:
        uf.find(nid)
    for a, b, _ in g.edges:
        if b not in hubs:
            uf.union(a, b)
    groups: dict[str, list[str]] = defaultdict(list)
    for nid in g.nodes:
        groups[uf.find(nid)].append(nid)
    units = []
    for members in groups.values():
        consequences = sorted(m for m in members if g.nodes[m].kind != "context")
        if consequences:
            units.append((consequences, [m for m in members if g.nodes[m].kind == "context"]))
    units.sort(key=lambda u: u[0])
    for i, (cons, ctx) in enumerate(units):
        g.units.append(cons)
        for nid in cons + ctx:
            g.unit_of[nid] = i
    g.hubs = sorted(hubs)
    return g


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)).fetchone() is not None


def _email_tables(db: sqlite3.Connection) -> list[str]:
    out = []
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        if any(r[1] == "email" for r in db.execute(f"PRAGMA table_info({_q(t)})")):
            out.append(t)
    return out
