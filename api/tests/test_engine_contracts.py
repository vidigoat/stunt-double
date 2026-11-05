"""Intent Contracts: written from the request alone, before any plan; checked with no AI; enforced against the plan.

The model is faked here with the kind of contract a real one writes (see docs/ENGINE.md for live results)."""
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import config, main
from app.engine import contracts
from tests.conftest import needs_docker

PLANS = json.loads((Path(__file__).parent / "refund_plans.json").read_text())

EXTRA = ("WITH lw AS (SELECT id, order_id FROM before.charges WHERE status = 'succeeded' AND created_at >= '2026-10-26' "
         "AND created_at < '2026-11-02'), dup AS (SELECT order_id FROM lw GROUP BY order_id HAVING COUNT(*) >= 2), "
         "extra AS (SELECT lw.id FROM lw JOIN dup USING (order_id) WHERE lw.id NOT IN (SELECT MIN(id) FROM lw GROUP BY order_id)) ")
WORK = {"text": "Every extra charge on last week's double-charged orders is refunded.",
        "sql": EXTRA + "SELECT e.id FROM extra e WHERE e.id NOT IN (SELECT charge_id FROM sent.refunds)"}
GUARD = {"text": "No other charge is refunded or changed.",
         "sql": EXTRA + "SELECT c.id FROM charges c JOIN before.charges b ON b.id = c.id WHERE (c.status IS NOT b.status "
                "OR c.refunded_at IS NOT b.refunded_at) AND c.id NOT IN (SELECT id FROM extra) "
                "UNION SELECT charge_id FROM sent.refunds WHERE charge_id NOT IN (SELECT id FROM extra)"}
UNFAIR = {"text": "Nothing is refunded at all.", "sql": "SELECT charge_id FROM sent.refunds"}
CLOCK = {"text": "Only today's charges change.", "sql": "SELECT id FROM charges WHERE created_at > date('now')"}


class FakeModel:
    """Stands in for Vultr Serverless Inference: answers with a fixed contract and counts the calls."""

    def __init__(self, promises):
        self.promises, self.calls = promises, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.calls += 1
        assert "Today is Tuesday 2026-11-03" in kw["messages"][0]["content"]          # grounded in the business's date
        args = json.dumps({"promises": self.promises})
        call = SimpleNamespace(function=SimpleNamespace(arguments=args))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call], content=None))])


def _compile(fresh_business, tmp_path, promises):
    model = FakeModel(promises)
    c = contracts.compile_contract(PLANS["bad"]["task"], [], fresh_business, ["fake"], model, tmp_path, today="Tuesday 2026-11-03")
    return c, model


def test_promises_sort_themselves_on_todays_data(fresh_business, tmp_path):
    c, _ = _compile(fresh_business, tmp_path, [WORK, GUARD, CLOCK, {"text": "x", "sql": "DELETE FROM charges"}])
    kinds = [(p["kind"], p["today"]) for p in c["promises"]]
    assert kinds == [("obligation", 104), ("guard", 0)]          # the clock-dependent and the writing ones are refused


def test_the_same_request_is_never_compiled_twice(fresh_business, tmp_path):
    _, model = _compile(fresh_business, tmp_path, [WORK, GUARD])
    c, again = _compile(fresh_business, tmp_path, [WORK, GUARD])
    assert again.calls == 0 and c["cached"] and len(c["promises"]) == 2


def test_a_thin_contract_asks_the_next_model(fresh_business, tmp_path):
    thin, full = FakeModel([WORK]), FakeModel([WORK, GUARD])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: (thin if kw["model"] == "a" else full).create(**kw))))
    c = contracts.compile_contract(PLANS["bad"]["task"], [], fresh_business, ["a", "b"], client, tmp_path, today="Tuesday 2026-11-03")
    assert c["model"] == "b" and len(c["promises"]) == 2 and thin.calls == full.calls == 1


def test_an_unchecked_promise_is_never_counted_as_kept():
    from app.engine import verdict
    run = {"status": "review", "verdict": None, "attempts": [{"n": 1, "flags": [], "consequences": {"ok": True, "contract": {"promises": [
        {"text": "Nothing else", "kind": "guard", "today": 0, "after": None, "status": "unknown"}]}}}]}
    layer = verdict.decide(run)["layers"][2]
    assert layer["status"] == "warn" and "Couldn't check" in layer["reason"]


def test_a_promise_a_correct_plan_fails_is_withdrawn(fresh_business, tmp_path):
    c, _ = _compile(fresh_business, tmp_path, [WORK, GUARD, UNFAIR])
    db = sqlite3.connect(fresh_business)
    extra = db.execute(EXTRA.replace("before.", "") + "SELECT c.id, c.amount_cents FROM charges c JOIN extra USING (id)").fetchall()
    db.close()
    good = {"changes": {}, "payments": [{"charge_id": i, "amount_cents": a} for i, a in extra], "emails": [], "http": []}
    assert len(extra) == 104
    kept, gone = contracts.withdraw_unfair(c["promises"], fresh_business, [good])
    assert [p["text"] for p in gone] == [UNFAIR["text"]] and len(kept) == 2


# ---- through the real sandbox: the bad plan breaks its contract, and the contract cuts it -----------------------
def _wait(api, rid):
    for _ in range(400):
        r = api.get(f"/api/runs/{rid}").json()
        if r["status"] in ("review", "failed", "applied") and (r["status"] != "review" or r.get("verdict")):
            return r
        time.sleep(0.25)
    return r


def _ai(monkeypatch, promises):
    def fake_verify(task, code, consequences, emit, models=None, vision=True):
        ok = consequences.get("payments", {}).get("count") == 104
        return {"verdict": "looks_right" if ok else "concerns", "headline": "checked", "summary": "", "concerns": []}
    monkeypatch.setattr(config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(config, "CONTRACT_MODELS", ["fake"])
    monkeypatch.setattr(main.agent, "verify", fake_verify)
    monkeypatch.setattr(main.agent, "client", lambda: FakeModel(promises))
    monkeypatch.setattr(main, "_verify_budget", lambda: True)


@needs_docker
def test_the_bad_plan_breaks_its_contract_and_the_contract_cuts_it(fresh_business, monkeypatch):
    _ai(monkeypatch, [WORK, GUARD])
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    run = _wait(api, rid)
    assert run["contract"]["status"] == "ready"
    res = {p["text"]: p for p in run["attempts"][-1]["consequences"]["contract"]["promises"]}
    assert res[GUARD["text"]]["status"] == "broken" and res[GUARD["text"]]["after"] == 640
    assert res[WORK["text"]]["status"] == "met"                     # it did the work, and much more
    flag = next(f for f in run["attempts"][-1]["flags"] if f["rule"] == "contract")
    assert flag["severity"] == "critical" and run["verdict"]["verdict"] == "dangerous"   # stricter than the jury's "concerns"

    assert run["surgical"]["check"]["source"] == "intent contract"   # no learned rule, so the contract's guard does the cut
    assert run["surgical"]["offer"]["units_kept"] == 104
    main.CONTRACT_READY.clear()                                     # as after a restart: the contract on the run still counts
    api.post(f"/api/runs/{rid}/surgical")
    run = _wait(api, rid)
    after = {p["text"]: p["status"] for p in run["attempts"][-1]["consequences"]["contract"]["promises"]}
    assert after == {WORK["text"]: "met", GUARD["text"]: "kept"}
    assert run["verdict"]["verdict"] == "looks_right"


@needs_docker
def test_a_plan_that_does_half_the_work_leaves_an_obligation_unmet(fresh_business, monkeypatch):
    _ai(monkeypatch, [WORK, GUARD])
    code = ("def run(ctx):\n    rows = ctx.db.execute(\"SELECT c.id, c.amount_cents FROM charges c WHERE c.status = 'succeeded' "
            "AND c.created_at >= '2026-10-26' AND c.created_at < '2026-11-02' AND c.id NOT IN (SELECT MIN(id) FROM charges "
            "GROUP BY order_id) AND c.order_id IN (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1) "
            "ORDER BY c.id LIMIT 50\").fetchall()\n"
            "    for cid, amt in rows:\n        ctx.payments.refund(cid, amt, 'double charge')\n")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": code}).json()["id"]
    run = _wait(api, rid)
    res = {p["text"]: p for p in run["attempts"][-1]["consequences"]["contract"]["promises"]}
    assert res[WORK["text"]]["status"] == "unmet" and res[WORK["text"]]["after"] == 54
    assert res[GUARD["text"]]["status"] == "kept"
    assert any(f["rule"] == "contract" and f["severity"] == "high" for f in run["attempts"][-1]["flags"])


@needs_docker
def test_a_read_only_request_never_gets_a_subset_offer(fresh_business, monkeypatch):
    # the lying "audit": it changes 300 charges, some of them outside last week. Each broken promise alone could be cut
    # around; together, and with no work asked for, nothing of this plan is worth approving.
    last_week = {"text": "Last week's charges come out of the audit unchanged.",
                 "sql": "SELECT c.id FROM charges c JOIN before.charges b ON b.id = c.id WHERE b.created_at >= '2026-10-26' "
                        "AND b.created_at < '2026-11-02' AND (c.status IS NOT b.status OR c.refunded_at IS NOT b.refunded_at)"}
    nothing = {"text": "The audit changes nothing at all.",
               "sql": "SELECT c.id FROM charges c JOIN before.charges b ON b.id = c.id WHERE c.status IS NOT b.status"}
    _ai(monkeypatch, [last_week, nothing])
    code = ("def run(ctx):\n    ctx.db.execute(\"UPDATE charges SET status = 'refunded' WHERE id IN "
            "(SELECT id FROM charges ORDER BY created_at DESC LIMIT 150) OR id IN (SELECT id FROM charges ORDER BY created_at LIMIT 150)\")\n    ctx.log('Read-only audit: nothing changed.')\n")
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": "Audit last week's charges. Read only: change nothing.", "code": code}).json()["id"]
    run = _wait(api, rid)
    assert [p["status"] for p in run["attempts"][-1]["consequences"]["contract"]["promises"]] == ["broken", "broken"]
    assert "offer" not in run["surgical"] and run["decision"]["decision"] == "blocked"


def test_the_indexed_copy_follows_the_data(tmp_path):
    from app.engine import state
    src = tmp_path / "b.db"
    db = sqlite3.connect(src)
    db.execute("CREATE TABLE charges (id INTEGER PRIMARY KEY, order_id INTEGER, created_at TEXT, status TEXT)")
    db.execute("INSERT INTO charges VALUES (1, 7, '2026-10-27', 'succeeded')")
    db.commit()
    first = state.indexed(src)
    assert state.indexed(src) == first                                       # reused while the data is the same
    idx = {r[0] for r in sqlite3.connect(first).execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"sd_charges_order_id", "sd_charges_created_at"} <= idx and "sd_charges_status" not in idx
    time.sleep(0.01)
    db.execute("INSERT INTO charges VALUES (2, 8, '2026-10-28', 'succeeded')")
    db.commit()
    db.close()
    second = state.indexed(src)
    assert second != first and sqlite3.connect(second).execute("SELECT COUNT(*) FROM charges").fetchone()[0] == 2
    assert not sqlite3.connect(src).execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'").fetchone()[0]  # the real data: untouched


@needs_docker
def test_a_person_can_strike_a_promise_and_the_record_says_who_and_why(fresh_business, monkeypatch):
    _ai(monkeypatch, [WORK, GUARD])
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    run = _wait(api, rid)
    assert run["decision"]["decision"] == "cut" and run["verdict"]["verdict"] == "dangerous"      # raised by the broken guard
    assert api.post(f"/api/runs/{rid}/contract/strike", json={"index": 1, "reason": "no"}).status_code == 422   # a reason is required
    r = api.post(f"/api/runs/{rid}/contract/strike", json={"index": 1, "by": "Priya", "reason": "We also refund same-day repeat orders"})
    run = r.json()
    assert [p["text"] for p in run["attempts"][-1]["consequences"]["contract"]["promises"]] == [WORK["text"]]
    assert not any(f["rule"] == "contract" for f in run["attempts"][-1]["flags"])
    assert run["verdict"]["verdict"] == "concerns"                     # the jury's own verdict is back
    assert run["decision"]["decision"] == "review" and "1 struck by Priya" in run["decision"]["layers"][2]["reason"]
    assert "offer" not in (run.get("surgical") or {})
    assert api.post(f"/api/runs/{rid}/contract/strike", json={"index": 0, "reason": "the last one goes too"}).status_code == 409
    ev = api.get(f"/api/runs/{rid}/evidence").json()
    struck = next(e for e in ev["chain"]["entries"] if e["kind"] == "contract_struck")["body"]
    assert struck[0]["by"] == "Priya" and struck[0]["reason"] == "We also refund same-day repeat orders"
    assert api.post("/api/evidence/verify", json=ev).json()["ok"]


def test_two_readings_are_compared_by_how_much_work_they_find():
    w = lambda n: {"kind": "obligation", "today": n}  # noqa: E731
    g = {"kind": "guard", "today": 0}
    assert contracts.cross_check([w(104), w(104), g], [w(104), g])["status"] == "agree"
    assert contracts.cross_check([w(104)], [w(58)]) == {"status": "disagree", "ours": 104, "theirs": 58}
    assert contracts.cross_check([g], [w(3)])["status"] == "disagree"


@needs_docker
def test_an_ambiguous_request_is_flagged_before_anyone_trusts_either_reading(fresh_business, monkeypatch):
    seven_days = {"text": "Every extra charge from the last seven days is refunded.",
                  "sql": WORK["sql"].replace("created_at >= '2026-10-26'", "created_at >= '2026-10-29'")}
    by_model = {"a": FakeModel([WORK, GUARD]), "b": FakeModel([seven_days, GUARD])}
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: by_model[kw["model"]].create(**kw))))
    _ai(monkeypatch, [])
    monkeypatch.setattr(config, "CONTRACT_MODELS", ["a", "b"])
    monkeypatch.setattr(main.agent, "client", lambda: client)
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["good"]["task"], "code": PLANS["good"]["code"]}).json()["id"]
    run = _wait(api, rid)
    for _ in range(40):
        if (run.get("contract") or {}).get("cross_check"):
            break
        time.sleep(0.25)
        run = api.get(f"/api/runs/{rid}").json()
    cc = run["contract"]["cross_check"]
    assert cc == {"model": "b", "status": "disagree", "ours": 104, "theirs": 58, "second_reading": 58}   # it reproduced
    assert run["decision"]["layers"][2]["status"] == "warn" and "104 to do, or 58" in run["decision"]["layers"][2]["reason"]
    assert run["decision"]["decision"] == "review"           # the correct plan, but the request itself needs a person


@needs_docker
def test_when_the_contract_and_the_jury_disagree_a_person_decides_with_a_reason(fresh_business, monkeypatch):
    _ai(monkeypatch, [WORK, GUARD])
    monkeypatch.setattr(main.agent, "verify", lambda *a, **k: {"verdict": "looks_right", "headline": "fine", "summary": "", "concerns": []})
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"]}).json()["id"]
    run = _wait(api, rid)
    flag = next(f for f in run["attempts"][-1]["flags"] if f["rule"] == "contract")
    assert flag["severity"] == "high" and "strike the promise" in flag["detail"]          # not a lock: two AI readings disagree
    assert run["verdict"]["verdict"] == "looks_right" and run["decision"]["decision"] == "cut"   # the cut is still offered
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya"})
    assert r.status_code == 422 and "promise" in r.json()["detail"]                       # but approving the whole needs a reason
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya", "note": "Same-day repeat orders are refunded by our policy"})
    assert r.status_code == 200 and len(r.json()["approvals"]) == 1                    # accepted with a reason (and $37k needs a second person)


def test_the_jury_reads_the_outcome_without_the_contract():
    from app import agent
    c = {"ok": True, "tables": {}, "payments": {"count": 0, "total_cents": 0, "samples": []}, "emails": {"count": 0, "samples": []},
         "contract": {"promises": [{"text": "x", "kind": "guard", "status": "broken", "today": 0, "after": 3}]}}
    assert "intent_contract" in agent.compact_consequences(c)                     # the ops agent sees it, to fix its plan
    assert "intent_contract" not in agent.compact_consequences(c, contract=False)  # the jury doesn't: two independent readings
    src = Path(agent.__file__).read_text()
    assert "compact_consequences(consequences, contract=False)" in src


@needs_docker
def test_the_agent_plans_against_the_contract(fresh_business, monkeypatch):
    _ai(monkeypatch, [WORK, GUARD])
    seen = {}

    def fake_agent(task, rehearse, emit, feedback=None, history=None):
        seen["task"] = task
        rehearse(PLANS["good"]["code"], "refund the 104")
        return "done", []
    monkeypatch.setattr(main.agent, "ops_agent", fake_agent)
    api = TestClient(main.app)
    rid = api.post("/api/runs", json={"task": PLANS["good"]["task"]}).json()["id"]
    run = _wait(api, rid)
    assert WORK["text"] in seen["task"] and GUARD["text"] in seen["task"] and seen["task"].startswith(PLANS["good"]["task"])
    assert run["task"] == PLANS["good"]["task"]                  # the jury still judges the person's own words
    assert run["decision"]["layers"][2]["status"] == "pass"



@needs_docker
def test_a_disagreement_that_does_not_reproduce_is_noise(fresh_business, monkeypatch):
    seven_days = {"text": "Every extra charge from the last seven days is refunded.",
                  "sql": WORK["sql"].replace("created_at >= '2026-10-26'", "created_at >= '2026-10-29'")}
    readings = iter([[seven_days, GUARD], [WORK, GUARD]])             # b misreads once, then reads it like a
    a = FakeModel([WORK, GUARD])
    b = SimpleNamespace(create=lambda **kw: FakeModel(next(readings)).create(**kw))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: (a if kw["model"] == "a" else b).create(**kw))))
    _ai(monkeypatch, [])
    monkeypatch.setattr(config, "CONTRACT_MODELS", ["a", "b"])
    monkeypatch.setattr(main.agent, "client", lambda: client)
    api = TestClient(main.app)
    rid = api.post("/api/runs/manual", json={"task": PLANS["good"]["task"], "code": PLANS["good"]["code"]}).json()["id"]
    run = _wait(api, rid)
    for _ in range(40):
        if (run.get("contract") or {}).get("cross_check"):
            break
        time.sleep(0.25)
        run = api.get(f"/api/runs/{rid}").json()
    assert run["contract"]["cross_check"] == {"model": "b", "status": "agree", "ours": 104, "theirs": 104, "first_reading": 58}
    assert run["decision"]["decision"] == "approve"


def test_what_does_this_mean_shows_the_contract_before_any_plan_and_the_run_reuses_it(fresh_business, monkeypatch):
    a, b = FakeModel([WORK, GUARD]), FakeModel([WORK, GUARD])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: (a if kw["model"] == "a" else b).create(**kw))))
    monkeypatch.setattr(config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(config, "CONTRACT_MODELS", ["a", "b"])
    monkeypatch.setattr(main.agent, "client", lambda: client)
    api = TestClient(main.app)
    r = api.post("/api/contract/preview", json={"task": PLANS["bad"]["task"]}).json()
    assert [(p["kind"], p["today"]) for p in r["promises"]] == [("obligation", 104), ("guard", 0)]
    assert r["cross_check"] == {"model": "b", "status": "agree", "ours": 104, "theirs": 104}
    calls = (a.calls, b.calls)
    again = api.post("/api/contract/preview", json={"task": PLANS["bad"]["task"]}).json()
    assert again["cached"] and (a.calls, b.calls) == calls                       # asked once, remembered
