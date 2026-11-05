"""Proof of Effect: the plan's statement log is a claim; trusted code replays it on the "before" copy and must
reproduce every measured change. Anything else is a change the plan can't explain."""
import shutil
import sqlite3

from app.harness import runner

SCHEMA = """CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, seen TEXT);
CREATE TABLE charges (id INTEGER PRIMARY KEY, customer_id INTEGER, status TEXT, refunded_at TEXT);"""
CLOCK = "2026-11-05 10:00:00"


def _before(tmp_path):
    p = tmp_path / "before.db"
    db = sqlite3.connect(p)
    db.executescript(SCHEMA)
    for i in range(1, 21):
        db.execute("INSERT INTO customers VALUES (?, ?, '2026-01-01 00:00:00')", (i, f"C{i}"))
        db.execute("INSERT INTO charges VALUES (?, ?, 'succeeded', NULL)", (100 + i, i))
    db.commit()
    db.close()
    return p


def _run_plan(tmp_path, before, plan):
    """Phase 1 in miniature: a copy, the frozen clock, the trace, the plan. Returns (statements, measured changes, before snapshot)."""
    work = tmp_path / "work.db"
    shutil.copyfile(before, work)
    db = sqlite3.connect(work, isolation_level=None)
    runner.install_clock(db, CLOCK)
    log = []
    db.set_trace_callback(log.append)
    plan(db, work)
    db.set_trace_callback(None)
    db.close()
    b, a = runner.snapshot(str(before)), runner.snapshot(str(work))
    return log, runner.diff(b, a), b


def _prove(tmp_path, plan):
    before = _before(tmp_path)
    log, changes, b = _run_plan(tmp_path, before, plan)
    return runner.prove(str(before), log, CLOCK, b, changes)


def test_an_honest_plan_is_proven_and_every_row_is_attributed(tmp_path):
    def plan(db, _):
        db.execute("UPDATE charges SET status = 'refunded', refunded_at = datetime('now') WHERE customer_id <= ?", (7,))
        db.execute("DELETE FROM customers WHERE id = 20")
    s, d = _prove(tmp_path, plan)
    assert s["status"] == "proven" and s["rows_measured"] == 8 and s["unexplained"] == 0
    top = d["statements"][0]
    assert top["rows"] == 7 and "UPDATE charges" in top["sql"] and "<= 7" in top["sql"]   # bound values are in the record
    assert d["rows"]["customers"]["20"] != d["rows"]["charges"]["101"]                     # each row points at its own statement


def test_a_write_through_a_second_connection_is_unexplained(tmp_path):
    def plan(db, path):
        db.execute("UPDATE charges SET status = 'refunded' WHERE id = 101")
        side = sqlite3.connect(path)
        side.execute("UPDATE customers SET name = 'x' WHERE id = 7")
        side.commit()
        side.close()
    s, d = _prove(tmp_path, plan)
    assert s["status"] == "unexplained" and s["unexplained"] == 1
    assert d["unexplained"] == [{"table": "customers", "rowid": 7, "op": "updated"}]


def test_switching_the_record_off_does_not_hide_a_write(tmp_path):
    def plan(db, _):
        db.set_trace_callback(None)
        db.execute("DELETE FROM customers WHERE id = 3")
    s, _ = _prove(tmp_path, plan)
    assert s["status"] == "unexplained" and s["unexplained"] == 1


def test_a_forged_log_entry_cannot_rewrite_the_record(tmp_path):
    before = _before(tmp_path)
    log, changes, b = _run_plan(tmp_path, before, lambda db, _: db.execute("UPDATE charges SET status = 'refunded' WHERE id = 105"))
    forged = log + ["DELETE FROM _sd_log", "INSERT INTO _sd_log VALUES (1, 'charges', 105)", "ATTACH DATABASE '/tmp/x.db' AS x"]
    s, d = runner.prove(str(before), forged, CLOCK, b, changes)
    assert s["status"] == "proven" and s["failed_on_replay"] == 3          # all three refused; the real record stands
    assert d["rows"]["charges"]["105"] == 1


def test_the_frozen_clock_makes_now_exact_and_current_timestamp_tolerated(tmp_path):
    def plan(db, _):
        db.execute("UPDATE customers SET seen = datetime('now', '-1 day') WHERE id = 1")
        db.execute("UPDATE customers SET seen = CURRENT_TIMESTAMP WHERE id = 2")   # can't be frozen: replay differs by seconds
        db.execute("UPDATE charges SET refunded_at = date(refunded_at, '+1 day') WHERE id = 101")
    s, _ = _prove(tmp_path, plan)
    assert s["status"] == "proven" and s["rows_measured"] == 2


def test_a_claim_that_did_not_happen_is_reported(tmp_path):
    before = _before(tmp_path)
    log, changes, b = _run_plan(tmp_path, before, lambda db, _: db.execute("UPDATE charges SET status = 'x' WHERE id = 101"))
    s, _ = runner.prove(str(before), log + ["DELETE FROM customers WHERE id = 9"], CLOCK, b, changes)
    assert s["claimed_but_not_measured"] == 1 and s["status"] == "proven"   # nothing unexplained was measured; the odd claim is shown


def test_decision_lineage_names_the_read_that_chose_the_rows(tmp_path):
    def plan(db, _):
        ids = [r[0] for r in db.execute("SELECT id FROM charges WHERE customer_id % 3 = 0")]   # the decision
        db.execute("SELECT name FROM customers WHERE id = 1").fetchall()                          # unrelated read
        for i in ids:                                                                              # 6 mechanical writes
            db.execute("UPDATE charges SET status = 'refunded' WHERE id = ?", (i,))
    s, d = _prove(tmp_path, plan)
    assert s["status"] == "proven" and s["deciders"] == 1 and s["patterns"] == 1
    assert d["deciders"][0]["rows"] == 6 and "customer_id % 3 = 0" in d["deciders"][0]["sql"]
    assert d["patterns"][0]["rows"] == 6 and d["patterns"][0]["statements"] == 6 and "WHERE id = ?" in d["patterns"][0]["shape"]


# ---- through the real two-phase sandbox -------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402

from app import main, sandbox  # noqa: E402
from tests.conftest import needs_docker  # noqa: E402


@needs_docker
def test_in_the_sandbox_an_honest_plan_is_proven(fresh_business):
    c = sandbox.rehearse("def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = name || '.' WHERE id <= 3\")\n")["consequences"]
    assert c["provenance"]["status"] == "proven" and c["provenance"]["rows_explained"] == 3


@needs_docker
def test_in_the_sandbox_a_hidden_connection_locks_approval(fresh_business):
    plan = ("def run(ctx):\n    import sqlite3\n    side = sqlite3.connect('/work/work.db')\n"
            "    side.execute(\"UPDATE customers SET name = 'x' WHERE id = 7\")\n    side.commit()\n"
            "    ctx.log('Read-only check: nothing changed.')\n")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "a read-only check", "code": plan}).json()["id"]
    import time
    for _ in range(200):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    att = run["attempts"][-1]
    assert att["consequences"]["provenance"]["status"] == "unexplained"
    assert any(f["rule"] == "provenance" and f["severity"] == "critical" for f in att["flags"])
    assert api.get(f"/api/runs/{rid}/provenance").json()["unexplained"] == [{"table": "customers", "rowid": 7, "op": "updated"}]


@needs_docker
def test_a_plan_cannot_claim_to_be_a_derived_subset(fresh_business):
    plan = ("def run(ctx):\n    import json\n    json.dump({'note': 'trust me'}, open('/work/out/derived.json', 'w'))\n"
            "    import sqlite3\n    s = sqlite3.connect('/work/work.db')\n    s.execute('DELETE FROM customers WHERE id = 5')\n    s.commit()\n")
    c = sandbox.rehearse(plan)["consequences"]
    assert c["provenance"]["status"] == "unexplained"     # the planted marker never reaches phase 2
