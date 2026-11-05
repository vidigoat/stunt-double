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
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import agent, archive, beanpay, config, connectors, policy, rollback, pg_import, rules, sandbox, seed, sql_export, vultr_import, vultr_vm, workspaces
from . import apply as applier
from .engine import contracts as engine_contracts, evidence as engine_evidence, graph as engine_graph, subsets as engine_subsets, verdict as engine_verdict

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


def _vm_reaper() -> None:
    """Every two minutes, destroy any rehearsal VM older than ten minutes (a lost result must never leave one billing)."""
    while True:
        if vultr_vm.configured():
            vultr_vm.reap()
        time.sleep(120)


threading.Thread(target=_vm_reaper, daemon=True).start()


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
    iso = run.get("isolation", "container")
    if iso == "vultr_vm":
        _emit(run, "sandbox", "Creating a dedicated Vultr VM for this rehearsal", "Phase 1 runs on its own Cloud Compute instance; phase 2 measures it here in gVisor")
    with SANDBOX_SLOTS:
        res = sandbox.rehearse(code, iso, emit=lambda t: _emit(run, "sandbox", t))
    return _add_attempt(run, res, code, summary)


def _add_attempt(run: dict, res: dict, code: str, summary: str, **extra) -> dict:
    """Turn a measured result (a rehearsed plan, or a surgical subset) into the run's next attempt."""
    c = res["consequences"]
    _contract_check(run, c, res.get("effects_path"))
    effects = open(res["effects_path"], "rb").read() if c.get("ok") else b""
    attempt = {"n": len(run["attempts"]) + 1, "sandbox_id": res["id"], "code": code, "summary": summary,
               "consequences": c, "flags": _gate_flags(c, run), "effects_path": res["effects_path"],
               "plan_sha256": hashlib.sha256(code.encode()).hexdigest(), "effects_sha256": hashlib.sha256(effects).hexdigest() if effects else None,
               "created_at": time.time(), **extra}
    attempt["approvals_required"], attempt["approval_reasons"] = policy.approvals_required(c, run["mode"])
    with LOCK:
        run["attempts"].append(attempt)
        _save(run)
    sb = c["sandbox"]
    _emit(run, "sandbox", f"Sandbox {res['id']} finished and was destroyed",
          f"ok={c['ok']} · {sb['wall_ms']} ms · network={sb['network']} · memory={sb['memory']} · runtime={sb['runtime']}")
    _status(run, "planning")
    return c


def _jury_own(run: dict) -> str | None:
    """What the AI jury itself concluded (before any deterministic check raised it), if it ran."""
    v = run.get("verdict") or {}
    if not v or v.get("source") == "learned_rule" or v.get("headline") == "Verifier could not finish":
        return None
    return v.get("raised_from") or v.get("verdict")


def _gate_flags(c: dict, run: dict, pol: dict | None = None, jury: str | None = None) -> list[dict]:
    """Policy flags for a run, the intent contract, and the workspace rule: money and email only exist for the demo business.

    A broken promise locks approval, unless the AI jury, investigating on its own, judged the outcome right: then two
    AI readings of the request disagree, and a person decides (strike the promise with a reason, or reject)."""
    flags = agent.red_flags(c, pol)
    jury = jury or _jury_own(run)
    for p in (c.get("contract") or {}).get("promises", []):
        if p.get("status") == "broken":
            rows = f"{p['after']:,} row{'s' if p['after'] != 1 else ''} break it."
            if jury == "looks_right":
                flags.insert(0, {"rule": "contract", "severity": "high", "title": f"Breaks a promise made before the plan: {p['text'].rstrip('.')}",
                                 "detail": f"{rows} The AI jury judged the outcome right, so the two readings of your request disagree: "
                                           "strike the promise with a reason, or reject."})
            else:
                flags.insert(0, {"rule": "contract", "severity": "critical", "title": f"Breaks a promise made before the plan: {p['text'].rstrip('.')}",
                                 "detail": f"{rows} Written before the plan existed."})
        elif p.get("status") == "unmet":
            done = max(0, p["today"] - p["after"])
            flags.append({"rule": "contract", "severity": "high", "title": f"Leaves the work undone: {p['text'].rstrip('.')}",
                          "detail": f"{p['after']:,} of {p['today']:,} still to do after this plan ({done:,} done)."})
        elif p.get("status") == "unknown":
            flags.append({"rule": "contract", "severity": "medium", "title": f"Couldn't check a promise: {p['text'].rstrip('.')}",
                          "detail": f"Its check didn't finish on this rehearsal ({p.get('why') or 'unknown reason'}). Judge this part yourself."})
    if run.get("workspace", workspaces.DEMO) != workspaces.DEMO and (c.get("payments", {}).get("count") or c.get("emails", {}).get("count")):
        flags.insert(0, {"rule": "workspace_side_effects", "severity": "critical", "title": "Refunds and email aren't connected for this workspace",
                         "detail": "Uploaded databases can change rows and call connectors. Payments and email only exist for the demo business."})
    return flags


# ---- intent contracts: what the request means, written before any plan ---------------------------------------------
CONTRACT_READY: dict[str, threading.Event] = {}


def _contract_job(run: dict) -> None:
    ws = run.get("workspace", workspaces.DEMO)
    base = workspaces.db_path(ws)
    try:
        c = engine_contracts.compile_contract(run["task"], policy.load().get("glossary") or [], base, config.CONTRACT_MODELS,
                                              agent.client(), config.DATA_DIR, today=config.DEMO_TODAY if ws == workspaces.DEMO else None)
        good = [json.loads(open(r["attempts"][-1]["effects_path"]).read()) for r in RUNS.values()
                if r["id"] != run["id"] and r.get("task", "").strip() == run["task"].strip() and r.get("workspace", workspaces.DEMO) == ws
                and (r.get("verdict") or {}).get("verdict") == "looks_right" and r["status"] != "applied" and r["attempts"]][:5]
        enforced, withdrawn = engine_contracts.withdraw_unfair(c["promises"], base, good)
        contract = {**c, "status": "ready", "promises": enforced, "withdrawn": withdrawn}
        if not enforced:
            contract = {"status": "failed", "reason": "every promise was withdrawn: each one failed a plan the jury judged correct"}
    except Exception as e:  # noqa: BLE001 - the contract is a layer of protection, never a reason a run fails
        contract = {"status": "failed", "reason": str(e)[:300]}
    with LOCK:
        run["contract"] = contract
        _save(run)
    if contract["status"] == "ready":
        work = [p for p in contract["promises"] if p["kind"] == "obligation"]
        _emit(run, "contract", f"Contract signed before the plan: {len(contract['promises'])} promises",
              "\n".join(f"{'Work to do' if p['kind'] == 'obligation' else 'Guard'}: {p['text']}"
                        + (f" ({p['today']:,} today)" if p["kind"] == "obligation" else "") for p in contract["promises"])
              + (f"\nWithdrawn: {len(withdrawn)} promise(s) a correct plan for this request failed." if withdrawn else "")
              + ("" if work else "\nNo work to measure today: every promise is a guard."))
    else:
        _emit(run, "contract", "No contract for this run", contract["reason"])
    CONTRACT_READY.setdefault(run["id"], threading.Event()).set()
    if contract["status"] == "ready":
        _contract_cross_check(run, contract, base, ws)


def _contract_cross_check(run: dict, contract: dict, base, ws: str) -> None:
    """A second model, from another lab, reads the same request on its own. Never delays the run."""
    second = next((m for m in config.CONTRACT_MODELS if m != contract.get("model")), None)
    if not second:
        return
    try:
        theirs = engine_contracts.compile_contract(run["task"], policy.load().get("glossary") or [], base, [second], agent.client(),
                                                   config.DATA_DIR, today=config.DEMO_TODAY if ws == workspaces.DEMO else None)
        cc = {"model": second, **engine_contracts.cross_check(contract["promises"], theirs["promises"])}
    except Exception as e:  # noqa: BLE001
        cc = {"model": second, "status": "failed", "reason": str(e)[:200]}
    with LOCK:
        if run.get("contract") is contract:
            contract["cross_check"] = cc
            _save(run)
    if cc["status"] == "agree":
        _emit(run, "contract", f"Cross-checked: {second} read the request the same way ({cc['ours']:,} to do)")
    elif cc["status"] == "disagree":
        _emit(run, "contract", f"Two models read this request differently: {cc['ours']:,} to do, or {cc['theirs']:,}",
              "The request is ambiguous. A glossary entry for the term they disagree on settles it for every future run.")


def _contract_start(run: dict) -> None:
    if not config.INFERENCE_KEY or not config.CONTRACT_MODELS:
        return
    CONTRACT_READY[run["id"]] = threading.Event()
    with LOCK:
        run["contract"] = {"status": "writing"}
    _emit(run, "contract", "Writing down what the request means, before any plan exists",
          "From the request, the business glossary and the schema only. The plan will never see it.")
    threading.Thread(target=_contract_job, args=(run,), daemon=True).start()


def _contract_check(run: dict, c: dict, effects_path: str | None, wait_s: float = 120) -> None:
    """Check the measured effects against the run's contract and put the result into the consequences. No AI."""
    if not c.get("ok") or not effects_path or not run.get("contract"):
        return
    ev = CONTRACT_READY.get(run["id"])         # None after a restart: then the contract on the run is all there is
    if ev is not None and not ev.is_set():
        _emit(run, "contract", "Waiting for the contract to be finished before judging the plan")
        if not ev.wait(wait_s):
            c["contract"] = {"status": "late", "promises": []}
            return
    contract = run.get("contract") or {}
    if contract.get("status") != "ready":
        return
    try:
        effects = json.loads(open(effects_path).read())
        results = engine_contracts.evaluate(contract["promises"], workspaces.db_path(run.get("workspace", workspaces.DEMO)), effects)
    except (OSError, ValueError) as e:
        c["contract"] = {"status": "unknown", "why": str(e)[:200], "promises": []}
        return
    c["contract"] = {"status": "checked", "model": contract.get("model"), "promises": results,
                     "broken": sum(r["status"] == "broken" for r in results), "unmet": sum(r["status"] == "unmet" for r in results)}


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


VERDICT_CACHE = config.DATA_DIR / "verdict-cache.json"
UNFINISHED = {"Verifier could not finish", "Automatic review unavailable"}


def _verdict_key(run: dict, att: dict) -> str | None:
    """Same request, same measured effects, same data, same policy and model: the AI would be judging identical facts.
    Only then may an earlier live verdict be shown again (labelled, with a one-click live re-check)."""
    if not att.get("effects_sha256"):
        return None
    try:
        con = sqlite3.connect(f"file:{workspaces.db_path(run.get('workspace'))}?mode=ro", uri=True)
        h = hashlib.sha256()
        for line in con.iterdump():
            h.update(line.encode())
        con.close()
    except sqlite3.Error:
        return None
    facts = [run["task"].strip(), att["effects_sha256"], h.hexdigest(), json.dumps(policy.load(), sort_keys=True), config.VERIFIER_MODEL,
             ",".join(config.JURY_MODELS), "jury-independent-of-contract"]
    return hashlib.sha256(json.dumps(facts).encode()).hexdigest()


def _cache_get(key: str | None) -> dict | None:
    if not key:
        return None
    try:
        return json.loads(VERDICT_CACHE.read_text()).get(key)
    except (OSError, ValueError):
        return None


def _cache_put(key: str | None, verdict: dict, ms: int) -> None:
    if not key or verdict.get("headline") in UNFINISHED:
        return
    with LOCK:
        try:
            cache = json.loads(VERDICT_CACHE.read_text())
        except (OSError, ValueError):
            cache = {}
        cache[key] = {"verdict": verdict, "at": time.time(), "ms": ms}
        cache = dict(sorted(cache.items(), key=lambda kv: kv[1]["at"])[-200:])
        VERDICT_CACHE.write_text(json.dumps(cache))


LABS = {"glm": "Zhipu GLM", "deepseek": "DeepSeek", "minimax": "MiniMax", "qwen": "Qwen", "mimo": "Xiaomi MiMo"}
SEVERITY = {"looks_right": 0, "concerns": 1, "dangerous": 2}


def _lab(model: str) -> str:
    return next((v for k, v in LABS.items() if model.startswith(k)), model)


def _verify_with_jury(run: dict, att: dict) -> dict:
    """The verifier and the jurors (other labs' models on Vultr Inference) investigate the same facts independently and in
    parallel. The jury can only make the verdict stricter: one 'dangerous' or two objections rule out 'looks right'."""
    import concurrent.futures
    import contextvars

    def call(models, vision, label):
        def emit(k, t, d=None):
            _emit(run, k, f"{label}: {t}" if label else t, d)
        try:
            return agent.verify(run["task"], att["code"], att["consequences"], emit, models=models, vision=vision)
        except Exception as e:  # noqa: BLE001
            return {"verdict": "concerns", "headline": "Automatic review unavailable", "summary": str(e)[:300], "concerns": []}

    primary = config.VERIFIER_MODEL.split(",")[0]
    jurors = [m for m in config.JURY_MODELS if m != primary]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1 + len(jurors)) as ex:  # each juror reads the same workspace
        main_f = ex.submit(contextvars.copy_context().run, call, None, True, "")
        jury_f = [(m, ex.submit(contextvars.copy_context().run, call, [m, config.JURY_FALLBACK], False, f"Juror {_lab(m)}")) for m in jurors]
        verdict = main_f.result()
        votes = [{"model": primary, "lab": _lab(primary), "verdict": verdict.get("verdict"), "headline": verdict.get("headline"), "role": "verifier"}]
        for m, f in jury_f:
            v = f.result()
            if v.get("headline") in UNFINISHED:
                votes.append({"model": m, "lab": _lab(m), "verdict": None, "headline": "abstained (could not finish)", "role": "juror"})
            else:
                votes.append({"model": m, "lab": _lab(m), "verdict": v.get("verdict"), "headline": v.get("headline"), "role": "juror"})
    if not jurors or verdict.get("headline") in UNFINISHED:
        return verdict
    cast = [v["verdict"] for v in votes if v["verdict"]]
    objections = sum(1 for v in cast if v != "looks_right")
    stricter = "dangerous" if "dangerous" in cast[1:] and objections >= 2 else "concerns" if objections >= 2 or "dangerous" in cast else None
    if stricter and SEVERITY[stricter] > SEVERITY.get(verdict.get("verdict"), 1):
        dissent = next(v for v in votes[1:] if v["verdict"] and v["verdict"] != "looks_right")
        verdict["verdict"] = stricter
        verdict.setdefault("concerns", []).insert(0, {"severity": "high" if stricter == "dangerous" else "medium",
                                                      "title": f"The AI jury objected ({objections} of {len(cast)})",
                                                      "detail": f"{dissent['lab']}: {dissent['headline']}"})
    approve = verdict["verdict"] == "looks_right"
    verdict["jury"] = {"votes": votes, "agree": sum(1 for v in cast if (v == "looks_right") == approve), "cast": len(cast)}
    return verdict


def _verify(run: dict) -> None:
    att = run["attempts"][-1]
    _status(run, "verifying")
    _emit(run, "verify", "Stunt Double is checking the consequences against your request")
    key = _verdict_key(run, att)
    hit = None if run.pop("force_live", False) else _cache_get(key)
    if hit:
        verdict = json.loads(json.dumps(hit["verdict"]))
        verdict["cached"] = {"at": hit["at"], "ms": hit["ms"]}
        _emit(run, "verify", "Same request, same measured effects, same data as an earlier live check: showing its verdict",
              f"Live check at {time.strftime('%H:%M UTC', time.gmtime(hit['at']))} took {hit['ms'] / 1000:.0f} s. Use 'Re-check live' to run the AI again.")
    else:
        t0 = time.time()
        verdict = _verify_with_jury(run, att)
        _cache_put(key, verdict, int((time.time() - t0) * 1000))
    rule = verdict.get("rule") if isinstance(verdict.get("rule"), dict) else None
    if rule:  # only offer a rule a human can actually learn: one read-only SELECT that passes today's data
        try:
            rule["sql"] = rules.check_sql(rule.get("sql", ""), run.get("workspace", workspaces.DEMO))
            rules.check_against_good(rule["sql"], run.get("workspace", workspaces.DEMO), _good_rehearsals(run.get("workspace", workspaces.DEMO), run["id"]))
        except ValueError as e:
            verdict.pop("rule", None)
            _emit(run, "verify", "The verifier's proposed rule was not offered", str(e))
    att["flags"] = _gate_flags(att["consequences"], run, jury=None if verdict.get("source") == "learned_rule" else verdict.get("verdict"))
    crit = [f for f in att["flags"] if f["severity"] == "critical"]
    if crit and verdict.get("verdict") != "dangerous":
        verdict["raised_from"] = verdict.get("verdict")      # what the jury said, before a deterministic check overruled it
        verdict["verdict"] = "dangerous"
    with LOCK:
        run["verdict"] = verdict
        run["flags"] = att["flags"]
    _emit(run, "verify", verdict.get("headline", "Review ready"))
    broken = any(p.get("status") == "broken" for p in (att["consequences"].get("contract") or {}).get("promises", []))
    if (verdict.get("verdict") != "looks_right" or broken) and not run["attempts"][-1].get("surgical_of"):
        _surgical_offer(run)
    _status(run, "review")
    if not _auto_approve(run):
        _notify_review(run)


def _within_autonomy(run: dict, pol: dict) -> str | None:
    """Why this run may apply without a human (graduated autonomy), or None. Everything must hold: no flags at all, the
    AI verifier said looks_right, one approver needed, and the money / rows / email / cloud budget is respected."""
    if not pol.get("autonomy_enabled") or run.get("mode") == "rollback":
        return None
    att = run["attempts"][-1]
    c = att["consequences"]
    v = run.get("verdict") or {}
    rows = sum(t["deleted"] + t["updated"] + t["inserted"] for t in c.get("tables", {}).values())
    money = c.get("payments", {}).get("total_cents", 0)
    cl = c.get("cloud") or {}
    if (not c.get("ok") or att["flags"] or v.get("verdict") != "looks_right" or att.get("approvals_required", 1) > 1
            or money > pol.get("autonomy_max_usd", 0) * 100 or rows > pol.get("autonomy_max_rows", 0)
            or (c.get("emails", {}).get("count") and not pol.get("autonomy_allow_email")) or (c.get("http") or {}).get("count")
            or cl.get("deleted") or cl.get("stopped") or cl.get("resized")):
        return None
    return f"within the autonomy budget (≤ ${pol.get('autonomy_max_usd', 0):,} and ≤ {pol.get('autonomy_max_rows', 0):,} rows; no flags; the verifier agreed)"


def _auto_approve(run: dict) -> bool:
    """Graduated autonomy: a small, clean, AI-confirmed change applies without waiting for a human (opt-in policy)."""
    why = _within_autonomy(run, policy.load())
    if not why:
        return False
    att = run["attempts"][-1]
    with LOCK:
        if run["status"] != "review":
            return False
        effects = open(att["effects_path"], "rb").read()
        if hashlib.sha256(effects).hexdigest() != att.get("effects_sha256"):
            return False
        run["approvals"] = [{"name": "Autonomy policy", "at": time.time(), "effects_sha256": att["effects_sha256"]}]
        run["approval"] = {"approved_at": time.time(), "approver": "Autonomy policy (no human needed)", "approvers": ["Autonomy policy"],
                           "notes": [f"Auto-approved {why}"], "auto": True, "plan_sha256": att["plan_sha256"],
                           "effects_sha256": att["effects_sha256"], "sandbox_id": att["sandbox_id"], "policy": policy.load(), "warnings": []}
        run["status"] = "applying"
        _save(run)
    _emit(run, "human", "Auto-approved by the autonomy policy", why)
    with APPLY_LOCK:
        if beanpay.refunded_charges([p["charge_id"] for p in json.loads(effects).get("payments", [])]):
            with LOCK:
                run["status"], run["approval"] = "review", None
                _save(run)
            return False
        _apply_claimed(run, att, run["id"])
    return True


def _agent_job(run: dict, feedback: str | None = None) -> None:
    workspaces.use(run.get("workspace", workspaces.DEMO))
    try:
        _status(run, "planning")
        task = run["task"]
        ev = CONTRACT_READY.get(run["id"])
        if not feedback and ev is not None:      # the agent signs before it writes: it plans against the contract
            ev.wait(45)
            promises = (run.get("contract") or {}).get("promises") if (run.get("contract") or {}).get("status") == "ready" else None
            if promises:
                task += ("\n\nBefore you started, Stunt Double wrote down what this request means. Your plan will be checked "
                         "against these promises, by code, after it runs:\n" + "\n".join(f"- {p['text']}" for p in promises))
                _emit(run, "agent", f"The agent plans against the contract ({len(promises)} promises)")
        _emit(run, "agent", "Ops agent is planning" if not feedback else "Ops agent is fixing the plan")
        final, history = agent.ops_agent(task, lambda code, s: _rehearse(run, code, s),
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
                run["verdict"] = {"verdict": "dangerous", "headline": learned[0]["title"], "concerns": [], "source": "learned_rule",
                                  "summary": "Blocked by a rule this business learned from an earlier AI catch. It ran deterministically in the sandbox; no AI was needed."}
            _emit(run, "verify", f"{learned[0]['title']} (no AI needed)", learned[0]["detail"])
            _surgical_offer(run)
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


def _surgical_checks(run: dict) -> list[dict]:
    """The checks that flag what's wrong, best first: a learned rule that fired, a contract guard the plan broke,
    then the AI jury's own check."""
    att = run["attempts"][-1]
    ws = run.get("workspace", workspaces.DEMO)
    out = []
    for r in (att["consequences"].get("rules") or []):
        if r.get("violations"):
            hit = next((x for x in rules.all_rules(ws) if x["id"] == r.get("id")), None)
            if hit:
                out.append({"title": hit["title"], "sql": hit["sql"], "source": "learned rule", "required": True})
    for p in (att["consequences"].get("contract") or {}).get("promises", []):
        if p.get("status") == "broken":
            out.append({"title": p["text"], "sql": p["sql"], "source": "intent contract", "required": True})
    v = run.get("verdict") or {}
    if v.get("verdict") in ("concerns", "dangerous") and isinstance(v.get("rule"), dict) and v["rule"].get("sql"):
        out.append({"title": v["rule"].get("title") or "the AI jury's check", "sql": v["rule"]["sql"], "source": "AI jury", "required": False})
    return out


def _surgical_propose(run: dict) -> tuple[dict, engine_subsets.Offer]:
    """The largest part of the plan that passes every check that fired and still does some of the work asked for."""
    att = run["attempts"][-1]
    checks = _surgical_checks(run)
    if not checks:
        raise engine_subsets.NoOffer("nothing flags specific rows of this plan")
    if not att["consequences"].get("ok"):
        raise engine_subsets.NoOffer("the plan crashed in rehearsal")
    if att.get("surgical_of"):
        raise engine_subsets.NoOffer("this is already a surgical subset")
    effects = _effects_cached(att["effects_path"], att.get("effects_sha256") or "")
    base = workspaces.db_path(run.get("workspace", workspaces.DEMO))
    g = engine_graph.build(effects, str(base))
    offer = engine_subsets.propose(effects, g, base, checks)
    check = next(c for c in checks if c["title"] == offer.check_title)
    contract = run.get("contract") or {}
    work = [p for p in contract.get("promises") or [] if p["kind"] == "obligation"] if contract.get("status") == "ready" else []
    if work:   # the part that's kept must do some of what was asked, or there is nothing worth approving
        done = engine_contracts.evaluate(work, base, offer.effects)
        if not any(r.get("after") is not None and r["after"] < r["today"] for r in done):
            raise engine_subsets.NoOffer("the part that passes every check does none of the work the request asked for")
    elif contract.get("status") == "ready":
        raise engine_subsets.NoOffer("the request asks for no change, so no part of this plan is needed")
    try:   # Proof of Effect: which lines of the plan produced the rows being cut
        prov = json.loads(open(att["effects_path"].replace("effects.json", "provenance.json")).read())
        wrote, chose = prov.get("rows") or {}, prov.get("decided") or {}
        stmts: dict[tuple[int, str], int] = {}
        for ui in offer.dropped_units:
            for nid in g.units[ui]:
                n = g.nodes[nid]
                if n.kind != "row":
                    continue
                j = chose.get(n.table, {}).get(str(n.rowid))     # the read that chose this row, if the plan chose by query
                key = (j, "chose") if j is not None else (wrote.get(n.table, {}).get(str(n.rowid)), "wrote")
                if key[0] is not None:
                    stmts[key] = stmts.get(key, 0) + 1
        offer.caused_by = [{"i": i, "rows": k, "how": how} for (i, how), k in sorted(stmts.items(), key=lambda x: -x[1])[:5]]
    except (OSError, ValueError, KeyError):
        pass
    return check, offer


def _surgical_offer(run: dict) -> None:
    """Attach 'these N of M changes are right' to a run under review, if the engine can prove it."""
    try:
        check, offer = _surgical_propose(run)
        payload = {"offer": offer.public(), "check": {"title": check["title"], "source": check["source"]}}
        _emit(run, "verify", f"Surgical approval available: {offer.units_kept:,} of {offer.units_total:,} changes keep the check",
              f"Checked by {check['source']}: {check['title']}. The other {offer.units_dropped:,} would be cut out, whole.")
    except engine_subsets.NoOffer as e:
        payload = {"none": str(e)}
    except Exception as e:  # noqa: BLE001 - the offer is an extra; never let it break a review
        payload = {"none": f"the engine couldn't compute a subset ({type(e).__name__})"}
    with LOCK:
        run["surgical"] = payload
        _save(run)


def _surgical_job(run: dict, offer: engine_subsets.Offer, check: dict) -> None:
    workspaces.use(run.get("workspace", workspaces.DEMO))
    prev = run["attempts"][-1]
    try:
        _status(run, "rehearsing")
        _emit(run, "sandbox", f"Re-rehearsing the {offer.units_kept:,} changes that keep the check, in a fresh sandbox",
              "The subset is rebuilt by trusted code and measured by phase 2 like any rehearsal; no plan code runs.")
        with SANDBOX_SLOTS:
            res = sandbox.measure_effects(offer.effects, f"Surgical subset of attempt {prev['n']}")
        code = (f"# Surgical subset of attempt {prev['n']}: kept {offer.units_kept} of {offer.units_total} units of work.\n"
                f"# Cut by {check['source']}: {check['title']}\n" + prev["code"])
        _add_attempt(run, res, code, f"Surgical subset: kept {offer.units_kept:,} of {offer.units_total:,}",
                     surgical_of=prev["n"], surgical={"check": check, "offer": offer.public()})
        with LOCK:
            run["surgical"] = {"applied_to": prev["n"], "offer": offer.public(), "check": {"title": check["title"], "source": check["source"]}}
            run["verdict"] = None
            _save(run)
        att = run["attempts"][-1]
        _emit(run, "sandbox", f"Subset measured in {res['id']}: {att['consequences'].get('payments', {}).get('count', 0):,} refunds, "
                              f"{sum(t['updated'] + t['deleted'] + t['inserted'] for t in att['consequences'].get('tables', {}).values()):,} rows")
        if config.INFERENCE_KEY and _verify_budget():
            _verify(run)
        else:
            with LOCK:
                run["flags"] = att["flags"]
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
    out["decision"] = engine_verdict.decide(run)
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
    isolation: Literal["container", "vultr_vm"] = "container"


class ApproveIn(BaseModel):
    approver: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class StrikeIn(BaseModel):
    index: int = Field(ge=0, le=20)
    by: str | None = Field(default=None, max_length=80)
    reason: str = Field(min_length=10, max_length=500)


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
            "vm_isolation": vultr_vm.configured(), "sample_postgres": bool(config.SAMPLE_PG_URL), "vm_plan": config.VM_PLAN if vultr_vm.configured() else None,
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


class VultrImportIn(BaseModel):
    api_key: str = Field(min_length=20, max_length=64)
    name: str = Field(default="My Vultr fleet", max_length=60)


@app.post("/api/workspaces/vultr")
def import_vultr_fleet(body: VultrImportIn, req: Request):
    """Rehearse against a double of YOUR Vultr fleet: one read-only listing with your key, which is never stored or logged."""
    _rate_limit(req, per_hour=6, kind="Vultr import")
    try:
        instances = vultr_import.fleet(body.api_key)
    except vultr_import.ImportError_ as e:
        raise HTTPException(400, str(e)) from None
    except Exception:  # noqa: BLE001 - never echo anything that could include the key
        raise HTTPException(502, "Couldn't reach the Vultr API") from None
    if not instances:
        raise HTTPException(400, "That account has no instances to rehearse against")
    cost = sum(i["_monthly_cents"] for i in instances)
    entry = workspaces.create(body.name, vultr_import.to_sqlite(instances), kind="vultr",
                              description=f"{len(instances)} Vultr servers · ${cost / 100:,.2f}/month · imported read-only")
    return {**entry, "servers": len(instances), "monthly_cost_cents": cost}


class PgImportIn(BaseModel):
    url: str = Field(min_length=12, max_length=500)
    schema_name: str = Field(default="public", max_length=63, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    name: str = Field(default="My Postgres", max_length=60)


@app.post("/api/workspaces/postgres")
def import_postgres(body: PgImportIn, req: Request):
    """Rehearse against a double of YOUR PostgreSQL database: one read-only copy; the connection string is never kept."""
    _rate_limit(req, per_hour=6, kind="Postgres import")
    try:
        data, meta = pg_import.import_db(body.url, body.schema_name)
    except pg_import.PgImportError as e:
        raise HTTPException(400, str(e)) from None
    except Exception:  # noqa: BLE001 - never echo anything that could include the connection string
        raise HTTPException(502, "Couldn't import that database") from None
    try:
        entry = workspaces.create(body.name, data, kind="postgres", extra={"pks": meta["pks"], "types": meta["types"]},
                                  description=f"{meta['server']} · {meta['tables']} tables, {meta['rows']:,} rows · imported read-only")
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {k: v for k, v in entry.items() if k not in ("pks", "types")}


@app.post("/api/workspaces/postgres/sample")
def import_sample_postgres(req: Request):
    """One click: the same read-only import, from a small sample SaaS database that runs inside this deployment."""
    _rate_limit(req, per_hour=10, kind="Postgres import")
    if not config.SAMPLE_PG_URL:
        raise HTTPException(404, "No sample database on this server")
    try:
        data, meta = pg_import.import_db(config.SAMPLE_PG_URL, "public", allow_private=True)  # our own configured, internal host
    except pg_import.PgImportError as e:
        raise HTTPException(503, f"The sample database isn't ready: {e}") from None
    entry = workspaces.create("Sample SaaS (Postgres)", data, kind="postgres", extra={"pks": meta["pks"], "types": meta["types"]},
                              description=f"{meta['server']} · {meta['tables']} tables, {meta['rows']:,} rows · imported read-only")
    return {k: v for k, v in entry.items() if k not in ("pks", "types")}


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
    _contract_start(run)
    threading.Thread(target=_agent_job, args=(run,), daemon=True).start()
    return {"id": run["id"]}


@app.post("/api/runs/manual")
def create_manual_run(body: ManualIn, req: Request):
    _rate_limit(req)
    if not workspaces.exists(body.workspace):
        raise HTTPException(404, "unknown workspace")
    if body.isolation == "vultr_vm":
        if not vultr_vm.configured():
            raise HTTPException(400, "Dedicated Vultr VMs are not configured on this server")
        if sandbox.uses_browser(body.code):
            raise HTTPException(400, "Browser rehearsals run in the gVisor browser sandbox, not on a dedicated VM")
        _rate_limit(req, per_hour=6, kind="dedicated VM")
    run = _new_run(body.task, "manual", body.workspace)
    if body.isolation == "vultr_vm":
        run["isolation"] = "vultr_vm"
    _contract_start(run)
    threading.Thread(target=_manual_job, args=(run, body.code), daemon=True).start()
    return {"id": run["id"]}


@app.get("/api/vm/{token}/bundle")
def vm_bundle(token: str):
    """Called once by a rehearsal VM to fetch its plan, database copy and harness (one-time token)."""
    data = vultr_vm.take_bundle(token)
    if data is None:
        raise HTTPException(404, "unknown or used token")
    return Response(data, media_type="application/gzip")


@app.post("/api/vm/{token}/result")
async def vm_result(token: str, req: Request):
    """Called once by a rehearsal VM to return the modified database copy and the plan's recorded intents."""
    if int(req.headers.get("content-length") or 0) > vultr_vm.MAX_RESULT_BYTES:
        raise HTTPException(413, "result too large")
    if not vultr_vm.put_result(token, await req.body()):
        raise HTTPException(404, "unknown or used token")
    return {"ok": True}


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
            "sandbox": {k: (c.get("sandbox") or {}).get(k) for k in ("id", "runtime", "wall_ms", "profile", "isolation")} if a else None,
            "kind": _kind(c) if a else None, "workspace_kind": workspaces.kind(r.get("workspace", workspaces.DEMO)),
            "decision": {k: d[k] for k in ("decision", "headline")} if (d := engine_verdict.decide(r)) else None,
            "cut": next(({"kept": a2["surgical"]["offer"]["units_kept"], "total": a2["surgical"]["offer"]["units_total"]}
                         for a2 in r["attempts"] if a2.get("surgical")), None)}


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
    def caught(r) -> bool:  # locked by policy, or the AI verifier objected (and it wasn't applied anyway)
        v = (r.get("verdict") or {})
        ai = v.get("verdict") in ("concerns", "dangerous") and v.get("headline") != "Verifier could not finish"
        return any(f["severity"] == "critical" for f in last(r)["flags"]) or ai
    stopped = [r for r in runs if last(r) and (r["status"] == "rejected" or (r["status"] == "review" and caught(r)))]
    fixed = [r for r in runs if len(r["attempts"]) > 1]
    prevented = sum(last(r)["consequences"].get("payments", {}).get("total_cents", 0) for r in stopped)
    prevented += sum(max(0, r["attempts"][0]["consequences"].get("payments", {}).get("total_cents", 0)
                         - last(r)["consequences"].get("payments", {}).get("total_cents", 0)) for r in fixed)
    rows_protected = sum(sum(t["deleted"] + t["updated"] for t in last(r)["consequences"].get("tables", {}).values()) for r in stopped)
    return {"rehearsals": sum(len(r["attempts"]) for r in runs), "runs": len(runs), "applied": sum(1 for r in runs if r["status"] == "applied"),
            "stopped": len(stopped), "money_prevented_cents": prevented, "rows_protected": rows_protected,
            "rolled_back": sum(1 for r in runs if r.get("rolled_back_by")),
            # the Consequence Engine
            "contracts": sum(1 for r in runs if (r.get("contract") or {}).get("status") == "ready"),
            "promises_broken": sum(1 for r in runs if last(r) for p in (last(r)["consequences"].get("contract") or {}).get("promises", [])
                                   if p.get("status") == "broken"),
            "cuts": len(cut_runs := [r for r in runs if any(a.get("surgical_of") for a in r["attempts"])]),
            "cut_kept_cents": sum((r.get("surgical") or {}).get("offer", {}).get("kept", {}).get("money_cents", 0) for r in cut_runs),
            "proven": sum(1 for r in runs for a in r["attempts"] if (a["consequences"].get("provenance") or {}).get("status") in ("proven", "derived"))}


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


def _good_rehearsals(ws: str, exclude: str) -> list[tuple[str, dict]]:
    """Recent rehearsals in this workspace that the AI judged correct and nobody applied yet (applied ones are in today's data)."""
    out = []
    for r in sorted(RUNS.values(), key=lambda x: x["created_at"], reverse=True):
        if r["id"] == exclude or r.get("workspace", workspaces.DEMO) != ws or (r.get("verdict") or {}).get("verdict") != "looks_right":
            continue
        if r["status"] == "applied" or not r["attempts"]:
            continue
        try:
            out.append((r["id"], json.loads(open(r["attempts"][-1]["effects_path"]).read())))
        except (OSError, ValueError, KeyError):
            continue
        if len(out) >= 10:
            break
    return out


@app.post("/api/runs/{rid}/promote")
def promote_catch(rid: str, req: Request, body: PromoteIn | None = None):
    """Turn the AI verifier's catch into a learned rule: a deterministic check that runs on every future rehearsal."""
    _rate_limit(req, per_hour=30, kind="rule")
    run = _get(rid)
    rule = (run.get("verdict") or {}).get("rule") or {}
    if not rule.get("sql"):
        raise HTTPException(409, "This run's verifier didn't propose a rule")
    try:
        ws = run.get("workspace", workspaces.DEMO)
        rules.check_against_good(rules.check_sql(rule["sql"], ws), ws, _good_rehearsals(ws, rid))
        r = rules.add(ws, rule.get("title", ""), rule["sql"], rid, (body.by if body else "") or "")
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


@app.post("/api/runs/{rid}/surgical")
def surgical_run(rid: str, req: Request):
    """Keep the part of the plan that passes the check, cut the rest out whole, and re-rehearse what's left."""
    _rate_limit(req, per_hour=30, kind="surgical")
    run = _get(rid)
    with LOCK:
        if run["status"] != "review":
            raise HTTPException(409, f"Run is {run['status']}, not awaiting review")
    workspaces.use(run.get("workspace", workspaces.DEMO))
    try:
        check, offer = _surgical_propose(run)
    except engine_subsets.NoOffer as e:
        raise HTTPException(409, f"No surgical approval: {e}") from None
    with LOCK:
        if run["status"] != "review":
            raise HTTPException(409, f"Run is {run['status']}")
        run["status"] = "rehearsing"
        _save(run)
    threading.Thread(target=_surgical_job, args=(run, offer, check), daemon=True).start()
    return {"id": rid, "offer": offer.public()}


@app.post("/api/runs/{rid}/recheck")
def recheck_run(rid: str, req: Request):
    """Run the AI verifier again, live: when it couldn't finish, or to replace a reused verdict. Never changes the plan or its effects."""
    _rate_limit(req, per_hour=30, kind="re-check")
    run = _get(rid)
    with LOCK:
        v = run.get("verdict") or {}
        if run["status"] != "review" or not (v.get("headline") == "Verifier could not finish" or v.get("cached")):
            raise HTTPException(409, "Only a run whose verifier couldn't finish, or that shows an earlier verdict, can be checked again")
    if not _verify_budget():
        raise HTTPException(429, "Today's AI-check budget for this public demo is used up")
    with LOCK:
        if run["status"] != "review":
            raise HTTPException(409, f"Run is {run['status']}")
        run["status"] = "verifying"
        run["verdict"] = None
        run["force_live"] = True
        _save(run)
    threading.Thread(target=_verify, args=(run,), daemon=True).start()
    return {"id": rid}


@app.post("/api/runs/{rid}/contract/strike")
def strike_promise(rid: str, body: StrikeIn):
    """A person disagrees with a promise: it stops being enforced, with their name and reason in the record. The
    latest rehearsal is re-checked against what is left, with no AI, and the decision and any cut are recomputed."""
    run = _get(rid)
    who = " ".join((body.by or "").split())[:80] or "Approver"
    reason = " ".join(body.reason.split())[:500]
    with LOCK:
        contract = run.get("contract") or {}
        if run["status"] != "review" or contract.get("status") != "ready" or not run["attempts"]:
            raise HTTPException(409, "Only a ready contract of a run under review can be changed")
        if body.index >= len(contract["promises"]):
            raise HTTPException(404, "No such promise")
        if len(contract["promises"]) == 1:
            raise HTTPException(409, "That is the last promise; reject the run instead")
        gone = contract["promises"].pop(body.index)
        contract.setdefault("struck", []).append({**gone, "by": who, "reason": reason, "at": time.time()})
        att = run["attempts"][-1]
        _save(run)
    c = att["consequences"]
    _contract_check(run, c, att.get("effects_path"))
    flags = _gate_flags(c, run)
    v = run.get("verdict") or {}
    with LOCK:
        att["flags"] = flags
        run["flags"] = flags
        if v.get("raised_from") and not any(f["severity"] == "critical" for f in flags):
            v["verdict"] = v.pop("raised_from")       # the deterministic check that overruled the jury is gone
        run["surgical"] = None
        _save(run)
    _emit(run, "human", f"{who} struck a promise from the contract: {gone['text']}", f"Reason: {reason}")
    if not att.get("surgical_of"):
        _surgical_offer(run)
    return _public(run)


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
        if workspaces.kind(run.get("workspace", workspaces.DEMO)) == "vultr":
            raise HTTPException(409, "This is a double of your Vultr fleet. The public demo never holds your key, so it can't change "
                                     "your account: use the rehearsal to decide, then act in Vultr.")
        if workspaces.kind(run.get("workspace", workspaces.DEMO)) == "postgres":
            raise HTTPException(409, "This is a double of your Postgres database. The public demo never keeps your connection string: "
                                     "apply with 'Export as SQL' (drift-guarded) through your own pipeline.")
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
        broken = next((f for f in att["flags"] if f.get("rule") == "contract" and f["title"].startswith("Breaks a promise")), None)
        if broken and len(note) < 10:
            raise HTTPException(422, "A promise made before the plan is broken. Strike it with a reason, or write a note saying why you approve anyway.")
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


# Which part of this evidence record serves which control (for auditors; not legal advice).
CONTROLS = {
    "EU AI Act Art. 14 (human oversight)": "A named person decided on the measured consequences before anything happened "
        "(approval.approver, approval.notes); critical findings lock approval; overruling the AI verifier needs a written reason.",
    "EU AI Act Art. 12 (record-keeping)": "The timeline logs every step automatically: rehearsal, measurement, checks, verdicts, "
        "decision and apply, with timestamps.",
    "SOC 2 CC8.1 (change management)": "Each change was tested before production (attempts[].consequences, measured in a separate "
        "sandbox), authorized (approval, two people above thresholds) and applied exactly as approved (effects_sha256 bound to "
        "the approval; drift-checked apply_result).",
    "Tamper evidence": "Every step is one entry of a SHA-256 hash chain (chain.entries) whose head is signed with the server's "
        "Ed25519 key (chain.signature). Changing, removing or reordering anything breaks verification: POST /api/evidence/verify, "
        "or verify_evidence() in the Python SDK, with the public key from GET /api/evidence/key.",
}


def _evidence_steps(run: dict) -> list[tuple[str, object]]:
    """The run as an ordered list of steps, for the hash chain."""
    steps: list[tuple[str, object]] = [("request", {k: run.get(k) for k in ("id", "task", "mode", "workspace", "created_at", "agent_model", "verifier_model")})]
    if run.get("contract"):
        steps.append(("contract", {k: run["contract"].get(k) for k in ("status", "model", "today", "promises", "withdrawn", "struck", "cross_check", "reason")}))
    for a in run["attempts"]:
        c = a["consequences"]
        steps.append(("rehearsal", {
            "n": a["n"], "sandbox_id": a["sandbox_id"], "plan": a["code"], "plan_sha256": a.get("plan_sha256"),
            "effects_sha256": a.get("effects_sha256"), "surgical_of": a.get("surgical_of"), "flags": a["flags"],
            "measured": {k: c.get(k) for k in ("ok", "error", "tables", "row_counts", "payments", "emails", "blocked", "audit", "sandbox", "measured_by")},
            "graph": c.get("graph"), "proof_of_effect": c.get("provenance"), "contract": c.get("contract")}))
    if run.get("surgical"):
        steps.append(("surgical", {k: v for k, v in run["surgical"].items() if k != "offer"} | {"offer": {k: v for k, v in ((run["surgical"].get("offer") or {}).items()) if k != "dropped_units"}}))
    if run.get("verdict"):
        steps.append(("jury", run["verdict"]))
    if (run.get("contract") or {}).get("struck"):
        steps.append(("contract_struck", run["contract"]["struck"]))
    decision = engine_verdict.decide(run)
    if decision:
        steps.append(("decision", decision))
    if run.get("approval") or run.get("rejection"):
        steps.append(("sign_off", {"approval": run.get("approval"), "rejection": run.get("rejection"), "approvals": run.get("approvals")}))
    if run.get("apply_result"):
        steps.append(("applied", run["apply_result"]))
    return steps


_EVIDENCE_KEYS = ("ok", "error", "tables", "row_counts", "payments", "emails", "blocked", "audit", "sandbox", "measured_by", "provenance", "graph", "contract")


def _evidence(run: dict) -> dict:
    with LOCK:
        steps = _evidence_steps(run)
        out = {
            "evidence_version": 2, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run": {k: run.get(k) for k in ("id", "task", "mode", "status", "created_at", "agent_model", "verifier_model", "error")},
            "attempts": [{"n": a["n"], "sandbox_id": a["sandbox_id"], "plan_sha256": a.get("plan_sha256"), "effects_sha256": a.get("effects_sha256"),
                          "plan": a["code"], "summary": a["summary"], "flags": a["flags"],
                          "consequences": {k: a["consequences"].get(k) for k in _EVIDENCE_KEYS}}
                         for a in run["attempts"]],
            "contract": run.get("contract"), "verdict": run.get("verdict"), "decision": engine_verdict.decide(run),
            "approval": run.get("approval"), "apply_result": run.get("apply_result"),
            "timeline": run["events"],
            "controls": CONTROLS,
        }
    out["chain"] = engine_evidence.seal(steps, config.DATA_DIR)
    return out


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


@app.get("/api/runs/{rid}/provenance")
def run_provenance(rid: str, attempt: int = 0):
    """Proof of Effect: which statement of the plan caused which change, proven by replay."""
    run = _get(rid)
    if not run["attempts"]:
        raise HTTPException(404, "no rehearsal yet")
    att = run["attempts"][attempt - 1] if 0 < attempt <= len(run["attempts"]) else run["attempts"][-1]
    path = str(att.get("effects_path") or "").replace("effects.json", "provenance.json")
    try:
        d = json.loads(open(path).read())
    except (OSError, ValueError):
        raise HTTPException(404, "no provenance for this rehearsal") from None
    d.pop("rows", None)   # the full row map stays on the server; statements and the unexplained list are what people read
    return d


@app.get("/api/runs/{rid}/graph")
def run_graph(rid: str, attempt: int = 0, unit: int | None = None):
    """The Effect Graph of a rehearsal: every consequence as a node, linked into units of work. With `unit`, just
    that unit of work: its consequences, the unchanged rows that tie them together, and every link with its reason."""
    run = _get(rid)
    if not run["attempts"]:
        raise HTTPException(404, "no rehearsal yet")
    att = run["attempts"][attempt - 1] if 0 < attempt <= len(run["attempts"]) else run["attempts"][-1]
    path = str(att.get("effects_path") or "").replace("effects.json", "graph.json")
    try:
        g = json.loads(open(path).read())
    except (OSError, ValueError):
        raise HTTPException(404, "no graph for this rehearsal") from None
    if unit is None:
        return g
    if not 0 <= unit < len(g.get("units") or []):
        raise HTTPException(404, "no such unit of work")
    own = set(g["units"][unit]["nodes"])
    edges = [e for e in g.get("edges") or [] if e[0] in own or e[1] in own]
    ids = own | {x for e in edges for x in e[:2]}
    nodes = g.get("nodes") or {}
    return {"unit": unit, "units": len(g["units"]), "summary": g.get("summary"),
            "nodes": [nodes[i] for i in sorted(ids) if i in nodes], "edges": edges}


@app.get("/api/runs/{rid}/effects.sql")
def effects_sql(rid: str):
    """The measured data changes as a portable SQL script, for teams that apply through their own migration pipeline."""
    run = _get(rid)
    if not run["attempts"]:
        raise HTTPException(404, "no rehearsal yet")
    att = run["attempts"][-1]
    if not att["consequences"].get("ok"):
        raise HTTPException(409, "This rehearsal failed; there are no measured changes to export")
    try:
        effects = _effects_cached(att["effects_path"], att.get("effects_sha256") or "")
    except (OSError, ValueError) as e:
        raise HTTPException(404, "effects not available") from e
    ws = workspaces.entry(run.get("workspace", workspaces.DEMO))
    meta = {"run_id": rid, "status": run["status"], "task": run["task"], "plan_sha256": att.get("plan_sha256"), "effects_sha256": att.get("effects_sha256"),
            "pks": ws.get("pks") or {}, "types": ws.get("types") or {}}
    return Response(sql_export.export(effects, meta), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="stunt-double-{rid}.sql"'})


@app.get("/api/runs/{rid}/evidence")
def evidence(rid: str):
    """Everything an auditor needs for one run: request, plan, fingerprints, measured consequences, checks, verdict,
    approval (who, when, policy in force) and what was applied."""
    from fastapi.responses import JSONResponse
    return JSONResponse(_evidence(_get(rid)), headers={"Content-Disposition": f'attachment; filename="stunt-double-evidence-{rid}.json"'})


@app.get("/api/evidence/key")
def evidence_key():
    """The public key that signs every evidence record from this server."""
    return engine_evidence.public_key(config.DATA_DIR)


@app.post("/api/evidence/verify")
def verify_evidence(body: dict):
    """Check a downloaded evidence record: every entry of the chain, and the signature, against this server's key."""
    return engine_evidence.verify(body, engine_evidence.public_key(config.DATA_DIR)["public_key"])


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
