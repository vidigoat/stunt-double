"""One decision from six layers, and a signed record that breaks if anyone changes, drops or reorders a step."""
import copy
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, main
from app.engine import evidence, verdict
from tests.conftest import needs_docker

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdk" / "python"))
from stunt_double.evidence import verify_evidence  # noqa: E402


def _run(**over):
    c = {"ok": True, "tables": {"charges": {"updated": 104, "deleted": 0, "inserted": 0}}, "payments": {"count": 104}, "emails": {"count": 104},
         "provenance": {"status": "proven", "statements": 210, "rows_measured": 104},
         "contract": {"promises": [{"text": "Refund the 104", "kind": "obligation", "today": 104, "after": 0, "status": "met"},
                                   {"text": "Nothing else", "kind": "guard", "today": 0, "after": 0, "status": "kept"}]}}
    c.update(over.pop("c", {}))
    run = {"status": "review", "attempts": [{"n": 1, "consequences": c, "flags": over.pop("flags", []), "approvals_required": 1}],
           "verdict": {"verdict": "looks_right", "headline": "exactly the 104", "jury": {"agree": 3, "cast": 3}}}
    run.update(over)
    return run


def test_every_layer_passing_means_approve():
    d = verdict.decide(_run())
    assert d["decision"] == "approve" and [x["status"] for x in d["layers"]] == ["pass"] * 6
    assert "finishes the work (104 of 104)" in d["layers"][2]["reason"]


def test_a_broken_promise_blocks_and_a_provable_subset_turns_it_into_a_cut():
    broken = {"contract": {"promises": [{"text": "Nothing else", "kind": "guard", "today": 0, "after": 640, "status": "broken"}]}}
    d = verdict.decide(_run(c=broken, verdict={"verdict": "dangerous", "headline": "640 never double-charged"}))
    assert d["decision"] == "blocked" and d["failed"] == ["contract"] and "640 rows" in d["layers"][2]["reason"]
    d = verdict.decide(_run(c=broken, surgical={"offer": {"units_kept": 104, "units_total": 744}}))
    assert d["decision"] == "cut" and "104 of 744" in d["headline"]


def test_a_broken_promise_the_jury_disagrees_with_goes_to_a_person():
    broken = {"contract": {"promises": [{"text": "Keep a record of every server", "kind": "guard", "today": 0, "after": 4, "status": "broken"}]}}
    d = verdict.decide(_run(c=broken))                                   # the jury (by default here) says looks_right
    assert d["decision"] == "review" and d["failed"] == [] and "disagree" in d["headline"]


def test_an_unexplained_change_blocks():
    d = verdict.decide(_run(c={"provenance": {"status": "unexplained", "unexplained": 1}}))
    assert d["decision"] == "blocked" and d["failed"] == ["proof"]


def test_the_jury_alone_asks_for_a_person_not_a_lock():
    d = verdict.decide(_run(verdict={"verdict": "dangerous", "headline": "640 never double-charged"}))
    assert d["decision"] == "review" and d["failed"] == [] and "written reason" in d["headline"]


def test_unfinished_work_asks_for_review():
    unmet = {"contract": {"promises": [{"text": "Refund the 104", "kind": "obligation", "today": 104, "after": 54, "status": "unmet"}]}}
    d = verdict.decide(_run(c=unmet))
    assert d["decision"] == "review" and "54 of 104" in d["layers"][2]["reason"]


def test_rules_alone_never_mean_approve():
    d = verdict.decide(_run(verdict=None, c={"contract": None}))
    assert d["decision"] == "review" and "nothing checked the meaning" in d["headline"]


def test_nothing_to_decide_while_running():
    assert verdict.decide(_run(status="verifying")) is None
    assert verdict.decide(_run(status="failed")) is None          # interrupted before it was judged: no decision


# ---- the evidence chain ---------------------------------------------------------------------------------------
STEPS = [("request", {"task": "refund"}), ("rehearsal", {"refunds": {104: 513600}, "plan": "def run(ctx): ..."}),
         ("decision", {"decision": "approve"}), ("sign_off", {"approver": "Priya"})]


def _sealed(tmp_path):
    return json.loads(json.dumps(evidence.seal(STEPS, tmp_path)))     # exactly what a reader downloads


def test_a_sealed_record_verifies_after_download(tmp_path):
    b = _sealed(tmp_path)
    key = evidence.public_key(tmp_path)["public_key"]
    assert evidence.verify(b, key)["ok"] and verify_evidence(b, key)["ok"]      # server and SDK agree
    assert (tmp_path / "evidence-key.pem").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("tamper, why", [
    (lambda b: b["entries"][1]["body"]["refunds"].update({"104": 1}), "entry 1 (rehearsal) was changed"),
    (lambda b: b["entries"][3]["body"].update(approver="Mallory"), "entry 3 (sign_off) was changed"),
    (lambda b: b["entries"].pop(2), "out of order or detached"),
    (lambda b: b["entries"].reverse(), "out of order or detached"),
    (lambda b: b["entries"].pop(), "head doesn't match"),
])
def test_any_change_breaks_the_record(tmp_path, tamper, why):
    b = _sealed(tmp_path)
    tamper(b)
    for check in (evidence.verify(b), verify_evidence(b)):
        assert not check["ok"] and why in check["reason"]


def test_a_rehashed_forgery_fails_the_signature(tmp_path):
    b = _sealed(tmp_path)
    forged = evidence.chain([(e["kind"], e["body"]) for e in b["entries"]][:3] + [("sign_off", {"approver": "Mallory"})])
    b["entries"], b["head"] = forged, forged[-1]["hash"]                  # a perfectly consistent chain, re-hashed
    assert evidence.verify(b)["reason"] == "the signature doesn't match"


def test_a_record_signed_by_another_server_is_refused(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    b = json.loads(json.dumps(evidence.seal(STEPS, other)))
    assert evidence.verify(b)["ok"]                                      # self-consistent...
    trusted = evidence.public_key(tmp_path)["public_key"]
    assert evidence.verify(b, trusted)["reason"] == "signed by a different key than the one you trust"


@needs_docker
def test_the_downloaded_evidence_of_a_real_run_verifies(fresh_business, monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_KEY", "")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "rename one customer", "code":
                   "def run(ctx):\n    ctx.db.execute(\"UPDATE customers SET name = 'Ana B' WHERE id = 1\")\n"}).json()["id"]
    for _ in range(200):
        if api.get(f"/api/runs/{rid}").json()["status"] == "review":
            break
        time.sleep(0.25)
    run = api.get(f"/api/runs/{rid}").json()
    assert run["decision"]["layers"][1]["status"] == "pass"              # proof of effect
    api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"})
    ev = api.get(f"/api/runs/{rid}/evidence").json()
    assert [e["kind"] for e in ev["chain"]["entries"]] == ["request", "rehearsal", "decision", "sign_off", "applied"]
    assert api.post("/api/evidence/verify", json=ev).json()["ok"]
    bad = copy.deepcopy(ev)
    bad["chain"]["entries"][3]["body"]["approval"]["approver"] = "Someone else"
    assert api.post("/api/evidence/verify", json=bad).json()["ok"] is False


def test_sealed_bodies_hash_the_same_in_any_language(tmp_path):
    b = evidence.seal([("x", {"at": 1793883894.4790456, "whole": 5.0, "tiny": 1e-05, "n": 3})], tmp_path)
    body = b["entries"][0]["body"]
    assert body == {"at": "1793883894.4790456", "whole": 5, "tiny": "1e-05", "n": 3}   # no floats: JavaScript would print them differently
    assert evidence.verify(json.loads(json.dumps(b)))["ok"]


def test_health_reports_disk_headroom():
    from fastapi.testclient import TestClient
    from app import main
    h = TestClient(main.app).get("/api/health").json()
    assert h["disk_free_gb"] is None or h["disk_free_gb"] >= 0
    assert h["demo"]["state"] == "pristine" or h["demo"]["state"].startswith("changed")


def test_demo_heals_itself_when_changed_and_idle(fresh_business, monkeypatch):
    """A visitor approves refunds and learns a rule, then leaves: once idle, the demo business is back to its seed."""
    import sqlite3
    import time
    from app import beanpay, config, connectors, main, rules
    rules.reset()
    connectors.reset()
    assert main._demo_changed() == []
    db = connectors._outbox()                                                # an "approval needed" notification
    db.execute("INSERT INTO deliveries (connector, method, path, body, run_id, created_at, status) VALUES "
               "('slack', 'POST', '/stunt-double/notify', '{}', 'run_x', '2026-11-06', 200)")
    db.commit()
    assert main._demo_changed() == []                                        # is not a change to the business
    db = sqlite3.connect(config.PROD_DB)
    db.execute("UPDATE charges SET status = 'refunded' WHERE id = (SELECT MIN(id) FROM charges)")
    db.commit()
    db.close()
    rules.PATH.write_text('[{"id": "r1", "workspace": "demo", "title": "t", "sql": "SELECT 1"}]')
    assert set(main._demo_changed()) == {"data", "learned rules"}
    monkeypatch.setattr(config, "DEMO_IDLE_RESTORE_SECONDS", 1800)
    main.LAST_WRITE["t"] = time.time()
    assert main._demo_guard_tick() is False                                  # someone is still here: leave it alone
    assert main.DEMO_GUARD["state"].startswith("changed")
    main.LAST_WRITE["t"] = time.time() - 3600
    with main.LOCK:
        main.RUNS.clear()
    assert main._demo_guard_tick() is True                                   # idle for an hour: restored
    assert main._demo_changed() == [] and beanpay.ledger(0)["count"] == 0 and rules.all_rules() == []
    assert main.DEMO_GUARD["state"] == "pristine"
