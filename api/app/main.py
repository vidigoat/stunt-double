"""Stunt Double API: plan -> dispatch -> verify -> approve -> apply."""
import asyncio
import functools
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

from . import agent, archive, beanpay, config, connectors, policy, rollback, rules, sandbox, seed, workspaces
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
APPLY_LOCK = threading.Lock()            # one apply at a time: ledger check + replay are serialised across runs
RATE: dict[str, list[float]] = defaultdict(list)
AGENT_DAY: dict[str, int] = {"day": "", "count": 0}
VERIFY_DAY: dict[str, int] = {"day": "", "count": 0}  # AI checks of hand-written plans: a separate global daily budget

HISTORY_DIR = config.DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE = {"queued", "planning", "rehearsing", "verifying", "applying"}

def _demo_is_current() -> bool:
    """The demo database exists and was seeded by the current version of the demo (PRAGMA user_version)."""
    if not config.PROD_DB.exists():
        return False
    try:
        db = sqlite3.connect(config.PROD_DB)
        version = db.execute("PRAGMA user_version").fetchone()[0]
        db.close()
    except sqlite3.Error:
        return False
    return version == seed.SEED_VERSION


if not _demo_is_current():
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
    sandbox.cleanup_orphans(keep={a["sandbox_id"] for r in RUNS.values() if r["status"] in ("review", "applied") for a in r["attempts"]})
except OSError:
    pass


# ---- helpers ---------------------------------------------------------------------------------------
def _new_run(task: str, mode: str, workspace: str = workspaces.DEMO) -> dict:
    rid = "run_" + uuid.uuid4().hex[:10]
    run = {"id": rid, "task": task, "mode": mode, "workspace": workspace, "status": "queued", "created_at": time.time(), "events": [],
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
               "consequences": c, "flags": _gate_flags(c, run), "effects_path": res["effects_path"],
               "plan_sha256": hashlib.sha256(code.encode()).hexdigest(), "effects_sha256": hashlib.sha256(effects).hexdigest() if effects else None,
               "created_at": time.time()}
    attempt["approvals_required"], attempt["approval_reasons"] = policy.approvals_required(c, run["mode"])
    with LOCK:
        run["attempts"].append(attempt)
        _save(run)
    sb = c["sandbox"]
    _emit(run, "sandbox", f"Sandbox {res['id']} finished and was destroyed",
          f"ok={c['ok']} · {sb['wall_ms']} ms · network={sb['network']} · memory={sb['memory']} · runtime={sb['runtime']}")
    _status(run, "planning")
    return c


def _gate_flags(c: dict, run: dict, pol: dict | None = None) -> list[dict]:
    """Policy flags for a run, plus the workspace rule: money and email only exist for the demo business."""
    flags = agent.red_flags(c, pol)
    if run.get("workspace", workspaces.DEMO) != workspaces.DEMO and (c.get("payments", {}).get("count") or c.get("emails", {}).get("count")):
        flags.insert(0, {"rule": "workspace_side_effects", "severity": "critical", "title": "Refunds and email aren't connected for this workspace",
                         "detail": "Uploaded databases can change rows and call connectors. Payments and email only exist for the demo business."})
    return flags


def _person(name: str) -> str:
    """Identity key for the two-person rule: lookalikes (fullwidth, zero-width, soft hyphen, case) collapse to one person."""
    import unicodedata
    n = unicodedata.normalize("NFKC", name)
    n = "".join(ch for ch in n if unicodedata.category(ch) != "Cf")
    return " ".join(n.split()).casefold()


def _slack(text: str) -> str:
    """Escape user text for Slack mrkdwn so a task can't @channel or hide a link."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _notify_review(run: dict) -> None:
    """Ping humans through a connector when a decision is needed (not for blocked runs: nothing to decide)."""
    att = run["attempts"][-1] if run["attempts"] else None
    name = policy.load().get("notify_connector", "")
    if not att or not name or any(f["severity"] == "critical" for f in att["flags"]):
        return
    c = att["consequences"]
    site = config.PUBLIC_URL.rstrip("/")
    text = (f"Approval needed: “{_slack(run['task'][:120])}”. If approved: ${c.get('payments', {}).get('total_cents', 0) / 100:,.2f} out, "
            f"{c.get('emails', {}).get('count', 0)} emails, {(c.get('http') or {}).get('count', 0)} API calls"
            + (f". Needs {att.get('approvals_required')} approvers" if att.get("approvals_required", 1) > 1 else "")
            + (f". Review: {site}/app?run={run['id']}" if site else f". Run {run['id']}"))
    result = connectors.notify(name, {"text": text}, run["id"])
    _emit(run, "system", f"Notified {result.get('label', name)} that a decision is needed" if result.get("ok") else "Notification failed", text if result.get("ok") else str(result.get("error")))


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
    _notify_review(run)


def _agent_job(run: dict, feedback: str | None = None) -> None:
    workspaces.use(run.get("workspace", workspaces.DEMO))
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
    workspaces.use(run.get("workspace", workspaces.DEMO))
    try:
        _rehearse(run, code, "Submitted plan")
        learned = [f for f in run["attempts"][-1]["flags"] if f["rule"] == "learned_rule"]
        if learned:  # a rule learned from an earlier AI catch already blocks it: deterministic, instant, no AI call
            with LOCK:
                run["flags"] = run["attempts"][-1]["flags"]
                run["verdict"] = {"verdict": "dangerous", "headline": learned[0]["title"], "concerns": [],
                                  "summary": "Blocked by a rule this business learned from an earlier AI catch. It ran deterministically in the sandbox; no AI was needed."}
            _emit(run, "verify", f"{learned[0]['title']} (no AI needed)", learned[0]["detail"])
            _status(run, "review")
        elif config.INFERENCE_KEY and _verify_budget():
            _verify(run)
        else:
            if config.INFERENCE_KEY:
                _emit(run, "system", "Today's AI-check budget for this public demo is used up", "Policy rules still ran; the AI verifier resets at 00:00 UTC.")
            with LOCK:
                run["flags"] = run["attempts"][-1]["flags"]
            _status(run, "review")
            _notify_review(run)
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


def _rate_limit(req: Request, per_hour: int = 30, kind: str = "rehearsal") -> None:
    """Per visitor AND per kind of action: ten rehearsals must not use up a visitor's uploads or demo resets."""
    # The right-most X-Forwarded-For entry is the one our own proxy (Caddy) added; left-most entries are client-controlled.
    ip = (req.headers.get("x-forwarded-for") or (req.client.host if req.client else "?")).split(",")[-1].strip()
    key, now = f"{kind}:{ip}", time.time()
    RATE[key] = [t for t in RATE[key] if now - t < 3600]
    if len(RATE[key]) >= per_hour:
        raise HTTPException(429, f"Too many {kind}s from this address in the last hour, try again later")
    RATE[key].append(now)


# ---- API ----------------------------------------------------------------------------------------------
class TaskIn(BaseModel):
    task: str = Field(min_length=3, max_length=2000)
    workspace: str = Field(default=workspaces.DEMO, max_length=40)


class ManualIn(TaskIn):
    code: str = Field(min_length=10, max_length=20000)


class ApproveIn(BaseModel):
    approver: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class RejectIn(BaseModel):
    approver: str | None = Field(default=None, max_length=80)
    reason: str | None = Field(default=None, max_length=500)


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
            "agent_runs_daily_limit": config.DAILY_AGENT_RUNS,
            "ai_checks_today": VERIFY_DAY["count"] if VERIFY_DAY["day"] == time.strftime("%Y-%m-%d", time.gmtime()) else 0,
            "ai_checks_daily_limit": config.DAILY_VERIFICATIONS, "sandbox_runtime": config.SANDBOX_RUNTIME or "runc",
            "docker": docker.stdout.strip() or None, "sandbox_ready": ready, "sandbox_status": why,
            "evidence_archive": f"vultr-object-storage:{archive.BUCKET}" if archive.enabled() else None}


@app.get("/api/workspaces")
def list_workspaces():
    return {"workspaces": workspaces.all_workspaces()}


@app.post("/api/workspaces")
async def upload_workspace(request: Request, name: str = ""):
    """Upload a SQLite database (raw body, up to 20 MB) to rehearse plans against your own schema."""
    _rate_limit(request, per_hour=10, kind="upload")
    if int(request.headers.get("content-length") or 0) > workspaces.MAX_BYTES:
        raise HTTPException(413, "Databases up to 20 MB, please")
    chunks, size = [], 0
    async for chunk in request.stream():  # count as we read: chunked uploads have no Content-Length to trust
        size += len(chunk)
        if size > workspaces.MAX_BYTES:
            raise HTTPException(413, "Databases up to 20 MB, please")
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        return workspaces.create(name, data)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.delete("/api/workspaces/{ws}")
def delete_workspace(ws: str):
    if ws == workspaces.DEMO or not workspaces.exists(ws):
        raise HTTPException(404, "unknown workspace (the demo business can't be deleted)")
    with LOCK:
        if any(r.get("workspace") == ws and r["status"] in ("queued", "planning", "rehearsing", "verifying", "review", "applying") for r in RUNS.values()):
            raise HTTPException(409, "This workspace has runs in progress or awaiting review")
    if not workspaces.delete(ws):
        raise HTTPException(404, "unknown workspace")
    return {"deleted": ws}


@app.get("/api/business")
def business(ws: str = workspaces.DEMO):
    if ws != workspaces.DEMO:
        if not workspaces.exists(ws):
            raise HTTPException(404, "unknown workspace")
        d = workspaces.describe(ws)
        return {"name": d["name"], "workspace": ws, "tables": d["tables"], "counts": d["tables"],
                "refunded": {"count": 0, "total_cents": 0}, "recent_tickets": [], "beanpay": {k: v for k, v in beanpay.ledger(0).items() if k != "refunds"}}
    db = sqlite3.connect(f"file:{config.PROD_DB}?mode=ro", uri=True)
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("customers", "orders", "charges", "tickets", "servers")}
    refunded = db.execute("SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM charges WHERE status='refunded'").fetchone()
    tickets = db.execute("SELECT t.id, c.name, t.subject, t.created_at FROM tickets t JOIN customers c ON c.id=t.customer_id "
                         "ORDER BY t.created_at DESC LIMIT 8").fetchall()
    return {"name": "Bean There Coffee Co.", "counts": counts, "refunded": {"count": refunded[0], "total_cents": refunded[1]},
            "recent_tickets": [dict(zip(["id", "customer", "subject", "created_at"], r, strict=False)) for r in tickets],
            "beanpay": {k: v for k, v in beanpay.ledger(0).items() if k != "refunds"}}


def _verify_budget() -> bool:
    """True if today's global budget of AI checks on hand-written plans has room (and counts this one)."""
    day = time.strftime("%Y-%m-%d", time.gmtime())
    with LOCK:
        if VERIFY_DAY["day"] != day:
            VERIFY_DAY.update(day=day, count=0)
        if VERIFY_DAY["count"] >= config.DAILY_VERIFICATIONS:
            return False
        VERIFY_DAY["count"] += 1
        return True


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
    if not workspaces.exists(body.workspace):
        raise HTTPException(404, "unknown workspace")
    run = _new_run(body.task, "agent", body.workspace)
    threading.Thread(target=_agent_job, args=(run,), daemon=True).start()
    return {"id": run["id"]}


@app.post("/api/runs/manual")
def create_manual_run(body: ManualIn, req: Request):
    _rate_limit(req)
    if not workspaces.exists(body.workspace):
        raise HTTPException(404, "unknown workspace")
    run = _new_run(body.task, "manual", body.workspace)
    threading.Thread(target=_manual_job, args=(run, body.code), daemon=True).start()
    return {"id": run["id"]}


def _summary(r: dict) -> dict:
    a = r["attempts"][-1] if r["attempts"] else None
    c = a["consequences"] if a else {}
    return {"id": r["id"], "task": r["task"], "mode": r["mode"], "workspace": r.get("workspace", workspaces.DEMO), "status": r["status"], "created_at": r["created_at"],
            "attempts": len(r["attempts"]), "verdict": (r.get("verdict") or {}).get("verdict"),
            "money_cents": c.get("payments", {}).get("total_cents", 0), "emails": c.get("emails", {}).get("count", 0),
            "rows": sum(t["deleted"] + t["updated"] + t["inserted"] for t in c.get("tables", {}).values()),
            "blocked": any(f["severity"] == "critical" for f in (a or {}).get("flags", [])),
            "plan_sha256": (a or {}).get("plan_sha256"), "approval": r.get("approval"), "apply_result": r.get("apply_result"),
            "headline": (r.get("verdict") or {}).get("headline"),
            "top_flag": next((f["title"] for f in (a or {}).get("flags", []) if f["severity"] == "critical"), None),
            "sandbox": {k: (c.get("sandbox") or {}).get(k) for k in ("id", "runtime", "wall_ms", "profile")} if a else None,
            "kind": _kind(c) if a else None}


def _kind(c: dict) -> str:
    """What sort of double a rehearsal used, for Mission Control."""
    if (c.get("browser") or {}).get("steps"):
        return "browser"
    cl = c.get("cloud") or {}
    if cl.get("deleted") or cl.get("stopped") or cl.get("resized"):
        return "cloud"
    if (c.get("payments") or {}).get("count"):
        return "money"
    if (c.get("emails") or {}).get("count"):
        return "email"
    if (c.get("http") or {}).get("count"):
        return "api"
    return "data"


@app.get("/api/runs")
def list_runs():
    return [_summary(r) for r in sorted(RUNS.values(), key=lambda r: -r["created_at"])[:100]]


@app.get("/api/stats")
def stats():
    """Live impact numbers for this server (since the last demo reset)."""
    with LOCK:
        runs = list(RUNS.values())
    def last(r):
        return r["attempts"][-1] if r["attempts"] else None
    stopped = [r for r in runs if last(r) and (r["status"] == "rejected" or (r["status"] == "review" and any(f["severity"] == "critical" for f in last(r)["flags"])))]
    fixed = [r for r in runs if len(r["attempts"]) > 1]
    prevented = sum(last(r)["consequences"].get("payments", {}).get("total_cents", 0) for r in stopped)
    prevented += sum(max(0, r["attempts"][0]["consequences"].get("payments", {}).get("total_cents", 0)
                         - last(r)["consequences"].get("payments", {}).get("total_cents", 0)) for r in fixed)
    rows_protected = sum(sum(t["deleted"] + t["updated"] for t in last(r)["consequences"].get("tables", {}).values()) for r in stopped)
    return {"rehearsals": sum(len(r["attempts"]) for r in runs), "runs": len(runs), "applied": sum(1 for r in runs if r["status"] == "applied"),
            "stopped": len(stopped), "money_prevented_cents": prevented, "rows_protected": rows_protected,
            "rolled_back": sum(1 for r in runs if r.get("rolled_back_by"))}


@app.get("/api/runs.csv")
def runs_csv():
    """The audit trail as CSV, for auditors and spreadsheets."""
    import csv
    import io
    from fastapi.responses import Response
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["run_id", "created_utc", "workspace", "mode", "request", "status", "money_out_usd", "emails", "rows", "blocked_by_policy",
                "approvers", "approval_notes", "rejected_by", "rejection_reason", "plan_sha256", "effects_sha256"])
    with LOCK:
        runs = sorted(RUNS.values(), key=lambda r: r["created_at"])
        for r in runs:
            sm = _summary(r)
            a = r.get("approval") or {}
            rej = r.get("rejection") or {}
            att = r["attempts"][-1] if r["attempts"] else {}
            w.writerow([r["id"], time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r["created_at"])), sm["workspace"], r["mode"], r["task"], r["status"],
                        f"{sm['money_cents'] / 100:.2f}", sm["emails"], sm["rows"], sm["blocked"], " & ".join(a.get("approvers", [])),
                        " | ".join(a.get("notes", [])), rej.get("by", ""), rej.get("reason", ""), att.get("plan_sha256", ""), att.get("effects_sha256", "")])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="stunt-double-audit.csv"'})


@app.get("/api/runs/{rid}/shots/{n}.png")
def run_shot(rid: str, n: int, attempt: int = 0):
    """A screenshot the plan's browser took inside the sandbox (browser doubles only)."""
    from fastapi.responses import FileResponse
    run = _get(rid)
    if not run["attempts"] or not 1 <= n <= 12:
        raise HTTPException(404, "no such screenshot")
    att = run["attempts"][attempt - 1] if 1 <= attempt <= len(run["attempts"]) else run["attempts"][-1]
    sid = str(att.get("sandbox_id", ""))
    if not sid.startswith("sd-") or "/" in sid or ".." in sid:
        raise HTTPException(404, "no such screenshot")
    path = config.RUNS_DIR / sid / "out" / "shots" / f"{n}.png"
    if not path.is_file():
        raise HTTPException(404, "no such screenshot")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400, immutable"})


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
    with LOCK:  # claim atomically so a fix can't race an approval or another fix
        if run["status"] != "review" or run["mode"] != "agent":
            raise HTTPException(409, "Only an agent run under review can be fixed")
        run["status"] = "planning"
        _save(run)
    v = run.get("verdict") or {}
    feedback = "\n".join(filter(None, [v.get("fix_instructions"), *[f"- {c['title']}: {c['detail']}" for c in v.get("concerns", [])], body.note]))
    with LOCK:
        run["verdict"] = None
    threading.Thread(target=_agent_job, args=(run, feedback or "Please double-check the plan."), daemon=True).start()
    return {"id": rid}


class PromoteIn(BaseModel):
    by: str | None = Field(default=None, max_length=80)


@app.post("/api/runs/{rid}/promote")
def promote_catch(rid: str, req: Request, body: PromoteIn | None = None):
    """Turn the AI verifier's catch into a learned rule: a deterministic check that runs on every future rehearsal."""
    _rate_limit(req, per_hour=30, kind="rule")
    run = _get(rid)
    rule = (run.get("verdict") or {}).get("rule") or {}
    if not rule.get("sql"):
        raise HTTPException(409, "This run's verifier didn't propose a rule")
    try:
        r = rules.add(run.get("workspace", workspaces.DEMO), rule.get("title", ""), rule["sql"], rid, (body.by if body else "") or "")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    with LOCK:
        run["promoted_rule"] = r["id"]
        _save(run)
    _emit(run, "human", f"Turned the catch into a rule: {r['title']}", r["sql"])
    return r


@app.get("/api/rules")
def list_rules(ws: str = workspaces.DEMO):
    return {"rules": rules.all_rules(ws)}


@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: str):
    if not rules.delete(rule_id):
        raise HTTPException(404, "unknown rule")
    return {"deleted": rule_id}


@app.post("/api/runs/{rid}/recheck")
def recheck_run(rid: str, req: Request):
    """Run the AI verifier again when it couldn't finish (it never changes the plan or its effects)."""
    _rate_limit(req, per_hour=30, kind="re-check")
    run = _get(rid)
    with LOCK:
        if run["status"] != "review" or (run.get("verdict") or {}).get("headline") != "Verifier could not finish":
            raise HTTPException(409, "Only a run whose verifier couldn't finish can be checked again")
    if not _verify_budget():
        raise HTTPException(429, "Today's AI-check budget for this public demo is used up")
    with LOCK:
        if run["status"] != "review":
            raise HTTPException(409, f"Run is {run['status']}")
        run["status"] = "verifying"
        run["verdict"] = None
        _save(run)
    threading.Thread(target=_verify, args=(run,), daemon=True).start()
    return {"id": rid}


@app.post("/api/runs/{rid}/reject")
def reject_run(rid: str, body: RejectIn | None = None):
    run = _get(rid)
    who = " ".join(((body.approver if body else None) or "").split())[:80] or "Approver"
    reason = " ".join(((body.reason if body else None) or "").split())[:500]
    with LOCK:
        if run["status"] != "review":
            raise HTTPException(409, f"Run is {run['status']}, not awaiting review")
        run["status"] = "rejected"
        run["rejection"] = {"by": who, "at": time.time(), "reason": reason}
        _save(run)
    _emit(run, "human", f"Rejected by {who}. Nothing was changed.", reason)
    _archive_async(run)
    return _public(run)


@app.post("/api/runs/{rid}/approve")
def approve_run(rid: str, body: ApproveIn | None = None):
    run = _get(rid)
    with LOCK:  # check-and-claim atomically: two approvals can never both apply
        if run["status"] != "review":
            raise HTTPException(409, f"Run is {run['status']}, not awaiting review")
        att = run["attempts"][-1]
        if not att["consequences"].get("ok"):
            raise HTTPException(409, "A plan that crashed in rehearsal cannot be applied")
        if any(f["severity"] == "critical" for f in att["flags"]):
            raise HTTPException(409, "Blocked by policy: critical blast radius. Ask the agent to fix it or reject.")
        if run["mode"] != "rollback":  # policy may have changed since the rehearsal: the stricter result wins
            now = [f for f in _gate_flags(att["consequences"], run) if f["severity"] == "critical"]
            if now:
                raise HTTPException(409, f"Blocked by the current policy: {now[0]['title']}. Rehearse again or reject.")
        hours = policy.load().get("approval_expires_hours", 24)
        if hours and time.time() - att["created_at"] > hours * 3600:
            raise HTTPException(409, f"This rehearsal is more than {hours:g} hours old and has expired. Rehearse again to approve.")
        effects = open(att["effects_path"], "rb").read()
        if hashlib.sha256(effects).hexdigest() != att.get("effects_sha256"):
            raise HTTPException(409, "Integrity check failed: the recorded effects changed after the rehearsal")
        name = " ".join(((body.approver if body else None) or "").split())[:80]
        needed = max(att.get("approvals_required", 1), policy.approvals_required(att["consequences"], run["mode"])[0])
        approvals = [x for x in run.get("approvals", []) if x.get("effects_sha256") == att["effects_sha256"]]
        if needed > 1 and not name:
            raise HTTPException(422, "This change needs two named approvers. Enter your name to approve.")
        name = name or "Demo approver"
        if not _person(name):
            raise HTTPException(422, "Enter a real name to approve.")
        if any(_person(x["name"]) == _person(name) for x in approvals):
            raise HTTPException(409, f"{name} already approved. The second approval must come from a different person.")
        note = " ".join(((body.note if body else None) or "").split())[:500]
        v = run.get("verdict") or {}
        if v.get("verdict") in ("concerns", "dangerous") and v.get("headline") != "Verifier could not finish" and len(note) < 10:
            raise HTTPException(422, f"The AI verifier objected (“{v.get('headline', 'concerns')}”). To approve anyway, write a note saying why. It goes in the audit trail.")
        approvals.append({"name": name, "at": time.time(), "effects_sha256": att["effects_sha256"], **({"note": note} if note else {})})
        run["approvals"] = approvals
        if len(approvals) < needed:
            _save(run)
            pending = True
        else:
            pending = False
            run["approval"] = {"approved_at": time.time(), "approver": " & ".join(x["name"] for x in approvals), "approvers": [x["name"] for x in approvals],
                               "notes": [f"{x['name']}: {x['note']}" for x in approvals if x.get("note")],
                               "plan_sha256": att["plan_sha256"], "effects_sha256": att["effects_sha256"], "sandbox_id": att["sandbox_id"],
                               "policy": policy.load(), "warnings": [f["title"] for f in att["flags"]]}
            run["status"] = "applying"
            _save(run)
    if pending:
        _emit(run, "human", f"Approval {len(approvals)} of {needed} by {name}", "waiting for a second, different approver ("
              + ", ".join(att.get("approval_reasons", [])) + ")")
        return _public(run)
    with APPLY_LOCK:
        already = beanpay.refunded_charges([p["charge_id"] for p in json.loads(effects).get("payments", [])])
        if already:
            with LOCK:
                run["status"], run["approval"] = "review", None
                _save(run)
            raise HTTPException(409, f"{len(already)} of these charges were already refunded through BeanPay (e.g. #{already[0]}). Rehearse again.")
        return _apply_claimed(run, att, rid)


def _apply_claimed(run: dict, att: dict, rid: str):
    _emit(run, "human", "Approved. Running the drift check, then applying the approved changes for real",
          f"plan {att['plan_sha256'][:12]} · effects {att['effects_sha256'][:12]}")
    try:
        result = applier.apply(rid, att["effects_path"], run.get("workspace"))
    except applier.DriftError as e:
        with LOCK:
            run["apply_result"] = {"drifted": e.drifted[:20], "drift_count": len(e.drifted)}
        _emit(run, "drift", f"Drift detected: {len(e.drifted)} rows changed since the rehearsal. Nothing applied.")
        _status(run, "drifted")
        _archive_async(run)
        return _public(run)
    except Exception as e:  # noqa: BLE001 - never leave a run stuck in "applying"
        with LOCK:
            run["apply_result"] = {"error": str(e)[:500]}
            run["error"] = f"Apply failed: {str(e)[:300]}"
        _emit(run, "error", "Apply failed", str(e))
        _status(run, "failed")
        _archive_async(run)
        return _public(run)
    with LOCK:
        run["apply_result"] = result
        src = RUNS.get(run.get("rollback_of") or "")
        if src:
            src["rolled_back_by"] = run["id"]
            _save(src)
    _emit(run, "applied", f"Applied: {result['refunds']} refunds (${result['refund_total_cents'] / 100:,.2f}), "
                          f"{result['emails_sent']} emails, {result.get('http_delivered', 0)} API calls, {result['rows_written']} rows")
    _status(run, "applied")
    _archive_async(run)
    return _public(run)


@app.get("/api/schema")
def schema(ws: str = workspaces.DEMO):
    """What an external agent needs to write a plan: tables and the ctx API."""
    if not workspaces.exists(ws):
        raise HTTPException(404, "unknown workspace")
    workspaces.use(ws)
    return {"workspace": ws, "tables": agent.get_schema(), "plan_api": agent.CTX_DOC}


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


@functools.lru_cache(maxsize=16)
def _effects_cached(path: str, sha: str) -> dict:
    """Parsed effects, cached per file + hash: paging through 10,000 changed rows shouldn't re-read the file each time."""
    return json.loads(open(path).read())


@app.get("/api/runs/{rid}/changes")
def run_changes(rid: str, table: str = "", op: str = "", q: str = "", offset: int = 0, limit: int = 25):
    """Every changed row of the latest attempt (not just samples), filterable and paginated."""
    run = _get(rid)
    if not run["attempts"]:
        raise HTTPException(404, "no rehearsal yet")
    att = run["attempts"][-1]
    try:
        effects = _effects_cached(att["effects_path"], att.get("effects_sha256") or "")
    except (OSError, ValueError) as e:
        raise HTTPException(404, "effects not available") from e
    limit = max(1, min(limit, 100))
    rows = []
    for t, d in effects.get("changes", {}).items():
        if table and t != table:
            continue
        for kind in ("updated", "deleted", "inserted"):
            if op and op != kind:
                continue
            for item in d.get(kind, []):
                row = item.get("after") or item.get("before") or {}
                if q and q.lower() not in json.dumps(row, default=str).lower():
                    continue
                rows.append({"table": t, "op": kind, "rowid": item["rowid"], "before": item.get("before"), "after": item.get("after"),
                             "changed": item.get("changed", [])})
    return {"total": len(rows), "offset": offset, "limit": limit, "rows": rows[offset:offset + limit],
            "tables": sorted(effects.get("changes", {}).keys())}


@app.get("/api/runs/{rid}/evidence")
def evidence(rid: str):
    """Everything an auditor needs for one run: request, plan, fingerprints, measured consequences, checks, verdict,
    approval (who, when, policy in force) and what was applied."""
    from fastapi.responses import JSONResponse
    return JSONResponse(_evidence(_get(rid)), headers={"Content-Disposition": f'attachment; filename="stunt-double-evidence-{rid}.json"'})


@app.get("/api/policy")
def get_policy():
    return {"policy": policy.load(), "defaults": policy.DEFAULTS}


@app.post("/api/policy/simulate")
def simulate_policy(body: dict):
    """What would change if this draft policy had been in force for the recent rehearsals? Nothing is saved."""
    try:
        draft = {**policy.load(), **policy.validate(body)}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    current = policy.load()
    with LOCK:
        runs = sorted((r for r in RUNS.values() if r["attempts"]), key=lambda r: -r["created_at"])[:50]
    out = []
    for r in runs:
        c = r["attempts"][-1]["consequences"]
        before = agent.red_flags(c, current)
        after = agent.red_flags(c, draft)
        was = any(f["severity"] == "critical" for f in before)
        now = any(f["severity"] == "critical" for f in after)
        need_was = policy.approvals_required(c, r["mode"], current)[0]
        need_now = policy.approvals_required(c, r["mode"], draft)[0]
        if was != now or need_was != need_now:
            out.append({"id": r["id"], "task": r["task"], "blocked_before": was, "blocked_after": now,
                        "approvers_before": need_was, "approvers_after": need_now,
                        "new_reasons": [f["title"] for f in after if f["severity"] == "critical" and f["title"] not in {x["title"] for x in before}][:3]})
    return {"considered": len(runs), "changed": out,
            "newly_blocked": sum(1 for x in out if x["blocked_after"] and not x["blocked_before"]),
            "unblocked": sum(1 for x in out if x["blocked_before"] and not x["blocked_after"]),
            "now_two_person": sum(1 for x in out if x["approvers_after"] > x["approvers_before"])}


@app.put("/api/policy")
def put_policy(body: dict, req: Request, by: str = ""):
    _rate_limit(req, per_hour=60, kind="policy edit")
    try:
        return {"policy": policy.save(body, by), "defaults": policy.DEFAULTS}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/policy/history")
def policy_history():
    """Every rule change: who, when, old -> new. Policy edits are part of the audit trail too."""
    return {"history": policy.history()}


@app.post("/api/runs/{rid}/rollback")
def rollback_run(rid: str, req: Request):
    """Create a rollback run: the inverse of an applied run's data changes, awaiting approval like any change."""
    _rate_limit(req)
    src = _get(rid)
    with LOCK:
        if src["status"] != "applied":
            raise HTTPException(409, "Only an applied run can be rolled back")
        existing = src.get("rollback_run")
        if existing and RUNS.get(existing, {}).get("status") in ("review", "applying", "applied"):
            raise HTTPException(409, f"Rollback already exists: {existing}")
    att = src["attempts"][-1]
    ws = src.get("workspace", workspaces.DEMO)
    # Build the inverse BEFORE creating the run: a failure here must not leave a run stuck in "queued".
    try:
        if hashlib.sha256(open(att["effects_path"], "rb").read()).hexdigest() != att.get("effects_sha256"):
            raise ValueError("the approved effects changed on disk")
        db = sqlite3.connect(f"file:{workspaces.db_path(ws)}?mode=ro", uri=True)
        rows_now = {t: db.execute(f"SELECT COUNT(*) FROM {applier.q(t)}").fetchone()[0]  # noqa: S608 - quoted identifier
                    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
        db.close()
        rb_id = "rb-" + uuid.uuid4().hex[:10]
        c, effects_path, effects_sha = rollback.build(att["effects_path"], config.RUNS_DIR / rb_id / "out", rb_id, rows_now)
    except (OSError, ValueError, KeyError, sqlite3.Error) as e:
        raise HTTPException(409, f"Can't build an undo for this run: {str(e)[:200]}") from e
    run = _new_run(f"Undo: {src['task']}", "rollback", ws)
    flags = agent.red_flags(c)
    irr = c["irreversible"]
    if irr["refunds"] or irr["emails"] or irr["http"] or irr.get("servers_deleted"):
        flags.append({"rule": "irreversible", "severity": "medium", "title": "Some effects can't be undone",
                      "detail": f"{irr['refunds']} refunds (${irr['refund_total_cents'] / 100:,.2f}), {irr['emails']} emails, {irr['http']} API calls"
                                + (f" and {irr['servers_deleted']} deleted servers" if irr.get("servers_deleted") else "")
                                + " already happened. Only the data changes are rolled back."})
    code = f"# Rollback of {rid}: the inverse of its approved effects ({att.get('effects_sha256', '')[:12]})\n"
    with LOCK:
        run["rollback_of"] = rid
        run["attempts"].append({"n": 1, "sandbox_id": rb_id, "code": code, "summary": f"Undo the data changes of {rid}", "consequences": c,
                                "flags": flags, "effects_path": effects_path, "plan_sha256": hashlib.sha256(code.encode()).hexdigest(),
                                "effects_sha256": effects_sha, "created_at": time.time(),
                                "approvals_required": policy.approvals_required(c, "rollback")[0], "approval_reasons": policy.approvals_required(c, "rollback")[1]})
        run["flags"] = flags
        run["status"] = "review"
        src["rollback_run"] = run["id"]
        _save(run)
        _save(src)
    _emit(run, "sandbox", f"Built the inverse of {rid}'s approved changes", "updated rows go back, inserted rows are removed, deleted rows return")
    return {"id": run["id"]}


@app.get("/api/connectors")
def list_connectors():
    return {"connectors": connectors.public()}


@app.get("/api/outbox")
def outbox():
    """Everything delivered to API connectors after approval (the demo connectors deliver here)."""
    return connectors.deliveries()


@app.get("/api/beanpay/ledger")
def ledger():
    return beanpay.ledger()


@app.post("/api/demo/reset")
def reset(req: Request):
    _rate_limit(req, per_hour=20, kind="demo reset")
    if any(r["status"] in ACTIVE for r in RUNS.values()):
        raise HTTPException(409, "A rehearsal is still running; try again in a moment")
    seed.seed(config.PROD_DB)
    beanpay.reset()
    connectors.reset()
    policy.reset()
    rules.reset()
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
