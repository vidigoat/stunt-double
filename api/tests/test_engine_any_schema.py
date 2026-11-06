"""The Consequence Engine on a business it was never built or tuned for: Brightpath Academy, an online school with its
own schema (students, courses, enrollments, withdrawal requests). Nothing in the engine knows these tables. The bad plan
cancels every withdrawal request filed this week, including 22 from students who changed their mind; the engine must
prove every change, catch it, and cut it to exactly the 41 that are right. The model is faked with the kind of contract
a real one writes for this schema; the live results are in docs/BEYOND_THE_DEMO.md."""
import time

from fastapi.testclient import TestClient

from app import config, main
from eval.brightpath import PLANS, build
from tests.conftest import needs_docker
from tests.test_engine_contracts import FakeModel

THIS_WEEK = ("SELECT w.student_id, w.course_id FROM before.withdrawal_requests w "
             "WHERE w.created_at >= '2026-11-02' AND w.status = 'pending'")
WORK = {"text": "Every enrollment a student asked to leave this week, and still wants to, is cancelled.",
        "sql": "SELECT e.id FROM enrollments e JOIN (" + THIS_WEEK + ") p ON p.student_id = e.student_id AND p.course_id = e.course_id "
               "WHERE e.status != 'cancelled'"}
GUARD = {"text": "No other enrollment is cancelled: not one whose student withdrew the request, nor any other.",
         "sql": "SELECT e.id FROM enrollments e JOIN before.enrollments b ON b.id = e.id WHERE e.status = 'cancelled' "
                "AND b.status != 'cancelled' AND NOT EXISTS (SELECT 1 FROM (" + THIS_WEEK + ") p "
                "WHERE p.student_id = e.student_id AND p.course_id = e.course_id)"}


def _wait(api, rid, attempts=1):
    for _ in range(400):
        r = api.get(f"/api/runs/{rid}").json()
        if len(r["attempts"]) >= attempts and r["status"] in ("review", "failed") and (r["status"] != "review" or r.get("decision")):
            return r
        time.sleep(0.25)
    return r


@needs_docker
def test_the_engine_works_on_a_business_it_has_never_seen(fresh_business, monkeypatch, tmp_path):
    truth = build(tmp_path / "brightpath.db")
    assert truth == {"right": 41, "obvious": 63}
    monkeypatch.setattr(config, "INFERENCE_KEY", "set")
    monkeypatch.setattr(config, "CONTRACT_MODELS", ["fake"])
    monkeypatch.setattr(main.agent, "client", lambda: FakeModel([WORK, GUARD]))
    monkeypatch.setattr(main, "_verify_budget", lambda: True)

    def jury(task, code, consequences, emit, models=None, vision=True):
        n = sum(t["updated"] for t in consequences["tables"].values())
        return {"verdict": "looks_right" if n == truth["right"] else "dangerous", "headline": f"{n} cancelled", "summary": "", "concerns": []}
    monkeypatch.setattr(main.agent, "verify", jury)
    monkeypatch.setattr(main.engine_contracts, "compile_contract", _no_date_check(main.engine_contracts.compile_contract))

    api = TestClient(main.app)
    ws = api.post("/api/workspaces?name=Brightpath%20Academy", content=(tmp_path / "brightpath.db").read_bytes(),
                  headers={"content-type": "application/octet-stream"}).json()["id"]
    rid = api.post("/api/runs/manual", json={"task": PLANS["bad"]["task"], "code": PLANS["bad"]["code"], "workspace": ws}).json()["id"]
    run = _wait(api, rid)
    c = run["attempts"][-1]["consequences"]

    assert c["tables"]["enrollments"]["updated"] == 63                                  # what the obvious plan really did
    assert c["provenance"]["status"] == "proven" and c["provenance"]["rows_explained"] == 63   # every change has a reason
    assert c["graph"]["units"] == 63                                                    # one unit per cancelled enrollment
    res = {p["text"]: p for p in c["contract"]["promises"]}
    assert res[WORK["text"]]["today"] == 41 and res[WORK["text"]]["status"] == "met"
    assert res[GUARD["text"]]["status"] == "broken" and res[GUARD["text"]]["after"] == 22   # the students who stayed
    assert run["decision"]["decision"] == "cut" and run["surgical"]["offer"]["units_kept"] == 41

    api.post(f"/api/runs/{rid}/surgical")
    run = _wait(api, rid, attempts=2)
    sub = run["attempts"][-1]["consequences"]
    assert sub["tables"]["enrollments"]["updated"] == 41 and sub["provenance"]["status"] == "derived"
    assert {p["status"] for p in sub["contract"]["promises"]} == {"met", "kept"}
    assert run["decision"]["decision"] == "approve"
    ev = api.get(f"/api/runs/{rid}/evidence").json()
    assert api.post("/api/evidence/verify", json=ev).json()["ok"]


def _no_date_check(compile_contract):
    """The fake model checks for the demo business's date; this business uses the real one."""
    def wrapped(*a, **kw):
        kw["today"] = "Tuesday 2026-11-03"
        return compile_contract(*a, **kw)
    return wrapped
