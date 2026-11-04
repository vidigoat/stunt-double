"""The two AI roles, both on Vultr Serverless Inference.

1. The OPS AGENT (the thing being supervised): turns a request into a Python plan, then
   uses rehearsals to debug it. It never touches production.
2. The VERIFIER (Stunt Double itself): reads the rehearsal's real consequences, investigates
   the data with read-only queries, and tells a non-technical approver whether the outcome
   matches what they asked for, in plain English.
"""
import json
import re
import sqlite3
import time
import uuid
from typing import Callable

from openai import OpenAI

from . import config

CTX_DOC = """Your plan is a Python module that defines `def run(ctx):`.
- ctx.db: sqlite3 connection to the business database. A transaction is already open; do NOT commit or rollback.
- ctx.payments.refund(charge_id: int, amount_cents: int, reason: str): issue a refund through BeanPay.
  When you refund a charge also mark it in the DB: UPDATE charges SET status='refunded', refunded_at=<now> WHERE id=?
- ctx.email.send(to: str, subject: str, body: str): email a customer. Write the real final text (no template placeholders).
- ctx.log(*values): leave a note for the reviewer.
Standard library only. There is no network access."""

OPS_SYSTEM = f"""You are the operations AI agent for Bean There Coffee Co., an online coffee subscription shop.
You complete operations requests by writing a Python plan. Before any human approves it, Stunt Double rehearses
your plan on a throwaway copy of the business and shows the human the consequences.

{CTX_DOC}

Work like this: inspect the schema, look at the relevant data with run_query, then call submit_plan.
You will get the rehearsal results back. If the plan crashed, fix it and submit again. When the rehearsal ran
cleanly, reply with a short final message describing what the plan does. Today's date is 2026-11-03;
"last week" means 2026-10-26 through 2026-11-01."""

VERIFIER_SYSTEM = """You are Stunt Double's verifier. An AI operations agent wrote a plan for a human's request.
The plan was rehearsed on a throwaway copy of the business and you are given its REAL measured consequences.
Your job is to protect the business: decide whether the consequences match what the human actually asked for.

Investigate before you judge. Use run_query (read-only, on the data as it was BEFORE the plan ran) to test
whether the affected rows really satisfy the human's intent. For example, if refunds were issued for "double
charges", check whether each refunded charge really shares an order with another charge. Look for over-reach
(too many rows), under-reach, wrong people, wrong amounts, destructive changes nobody asked for, and anything a
customer would find embarrassing in the emails. Be concrete: give counts and examples.

Finish by calling the verdict tool exactly once."""

SCHEMA_TOOLS = [
    {"type": "function", "function": {"name": "get_schema", "description": "Tables, columns and row counts of the business database.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "run_query", "description": "Run ONE read-only SQL SELECT. Returns up to 50 rows.",
                                      "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}}},
]
SUBMIT_TOOL = {"type": "function", "function": {
    "name": "submit_plan", "description": "Submit a Python plan (defining run(ctx)) for rehearsal in the sandbox.",
    "parameters": {"type": "object", "properties": {
        "code": {"type": "string", "description": "Full Python source defining run(ctx)."},
        "summary": {"type": "string", "description": "One sentence: what the plan does."}}, "required": ["code", "summary"]}}}
VERDICT_TOOL = {"type": "function", "function": {
    "name": "verdict", "description": "Report your judgement to the human approver.",
    "parameters": {"type": "object", "properties": {
        "verdict": {"type": "string", "enum": ["looks_right", "concerns", "dangerous"]},
        "headline": {"type": "string", "description": "<= 12 words, plain English, for a non-technical manager."},
        "summary": {"type": "string", "description": "2-3 plain-English sentences: what would happen if approved."},
        "concerns": {"type": "array", "items": {"type": "object", "properties": {
            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "title": {"type": "string"}, "detail": {"type": "string"},
            "affected_count": {"type": "integer"}}, "required": ["severity", "title", "detail"]}},
        "fix_instructions": {"type": "string", "description": "If not looks_right: exact guidance for the ops agent to fix the plan."}},
        "required": ["verdict", "headline", "summary", "concerns"]}}}


def client() -> OpenAI:
    if not config.INFERENCE_KEY:
        raise RuntimeError("VULTR_INFERENCE_KEY is not set: Vultr Serverless Inference is required for the agent")
    return OpenAI(base_url=config.INFERENCE_BASE_URL, api_key=config.INFERENCE_KEY, timeout=config.LLM_TIMEOUT_S, max_retries=0)


# ---- read-only data access for both roles ----------------------------------------------------
def _ro() -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{config.PROD_DB}?mode=ro", uri=True)
    db.execute("PRAGMA query_only = ON")
    return db


def get_schema() -> dict:
    db = _ro()
    out = {}
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols = [f"{r[1]} {r[2]}" for r in db.execute(f'PRAGMA table_info("{t}")')]
        out[t] = {"columns": cols, "rows": db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]}
    return out


def run_query(sql: str) -> dict:
    s = sql.strip().rstrip(";")
    if not s.lower().startswith(("select", "with")) or ";" in s:
        return {"error": "Only a single read-only SELECT is allowed."}
    try:
        cur = _ro().execute(s)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(51)
        return {"columns": cols, "rows": rows[:50], "truncated": len(rows) > 50}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:300]}


def compact_consequences(c: dict) -> dict:
    """What the agents get to see from a rehearsal (bounded size)."""
    return {
        "ran_ok": c.get("ok"), "error": (c.get("error") or {}).get("message") if isinstance(c.get("error"), dict) else c.get("error"),
        "row_changes": {t: {k: v[k] for k in ("deleted", "inserted", "updated", "rows_before", "rows_after", "changed_columns", "dropped")}
                        for t, v in c.get("tables", {}).items()},
        "sample_changed_rows": {t: v["samples"] for t, v in c.get("tables", {}).items()},
        "refunds": {"count": c["payments"]["count"], "total_usd": c["payments"]["total_cents"] / 100, "samples": c["payments"]["samples"][:10]},
        "emails": {"count": c["emails"]["count"], "samples": c["emails"]["samples"][:5]},
        "blocked_side_effects": c.get("blocked", []),
        "plan_log": c.get("logs", [])[-20:], "stdout_tail": (c.get("stdout") or "")[-800:],
    }


# ---- tool-calling loop -------------------------------------------------------------------------
_TEXT_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>|```(?:json)?\s*(\{\s*\"name\".*?\})\s*```", re.S)


def _parse_args(raw) -> dict:
    """Arguments as a dict, tolerating double-encoded JSON and trailing junk from some open models."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    for candidate in (raw, raw.strip().rstrip(",")):
        try:
            val = json.loads(candidate)
            return json.loads(val) if isinstance(val, str) else (val if isinstance(val, dict) else {})
        except (json.JSONDecodeError, TypeError):
            continue
    return {}


def _calls_from_text(content: str) -> list[dict]:
    """Some models emit tool calls as text (<tool_call>{...}</tool_call> or a ```json block). Recover them."""
    calls = []
    for m in _TEXT_CALL.finditer(content or ""):
        try:
            obj = json.loads(m.group(1) or m.group(2))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("name"):
            calls.append({"id": f"text_{uuid.uuid4().hex[:8]}", "name": obj["name"], "arguments": obj.get("arguments", obj.get("parameters", {}))})
    return calls


def _complete(ai, models: list[str], messages: list, tools: list, emit: Callable):
    """One completion with retries and model fallback. Returns (model_used, message)."""
    last = None
    for model in models:
        for attempt in range(3):
            try:
                resp = ai.chat.completions.create(model=model, messages=messages, tools=tools, temperature=0.2,
                                                  max_tokens=config.MAX_TOKENS)
                return model, resp.choices[0].message
            except Exception as e:  # noqa: BLE001
                last = e
                status = getattr(e, "status_code", None)
                if status in (400, 401, 403, 404, 422):  # not transient: bad request / auth / unknown model -> next model
                    break
                time.sleep(min(8, 1.5 * 2 ** attempt))
        emit("system", f"Model {model} unavailable, trying the next one", str(last)[:200])
    raise RuntimeError(f"All models failed: {last}")


def _loop(models: str | list[str], messages: list, tools: list, handlers: dict[str, Callable], emit: Callable, max_turns: int,
          stop_tool: str | None = None, required_tool: str | None = None):
    """Tool-calling loop. `required_tool`: nudge the model (once) if it tries to stop without calling it."""
    ai = client()
    models = [m.strip() for m in (models.split(",") if isinstance(models, str) else models) if m.strip()]
    called: set[str] = set()
    nudged = False
    for _ in range(max_turns):
        _, msg = _complete(ai, models, messages, tools, emit)
        native = [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments} for tc in (msg.tool_calls or [])]
        calls = native or _calls_from_text(msg.content or "")
        if native:
            messages.append({"role": "assistant", "content": msg.content or None, "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] if isinstance(c["arguments"], str) else json.dumps(c["arguments"])}}
                for c in calls]})
        else:
            messages.append({"role": "assistant", "content": msg.content or ""})
        if not calls:
            if required_tool and required_tool not in called and not nudged:
                nudged = True
                messages.append({"role": "user", "content": f"You have not called `{required_tool}` yet. Call it now; do not reply with text."})
                continue
            return msg.content or "", None
        for c in calls:
            name, args = c["name"], _parse_args(c["arguments"])
            called.add(name)
            if name == stop_tool:
                if native:
                    messages.append({"role": "tool", "tool_call_id": c["id"], "content": "recorded"})
                return None, args
            handler = handlers.get(name)
            try:
                result = handler(**args) if handler else {"error": f"unknown tool {name}"}
            except TypeError as e:  # wrong/missing arguments: tell the model instead of crashing
                result = {"error": f"bad arguments for {name}: {e}"}
            payload = json.dumps(result, default=str)[:12000]
            if native:
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": payload})
            else:
                messages.append({"role": "user", "content": f"Result of {name}:\n{payload}"})
    return "Stopped: too many steps.", None


def clean_code(code: str) -> str:
    """Strip markdown fences models sometimes wrap code in."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", code or "", re.S)
    return (m.group(1) if m else code or "").strip() + "\n"


def ops_agent(task: str, rehearse: Callable[[str, str], dict], emit: Callable, feedback: str | None = None,
              history: list | None = None) -> tuple[str, list]:
    """Runs the ops agent. `rehearse(code, summary)` dispatches to the sandbox and returns consequences."""
    messages = history or [{"role": "system", "content": OPS_SYSTEM}, {"role": "user", "content": task}]
    if feedback:
        messages.append({"role": "user", "content": f"Stunt Double reviewed your rehearsed plan and the human asked you to fix it:\n{feedback}\nSubmit a corrected plan."})

    def _schema():
        emit("agent", "Reading the database schema")
        return get_schema()

    def _query(sql: str):
        emit("agent", "Looking at the data", sql)
        return run_query(sql)

    def _submit(code: str, summary: str = ""):
        code = clean_code(code)
        if "def run(" not in code:
            return {"error": "Your plan must define `def run(ctx):`. Submit the full module."}
        return compact_consequences(rehearse(code, summary))

    final, _ = _loop(config.AGENT_MODEL, messages, SCHEMA_TOOLS + [SUBMIT_TOOL],
                     {"get_schema": _schema, "run_query": _query, "submit_plan": _submit}, emit,
                     max_turns=config.AGENT_MAX_TURNS, required_tool="submit_plan")
    return final or "", messages


def verify(task: str, code: str, consequences: dict, emit: Callable) -> dict:
    messages = [{"role": "system", "content": VERIFIER_SYSTEM},
                {"role": "user", "content": json.dumps({"human_request": task, "plan_code": code,
                                                        "measured_consequences": compact_consequences(consequences)}, default=str)}]

    def _query(sql: str):
        emit("verify", "Checking the outcome against your request", sql)
        return run_query(sql)

    _, verdict = _loop(config.VERIFIER_MODEL, messages, [SCHEMA_TOOLS[1], VERDICT_TOOL], {"run_query": _query}, emit,
                       max_turns=10, stop_tool="verdict", required_tool="verdict")
    if not verdict:
        return {"verdict": "concerns", "headline": "Verifier could not finish", "summary": "Review the details manually before approving.", "concerns": []}
    verdict.setdefault("concerns", [])
    if verdict.get("verdict") not in ("looks_right", "concerns", "dangerous"):
        verdict["verdict"] = "concerns"
    verdict["concerns"] = [c for c in verdict["concerns"] if isinstance(c, dict) and c.get("title")]
    for c in verdict["concerns"]:
        c.setdefault("detail", ""); c["severity"] = c.get("severity") if c.get("severity") in ("high", "medium", "low") else "medium"
    return verdict


# ---- deterministic red flags (no AI needed) -----------------------------------------------------
def red_flags(c: dict) -> list[dict]:
    flags = []
    for t, v in c.get("tables", {}).items():
        if v.get("dropped"):
            flags.append({"severity": "critical", "title": f"Drops the whole {t} table", "detail": f"{v['rows_before']:,} rows would be lost."})
        elif v["deleted"] and v["rows_before"] and v["deleted"] / v["rows_before"] >= 0.05:
            flags.append({"severity": "critical", "title": f"Deletes {v['deleted']:,} of {v['rows_before']:,} {t}",
                          "detail": f"{v['deleted'] / v['rows_before']:.0%} of the table would be gone."})
    for b in c.get("blocked", []):
        flags.append({"severity": "high", "title": f"Tried to reach {b['target']}", "detail": f"Blocked {b['kind']} attempt. Nothing left the sandbox."})
    if not c.get("ok"):
        msg = c.get("error", {}).get("message") if isinstance(c.get("error"), dict) else c.get("error")
        flags.append({"severity": "high", "title": "The plan crashed", "detail": str(msg)[:300]})
    return flags
