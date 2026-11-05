"""Measured changes export as a SQL script that applies exactly the rehearsed changes, and nothing if rows drifted."""
import sqlite3
import time

from fastapi.testclient import TestClient

from app import config, main, sql_export
from tests.conftest import needs_docker


def test_script_applies_exactly_and_refuses_drifted_rows(tmp_path):
    effects = {"changes": {"accounts": {"dropped": False, "created": False,
        "updated": [{"rowid": 1, "before": {"id": 1, "name": "O'Hara", "tier": "free"}, "after": {"id": 1, "name": "O'Hara", "tier": "pro"}, "changed": ["tier"]},
                    {"rowid": 2, "before": {"id": 2, "name": "Lee", "tier": "free"}, "after": {"id": 2, "name": "Lee", "tier": "pro"}, "changed": ["tier"]}],
        "deleted": [{"rowid": 3, "before": {"id": 3, "name": "Gone", "tier": None}}],
        "inserted": [{"rowid": 4, "after": {"id": 4, "name": "New; DROP TABLE accounts;--", "tier": "free"}}]}},
        "payments": [{"amount_cents": 100}], "emails": [], "http": []}
    script = sql_export.export(effects, {"run_id": "run_x", "status": "review", "task": "upgrade", "plan_sha256": "p", "effects_sha256": "e"})
    db = sqlite3.connect(tmp_path / "t.db")
    db.executescript("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, tier TEXT);"
                     "INSERT INTO accounts VALUES (1, 'O''Hara', 'free'), (2, 'Lee', 'enterprise'), (3, 'Gone', NULL);")
    db.executescript(script)
    rows = db.execute("SELECT id, name, tier FROM accounts ORDER BY id").fetchall()
    assert rows == [(1, "O'Hara", "pro"), (2, "Lee", "enterprise"), (4, "New; DROP TABLE accounts;--", "free")]  # 2 drifted: untouched
    assert "1 refunds through the payments provider" in script


@needs_docker
def test_endpoint_exports_a_real_rehearsal(fresh_business):
    api = TestClient(main.app)
    plan = "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || ' (VIP)' WHERE id <= 2\")\n"
    rid = api.post("/api/runs/manual", json={"task": "mark two VIPs", "code": plan}).json()["id"]
    for _ in range(120):
        if api.get(f"/api/runs/{rid}").json()["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    r = api.get(f"/api/runs/{rid}/effects.sql")
    assert r.status_code == 200 and r.text.count('UPDATE "customers"') == 2 and "attachment" in r.headers["content-disposition"]
    db = sqlite3.connect(config.PROD_DB)
    db.executescript(r.text)
    assert db.execute("SELECT COUNT(*) FROM customers WHERE name LIKE '% (VIP)'").fetchone()[0] == 2
