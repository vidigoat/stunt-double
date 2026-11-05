"""Build a double of a real Vultr account's fleet: read the instances once with the visitor's API key (GET requests
only), write them into a `servers` table shaped like the demo fleet, and forget the key.

The key is never stored, logged, put in a run or passed to a sandbox. Rehearsals against the imported fleet change only
the double. The Vultr API has no CPU or traffic history, so those columns are NULL (unknown), never guessed.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import httpx

API = "https://api.vultr.com/v2"
MAX_INSTANCES = 500

SCHEMA = """CREATE TABLE servers (id INTEGER PRIMARY KEY, instance_id TEXT NOT NULL UNIQUE, label TEXT NOT NULL, plan TEXT NOT NULL,
  region TEXT NOT NULL, vcpu INTEGER NOT NULL, ram_mb INTEGER NOT NULL, monthly_cost_cents INTEGER NOT NULL, tags TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running', cpu_avg_7d REAL, requests_7d INTEGER, purpose TEXT NOT NULL, created_at TEXT NOT NULL,
  main_ip TEXT, os TEXT);"""


class ImportError_(Exception):
    pass


def _get_all(client: httpx.Client, path: str, key: str) -> list[dict]:
    items, cursor = [], ""
    while True:
        r = client.get(f"{API}{path}", params={"per_page": 100, **({"cursor": cursor} if cursor else {})})
        if r.status_code in (401, 403):
            raise ImportError_("Vultr rejected that key. Check it, and that the key's Access Control allows this server's IP.")
        if r.status_code >= 300:
            raise ImportError_(f"Vultr API error {r.status_code}")
        body = r.json()
        items += body.get(key, [])
        cursor = (body.get("meta", {}).get("links") or {}).get("next") or ""
        if not cursor or len(items) >= MAX_INSTANCES:
            return items[:MAX_INSTANCES]


def fleet(api_key: str) -> list[dict]:
    """Read-only: list instances and plan prices."""
    api_key = api_key.strip()
    if not (20 <= len(api_key) <= 64 and api_key.isalnum()):
        raise ImportError_("That doesn't look like a Vultr API key")
    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=20) as c:
        instances = _get_all(c, "/instances", "instances")
        prices = {p["id"]: p for p in _get_all(c, "/plans?type=all", "plans")}
    return [{**i, "_monthly_cents": int(round(float((prices.get(i.get("plan")) or {}).get("monthly_cost") or 0) * 100))} for i in instances]


def to_sqlite(instances: list[dict]) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "fleet.db"
        db = sqlite3.connect(path)
        db.executescript(SCHEMA)
        for n, i in enumerate(instances, start=1):
            db.execute("INSERT INTO servers (id,instance_id,label,plan,region,vcpu,ram_mb,monthly_cost_cents,tags,status,cpu_avg_7d,requests_7d,"
                       "purpose,created_at,main_ip,os) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,?,?,?,?)",
                       (n, str(i["id"]), str(i.get("label") or i.get("hostname") or i["id"])[:120], str(i.get("plan", "")), str(i.get("region", "")),
                        int(i.get("vcpu_count") or 0), int(i.get("ram") or 0), i["_monthly_cents"], ",".join(str(t) for t in (i.get("tags") or []))[:300],
                        "stopped" if i.get("power_status") == "stopped" else "running", str(i.get("hostname") or "")[:120],
                        str(i.get("date_created", ""))[:19].replace("T", " "), str(i.get("main_ip", "")), str(i.get("os", ""))[:80]))
        db.commit()
        db.close()
        return path.read_bytes()
