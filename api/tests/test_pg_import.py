"""A real PostgreSQL round trip: import a double read-only, rehearse, export the guarded SQL, run it on the real database.
The connection string is never kept, internal hosts are refused, and approval never writes to the real database."""
import json
import shutil
import subprocess
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app import config, main
from tests.conftest import needs_docker

PORT = 55432
URL = f"postgresql://sd:sd-secret-pw@127.0.0.1:{PORT}/shop"


@pytest.fixture(scope="module")
def postgres():
    if not shutil.which("docker") or subprocess.run(["docker", "image", "inspect", "postgres:16-alpine"], capture_output=True).returncode:
        pytest.skip("postgres:16-alpine image not available")
    name = "sd-test-pg-" + uuid.uuid4().hex[:6]
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_USER=sd", "-e", "POSTGRES_PASSWORD=sd-secret-pw",
                    "-e", "POSTGRES_DB=shop", "-p", f"{PORT}:5432", "postgres:16-alpine"], check=True, capture_output=True)
    import psycopg
    for _ in range(60):
        try:
            con = psycopg.connect(URL, connect_timeout=2, autocommit=True)
            break
        except psycopg.Error:
            time.sleep(1)
    else:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        pytest.skip("postgres did not start")
    con.execute("""CREATE TABLE plans (code text PRIMARY KEY, price numeric(10,2) NOT NULL);
                   CREATE TABLE accounts (account_id uuid PRIMARY KEY, email text NOT NULL, plan text REFERENCES plans(code),
                                          active boolean NOT NULL, seats integer NOT NULL, created_at timestamptz NOT NULL);
                   INSERT INTO plans VALUES ('free', 0), ('pro', 49.50);""")
    for i in range(1, 31):
        con.execute("INSERT INTO accounts VALUES (%s, %s, %s, %s, %s, now())",
                    (uuid.UUID(int=i), f"user{i}@example.com", "free" if i % 3 else "pro", i % 5 != 0, i))
    yield con
    con.close()
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@needs_docker
def test_postgres_round_trip(postgres, fresh_business, monkeypatch):
    monkeypatch.setattr(config, "PG_ALLOW_PRIVATE", True)
    api = TestClient(main.app)
    r = api.post("/api/workspaces/postgres", json={"url": URL, "name": "Shop DB"})
    assert r.status_code == 200, r.text
    ws = r.json()
    assert ws["kind"] == "postgres" and "2 tables, 32 rows" in ws["description"]
    stored = [p for p in (config.DATA_DIR / "workspaces").rglob("*") if p.is_file()]
    assert not any(b"sd-secret-pw" in p.read_bytes() for p in stored)          # the connection string is nowhere on disk
    assert "sd-secret-pw" not in json.dumps(api.get("/api/workspaces").json())

    plan = "def run(ctx):\n    ctx.db.execute(\"UPDATE accounts SET plan = 'pro', active = 1 WHERE plan = 'free' AND seats >= 25\")\n"
    rid = api.post("/api/runs/manual", json={"task": "Upgrade big free accounts to pro", "code": plan, "workspace": ws["id"]}).json()["id"]
    for _ in range(160):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    assert run["status"] == "review", run.get("error")
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya", "note": "big free accounts"}).status_code == 409  # never writes
    sql = api.get(f"/api/runs/{rid}/effects.sql").text
    assert '"account_id" = ' in sql and "TRUE" in sql                         # real primary key, real boolean

    postgres.execute("UPDATE accounts SET seats = 99 WHERE account_id = %s", (uuid.UUID(int=26),))  # someone changed one row since
    postgres.execute(sql)
    rows = dict(postgres.execute("SELECT seats, plan FROM accounts WHERE seats >= 25").fetchall())
    assert rows[25] == "pro" and rows[29] == "pro" and rows[28] == "pro"
    assert postgres.execute("SELECT plan FROM accounts WHERE account_id = %s", (uuid.UUID(int=26),)).fetchone()[0] == "free"  # drifted: untouched
    assert postgres.execute("SELECT count(*) FROM accounts WHERE plan = 'pro'").fetchone()[0] == 10 + 3


def test_internal_hosts_and_bad_urls_are_refused():
    api = TestClient(main.app)
    for url in ("postgresql://u:p@127.0.0.1:5432/db", "postgresql://u:p@169.254.169.254/db", "postgresql://u:p@10.0.0.5/db", "mysql://u:p@example.com/db"):
        r = api.post("/api/workspaces/postgres", json={"url": url})
        assert r.status_code == 400 and "p@" not in r.text, (url, r.text)


@needs_docker
def test_one_click_sample_database(fresh_business, monkeypatch):
    """The console's sample: infra/sample-pg/init.sql in a real Postgres, imported through the same read-only path."""
    if subprocess.run(["docker", "image", "inspect", "postgres:16-alpine"], capture_output=True).returncode:
        pytest.skip("postgres:16-alpine image not available")
    from pathlib import Path
    init = Path(__file__).resolve().parents[2] / "infra" / "sample-pg" / "init.sql"
    name, port = "sd-test-sample-" + uuid.uuid4().hex[:6], 55433
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_DB=saas", "-e", "POSTGRES_PASSWORD=x",
                    "-v", f"{init}:/docker-entrypoint-initdb.d/init.sql:ro", "-p", f"{port}:5432", "postgres:16-alpine"], check=True, capture_output=True)
    try:
        import psycopg
        url = f"postgresql://sd_readonly:sd-sample-readonly@127.0.0.1:{port}/saas"
        for _ in range(60):
            try:
                psycopg.connect(url, connect_timeout=2).close()
                break
            except psycopg.Error:
                time.sleep(1)
        monkeypatch.setattr(config, "SAMPLE_PG_URL", url)
        api = TestClient(main.app)
        r = api.post("/api/workspaces/postgres/sample")
        assert r.status_code == 200, r.text
        assert "3 tables, 1,719 rows" in r.json()["description"] and r.json()["kind"] == "postgres"
        assert "sd-sample-readonly" not in r.text
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
