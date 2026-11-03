"""Stunt Double API: plan -> dispatch -> verify -> approve -> apply."""
import json
import sqlite3
import subprocess
import threading
import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import agent, apply as applier, beanpay, config, sandbox, seed

app = FastAPI(title="Stunt Double API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

RUNS: dict[str, dict] = {}
HISTORY: dict[str, list] = {}           # ops-agent conversation per run (kept server-side)
LOCK = threading.Lock()
SANDBOX_SLOTS = threading.BoundedSemaphore(3)
RATE: dict[str, list[float]] = defaultdict(list)

if not config.PROD_DB.exists():
    seed.seed(config.PROD_DB)


# ---- helpers ---------------------------------------------------------------------------------------
def _new_run(task: str, mode: str) -> dict:
    rid = "run_" + uuid.uuid4().hex[:10]
    run = {"id": rid, "task": task, "mode": mode, "status": "queued", "created_at": time.time(), "events": [],
           "attempts": [], "verdict": None, "flags": [], "final_message": None, "apply_result": None, "error": None,
           "agent_model": config.AGENT_MODEL, "verifier_model": config.VERIFIER_MODEL}
    with LOCK:
        RUNS[rid] = run
    return run


def _emit(run: dict, kind: str, title: str, detail: str | None = None) -> None:
    with LOCK:
        run["events"].append({"t": time.time(), "kind": kind, "title": title, "detail": (detail or "")[:4000]})


def _status(run: dict, status: str) -> None:
    with LOCK:
        run["status"] = status


def _rehearse(run: dict, code: str, summary: str) -> dict:
    _status(run, "rehearsing")
    _emit(run, "sandbox", "Dispatching plan to an isolated sandbox", summary)
    with SANDBOX_SLOTS:
        res = sandbox.rehearse(code)
    c = res["consequences"]
    attempt = {"n": len(run["attempts"]) + 1, "sandbox_id": res["id"], "code": code, "summary": summary,
               "consequences": c, "flags": agent.red_flags(c), "effects_path": res["effects_path"]}
    with LOCK:
        run["attempts"].append(attempt)
    sb = c["sandbox"]
    _emit(run, "sandbox", f"Sandbox {res['id']} finished and was destroyed",
          f"ok={c['ok']} · {sb['wall_ms']} ms · network={sb['network']} · memory={sb['memory']} · runtime={sb['runtime']}")
    _status(run, "planning")
    return c


def _verify(run: dict) -> None:
    att = run["attempts"][-1]
    _status(run, "verifying")
    _emit(run, "verify", "Stunt Double is checking the consequences against your request")
    try:
        verdict = agent.verify(run["task"], att["code"], att["consequences"], lambda k, t, d=None: _emit(run, k, t, d))
    except Exception as e:  # noqa: BLE001
        verdict = {"verdict": "concerns", "headline": "Automatic review unavailable", "summary": str(e)[:300], "concerns": []}
    crit = [f for f in att["flags"] if f["severity"] == "critical"]
    if crit and verdict.get("verdict") != "dangerous":
        verdict["verdict"] = "dangerous"
    with LOCK:
        run["verdict"] = verdict
        run["flags"] = att["flags"]
    _emit(run, "verify", verdict.get("headline", "Review ready"))
    _status(run, "review")


def _agent_job(run: dict, feedback: str | None = None) -> None:
    try:
        _status(run, "planning")
        _emit(run, "agent", "Ops agent is planning" if not feedback else "Ops agent is fixing the plan")
        final, history = agent.ops_agent(run["task"], lambda code, s: _rehearse(run, code, s),
                                         lambda k, t, d=None: _emit(run, k, t, d), feedback=feedback, history=HISTORY.get(run["id"]))
        HISTORY[run["id"]] = history
        with LOCK:
            run["final_message"] = final
        if not run["attempts"]:
            raise RuntimeError("The agent did not submit a plan")
        _verify(run)
    except Exception as e:  # noqa: BLE001
        with LOCK:
            run["error"] = str(e)[:1000]
        _emit(run, "error", "Run failed", str(e))
        _status(run, "failed")


def _manual_job(run: dict, code: str) -> None:
    try:
        _rehearse(run, code, "Submitted plan")
        if config.INFERENCE_KEY:
            _verify(run)
        else:
            with LOCK:
                run["flags"] = run["attempts"][-1]["flags"]
            _status(run, "review")
    except Exception as e:  # noqa: BLE001
        with LOCK:
            run["error"] = str(e)[:1000]
        _status(run, "failed")


def _get(rid: str) -> dict:
    run = RUNS.get(rid)
    if not run:
        raise HTTPException(404, "run not found")
    return run


def _public(run: dict) -> dict:
    out = dict(run)
    out["attempts"] = [{k: v for k, v in a.items() if k != "effects_path"} for a in run["attempts"]]
    return out


def _rate_limit(req: Request, per_hour: int = 30) -> None:
    ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "?").split(",")[0].strip()
    now = time.time()
    RATE[ip] = [t for t in RATE[ip] if now - t < 3600]
    if len(RATE[ip]) >= per_hour:
        raise HTTPException(429, "Too many rehearsals from this address, try again later")
    RATE[ip].append(now)


# ---- API ----------------------------------------------------------------------------------------------
class TaskIn(BaseModel):
    task: str = Field(min_length=3, max_length=2000)


class ManualIn(TaskIn):
    code: str = Field(min_length=10, max_length=20000)


class FixIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@app.get("/api/health")
def health():
    docker = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True)
    return {"ok": True, "inference_configured": bool(config.INFERENCE_KEY), "agent_model": config.AGENT_MODEL,
            "verifier_model": config.VERIFIER_MODEL, "sandbox_runtime": config.SANDBOX_RUNTIME or "runc",
            "docker": docker.stdout.strip() or None}


@app.get("/api/business")
def business():
    db = sqlite3.connect(f"file:{config.PROD_DB}?mode=ro", uri=True)
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("customers", "orders", "charges", "tickets")}
    refunded = db.execute("SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM charges WHERE status='refunded'").fetchone()
    tickets = db.execute("SELECT t.id, c.name, t.subject, t.created_at FROM tickets t JOIN customers c ON c.id=t.customer_id "
                         "ORDER BY t.created_at DESC LIMIT 8").fetchall()
    return {"name": "Bean There Coffee Co.", "counts": counts, "refunded": {"count": refunded[0], "total_cents": refunded[1]},
            "recent_tickets": [dict(zip(["id", "customer", "subject", "created_at"], r)) for r in tickets],
            "beanpay": {k: v for k, v in beanpay.ledger(0).items() if k != "refunds"}}


@app.post("/api/runs")
def create_run(body: TaskIn, req: Request):
    _rate_limit(req)
    run = _new_run(body.task, "agent")
    threading.Thread(target=_agent_job, args=(run,), daemon=True).start()
    return {"id": run["id"]}


@app.post("/api/runs/manual")
def create_manual_run(body: ManualIn, req: Request):
    _rate_limit(req)
    run = _new_run(body.task, "manual")
    threading.Thread(target=_manual_job, args=(run, body.code), daemon=True).start()
    return {"id": run["id"]}


@app.get("/api/runs")
def list_runs():
    return [{"id": r["id"], "task": r["task"], "status": r["status"], "created_at": r["created_at"]}
            for r in sorted(RUNS.values(), key=lambda r: -r["created_at"])[:50]]


@app.get("/api/runs/{rid}")
def get_run(rid: str):
    return _public(_get(rid))


@app.post("/api/runs/{rid}/fix")
def fix_run(rid: str, body: FixIn):
    run = _get(rid)
    if run["status"] != "review" or run["mode"] != "agent":
        raise HTTPException(409, "Only an agent run under review can be fixed")
    v = run.get("verdict") or {}
    feedback = "\n".join(filter(None, [v.get("fix_instructions"), *[f"- {c['title']}: {c['detail']}" for c in v.get("concerns", [])], body.note]))
    with LOCK:
        run["verdict"] = None
    threading.Thread(target=_agent_job, args=(run, feedback or "Please double-check the plan."), daemon=True).start()
    return {"id": rid}


@app.post("/api/runs/{rid}/reject")
def reject_run(rid: str):
    run = _get(rid)
    _status(run, "rejected")
    _emit(run, "human", "Rejected by approver. Nothing was changed.")
    return _public(run)


@app.post("/api/runs/{rid}/approve")
def approve_run(rid: str):
    run = _get(rid)
    if run["status"] != "review":
        raise HTTPException(409, f"Run is {run['status']}, not awaiting review")
    att = run["attempts"][-1]
    if not att["consequences"].get("ok"):
        raise HTTPException(409, "A plan that crashed in rehearsal cannot be applied")
    if any(f["severity"] == "critical" for f in att["flags"]):
        raise HTTPException(409, "Blocked by policy: critical blast radius. Ask the agent to fix it or reject.")
    _status(run, "applying")
    _emit(run, "human", "Approved. Running the drift check, then applying the approved changes for real")
    try:
        result = applier.apply(rid, att["effects_path"])
    except applier.DriftError as e:
        with LOCK:
            run["apply_result"] = {"drifted": e.drifted[:20], "drift_count": len(e.drifted)}
        _emit(run, "drift", f"Drift detected: {len(e.drifted)} rows changed since the rehearsal. Nothing applied.")
        _status(run, "drifted")
        return _public(run)
    with LOCK:
        run["apply_result"] = result
    _emit(run, "applied", f"Applied: {result['refunds']} refunds (${result['refund_total_cents'] / 100:,.2f}), "
                          f"{result['emails_sent']} emails, {result['rows_written']} rows")
    _status(run, "applied")
    return _public(run)


@app.get("/api/beanpay/ledger")
def ledger():
    return beanpay.ledger()


@app.post("/api/demo/reset")
def reset(req: Request):
    _rate_limit(req, per_hour=20)
    seed.seed(config.PROD_DB)
    beanpay.reset()
    return {"ok": True, **business()}
