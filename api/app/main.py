"""Stunt Double API: plan -> dispatch -> verify -> approve -> apply."""
import asyncio
import hashlib
import json
import sqlite3
import subprocess
import threading
import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import agent, archive, beanpay, config, policy, sandbox, seed
from . import apply as applier

app = FastAPI(
    title="Stunt Double API",
    description="Rehearse AI agent actions on a throwaway copy of the business, verify the consequences, approve, then apply.",
    version="1.0.0", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

RUNS: dict[str, dict] = {}
HISTORY: dict[str, list] = {}           # ops-agent conversation per run (kept server-side)
LOCK = threading.Lock()
SANDBOX_SLOTS = threading.BoundedSemaphore(3)
RATE: dict[str, list[float]] = defaultdict(list)
AGENT_DAY: dict[str, int] = {"day": "", "count": 0}

HISTORY_DIR = config.DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE = {"queued", "planning", "rehearsing", "verifying", "applying"}

if not config.PROD_DB.exists():
    seed.seed(config.PROD_DB)


def _save(run: dict) -> None:
    """Persist a run (history + audit trail survive restarts). Caller holds LOCK."""
    run["version"] = run.get("version", 0) + 1
    tmp = HISTORY_DIR / f"{run['id']}.json.tmp"
    tmp.write_text(json.dumps(run, default=str))
    tmp.replace(HISTORY_DIR / f"{run['id']}.json")


def _load_history() -> None:
    for f in sorted(HISTORY_DIR.glob("run_*.json")):
        try:
            run = json.loads(f.read_text())
        except ValueError:
            continue
        if run.get("status") in ACTIVE:
            run["status"], run["error"] = "failed", "Interrupted by a server restart"
        RUNS[run["id"]] = run


_load_history()
try:
    sandbox.cleanup_orphans(keep={a["sandbox_id"] for r in RUNS.values() if r["status"] == "review" for a in r["attempts"]})
except OSError:
    pass


# ---- helpers ---------------------------------------------------------------------------------------
def _new_run(task: str, mode: str) -> dict:
    rid = "run_" + uuid.uuid4().hex[:10]
    run = {"id": rid, "task": task, "mode": mode, "status": "queued", "created_at": time.time(), "events": [],
           "attempts": [], "verdict": None, "flags": [], "final_message": None, "apply_result": None, "error": None,
           "agent_model": config.AGENT_MODEL.split(",")[0], "verifier_model": config.VERIFIER_MODEL.split(",")[0]}
    with LOCK:
        RUNS[rid] = run
        _save(run)
    return run


def _emit(run: dict, kind: str, title: str, detail: str | None = None) -> None:
    with LOCK:
        run["events"].append({"t": time.time(), "kind": kind, "title": title, "detail": (detail or "")[:4000]})
        _save(run)


def _status(run: dict, status: str) -> None:
    with LOCK:
        run["status"] = status
        _save(run)


def _rehearse(run: dict, code: str, summary: str) -> dict:
    _status(run, "rehearsing")
    _emit(run, "sandbox", "Dispatching plan to an isolated sandbox", summary)
    with SANDBOX_SLOTS:
        res = sandbox.rehearse(code)
    c = res["consequences"]
    effects = open(res["effects_path"], "rb").read() if c.get("ok") else b""
    attempt = {"n": len(run["attempts"]) + 1, "sandbox_id": res["id"], "code": code, "summary": summary,
               "consequences": c, "flags": agent.red_flags(c), "effects_path": res["effects_path"],
               "plan_sha256": hashlib.sha256(code.encode()).hexdigest(), "effects_sha256": hashlib.sha256(effects).hexdigest() if effects else None,
               "created_at": time.time()}
    with LOCK:
        run["attempts"].append(attempt)
        _save(run)
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


class ApproveIn(BaseModel):
    approver: str | None = Field(default=None, max_length=80)


class FixIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


def _sandbox_ready() -> tuple[bool, str]:
    """Is the configured sandbox runtime actually available? Rehearsals fail closed if not."""
    p = subprocess.run(["docker", "info", "--format", "{{json .Runtimes}}"], capture_output=True, text=True)
    if p.returncode != 0:
        return False, "Docker daemon unreachable"
    want = config.SANDBOX_RUNTIME or "runc"
    try:
        runtimes = json.loads(p.stdout or "{}")
    except ValueError:
        runtimes = {}
    if want not in runtimes and want != "runc":
        return False, f"sandbox runtime '{want}' is not installed (rehearsals will refuse to run)"
    return True, f"{want} ready"


@app.get("/api/health")
def health():
    ready, why = _sandbox_ready()
    docker = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True)
    return {"ok": True, "inference_configured": bool(config.INFERENCE_KEY), "agent_model": config.AGENT_MODEL.split(",")[0],
            "verifier_model": config.VERIFIER_MODEL.split(",")[0], "fallback_models": config.AGENT_MODEL.split(",")[1:],
            "agent_runs_today": AGENT_DAY["count"] if AGENT_DAY["day"] == time.strftime("%Y-%m-%d", time.gmtime()) else 0,
            "agent_runs_daily_limit": config.DAILY_AGENT_RUNS, "sandbox_runtime": config.SANDBOX_RUNTIME or "runc",
            "docker": docker.stdout.strip() or None, "sandbox_ready": ready, "sandbox_status": why,
            "evidence_archive": f"vultr-object-storage:{archive.BUCKET}" if archive.enabled() else None}


@app.get("/api/business")
def business():
    db = sqlite3.connect(f"file:{config.PROD_DB}?mode=ro", uri=True)
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("customers", "orders", "charges", "tickets")}
    refunded = db.execute("SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM charges WHERE status='refunded'").fetchone()
    tickets = db.execute("SELECT t.id, c.name, t.subject, t.created_at FROM tickets t JOIN customers c ON c.id=t.customer_id "
                         "ORDER BY t.created_at DESC LIMIT 8").fetchall()
    return {"name": "Bean There Coffee Co.", "counts": counts, "refunded": {"count": refunded[0], "total_cents": refunded[1]},
            "recent_tickets": [dict(zip(["id", "customer", "subject", "created_at"], r, strict=False)) for r in tickets],
            "beanpay": {k: v for k, v in beanpay.ledger(0).items() if k != "refunds"}}


def _agent_budget() -> None:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with LOCK:
        if AGENT_DAY["day"] != day:
            AGENT_DAY.update(day=day, count=0)
        if AGENT_DAY["count"] >= config.DAILY_AGENT_RUNS:
            raise HTTPException(429, "Today's AI-agent budget for this public demo is used up. 'Break it yourself' still works.")
        AGENT_DAY["count"] += 1


@app.post("/api/runs")
def create_run(body: TaskIn, req: Request):
    _rate_limit(req)
    if not config.INFERENCE_KEY:
        raise HTTPException(503, "The AI agent is offline: Vultr Serverless Inference is not configured on this server")
    _agent_budget()
    run = _new_run(body.task, "agent")
    threading.Thread(target=_agent_job, args=(run,), daemon=True).start()
    return {"id": run["id"]}


@app.post("/api/runs/manual")
def create_manual_run(body: ManualIn, req: Request):
    _rate_limit(req)
    run = _new_run(body.task, "manual")
    threading.Thread(target=_manual_job, args=(run, body.code), daemon=True).start()
    return {"id": run["id"]}


def _summary(r: dict) -> dict:
    a = r["attempts"][-1] if r["attempts"] else None
    c = a["consequences"] if a else {}
    return {"id": r["id"], "task": r["task"], "mode": r["mode"], "status": r["status"], "created_at": r["created_at"],
            "attempts": len(r["attempts"]), "verdict": (r.get("verdict") or {}).get("verdict"),
            "money_cents": c.get("payments", {}).get("total_cents", 0), "emails": c.get("emails", {}).get("count", 0),
            "rows": sum(t["deleted"] + t["updated"] + t["inserted"] for t in c.get("tables", {}).values()),
            "blocked": any(f["severity"] == "critical" for f in (a or {}).get("flags", [])),
            "plan_sha256": (a or {}).get("plan_sha256"), "approval": r.get("approval"), "apply_result": r.get("apply_result")}


@app.get("/api/runs")
def list_runs():
    return [_summary(r) for r in sorted(RUNS.values(), key=lambda r: -r["created_at"])[:100]]


@app.get("/api/runs/{rid}/stream")
async def stream_run(rid: str, request: Request):
    """Server-sent events: the full run every time it changes; ends when the run is no longer active."""
    _get(rid)

    async def events():
        seen, idle = -1, 0.0
        while not await request.is_disconnected():
            run = RUNS[rid]
            if run.get("version", 0) != seen:
                seen = run.get("version", 0)
                with LOCK:
                    payload = json.dumps(_public(run), default=str)
                yield f"data: {payload}\n\n"
                idle = 0.0
                if run["status"] not in ACTIVE:
                    return
            elif idle >= 15:
                yield ": keep-alive\n\n"
                idle = 0.0
            await asyncio.sleep(0.2)
            idle += 0.2

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    _archive_async(run)
    return _public(run)


@app.post("/api/runs/{rid}/approve")
def approve_run(rid: str, body: ApproveIn | None = None):
    run = _get(rid)
    if run["status"] != "review":
        raise HTTPException(409, f"Run is {run['status']}, not awaiting review")
    att = run["attempts"][-1]
    if not att["consequences"].get("ok"):
        raise HTTPException(409, "A plan that crashed in rehearsal cannot be applied")
    if any(f["severity"] == "critical" for f in att["flags"]):
        raise HTTPException(409, "Blocked by policy: critical blast radius. Ask the agent to fix it or reject.")
    effects = open(att["effects_path"], "rb").read()
    if hashlib.sha256(effects).hexdigest() != att.get("effects_sha256"):
        raise HTTPException(409, "Integrity check failed: the recorded effects changed after the rehearsal")
    with LOCK:
        name = " ".join(((body.approver if body else None) or "").split())[:80] or "Demo approver"
        run["approval"] = {"approved_at": time.time(), "approver": name, "plan_sha256": att["plan_sha256"],
                           "effects_sha256": att["effects_sha256"], "sandbox_id": att["sandbox_id"], "policy": policy.load(),
                           "warnings": [f["title"] for f in att["flags"]]}
    _status(run, "applying")
    _emit(run, "human", "Approved. Running the drift check, then applying the approved changes for real",
          f"plan {att['plan_sha256'][:12]} · effects {att['effects_sha256'][:12]}")
    try:
        result = applier.apply(rid, att["effects_path"])
    except applier.DriftError as e:
        with LOCK:
            run["apply_result"] = {"drifted": e.drifted[:20], "drift_count": len(e.drifted)}
        _emit(run, "drift", f"Drift detected: {len(e.drifted)} rows changed since the rehearsal. Nothing applied.")
        _status(run, "drifted")
        _archive_async(run)
        return _public(run)
    with LOCK:
        run["apply_result"] = result
    _emit(run, "applied", f"Applied: {result['refunds']} refunds (${result['refund_total_cents'] / 100:,.2f}), "
                          f"{result['emails_sent']} emails, {result['rows_written']} rows")
    _status(run, "applied")
    _archive_async(run)
    return _public(run)


@app.get("/api/schema")
def schema():
    """What an external agent needs to write a plan: tables and the ctx API."""
    return {"tables": agent.get_schema(), "plan_api": agent.CTX_DOC}


def _evidence(run: dict) -> dict:
    with LOCK:
        return {
            "evidence_version": 1, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run": {k: run.get(k) for k in ("id", "task", "mode", "status", "created_at", "agent_model", "verifier_model", "error")},
            "attempts": [{"n": a["n"], "sandbox_id": a["sandbox_id"], "plan_sha256": a.get("plan_sha256"), "effects_sha256": a.get("effects_sha256"),
                          "plan": a["code"], "summary": a["summary"], "flags": a["flags"],
                          "consequences": {k: a["consequences"].get(k) for k in ("ok", "error", "tables", "row_counts", "payments", "emails", "blocked", "audit", "sandbox", "measured_by")}}
                         for a in run["attempts"]],
            "verdict": run.get("verdict"), "approval": run.get("approval"), "apply_result": run.get("apply_result"),
            "timeline": run["events"],
        }


def _archive_async(run: dict) -> None:
    """Archive the decided run to Vultr Object Storage in the background (no-op unless configured)."""
    if not archive.enabled():
        return

    def job():
        result = archive.archive(run["id"], _evidence(run))
        with LOCK:
            run["archive"] = result
            _save(run)
    threading.Thread(target=job, daemon=True).start()


@app.get("/api/runs/{rid}/evidence")
def evidence(rid: str):
    """Everything an auditor needs for one run: request, plan, fingerprints, measured consequences, checks, verdict,
    approval (who, when, policy in force) and what was applied."""
    from fastapi.responses import JSONResponse
    return JSONResponse(_evidence(_get(rid)), headers={"Content-Disposition": f'attachment; filename="stunt-double-evidence-{rid}.json"'})


@app.get("/api/policy")
def get_policy():
    return {"policy": policy.load(), "defaults": policy.DEFAULTS}


@app.put("/api/policy")
def put_policy(body: dict, req: Request):
    _rate_limit(req, per_hour=60)
    try:
        return {"policy": policy.save(body), "defaults": policy.DEFAULTS}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/beanpay/ledger")
def ledger():
    return beanpay.ledger()


@app.post("/api/demo/reset")
def reset(req: Request):
    _rate_limit(req, per_hour=20)
    if any(r["status"] in ACTIVE for r in RUNS.values()):
        raise HTTPException(409, "A rehearsal is still running; try again in a moment")
    seed.seed(config.PROD_DB)
    beanpay.reset()
    policy.reset()
    if config.MAILPIT_API:  # empty the demo inbox too (best effort)
        try:
            import httpx
            httpx.delete(f"{config.MAILPIT_API}/api/v1/messages", timeout=5)
        except Exception:  # noqa: BLE001, S110 - an inbox that can't be emptied must not block the reset
            pass
    with LOCK:  # a demo reset starts a fresh audit trail too
        RUNS.clear()
        HISTORY.clear()
        for f in HISTORY_DIR.glob("run_*.json"):
            f.unlink(missing_ok=True)
    return {"ok": True, **business()}
