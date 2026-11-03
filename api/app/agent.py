"""The two AI roles, both on Vultr Serverless Inference.

1. The OPS AGENT (the thing being supervised): turns a request into a Python plan, then
   uses rehearsals to debug it. It never touches production.
2. The VERIFIER (Stunt Double itself): reads the rehearsal's real consequences, investigates
   the data with read-only queries, and tells a non-technical approver whether the outcome
   matches what they asked for, in plain English.
"""
import json
import sqlite3
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
    return OpenAI(base_url=config.INFERENCE_BASE_URL, api_key=config.INFERENCE_KEY, timeout=120)


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
def _loop(model: str, messages: list, tools: list, handlers: dict[str, Callable], emit: Callable, max_turns: int, stop_tool: str | None = None):
    ai = client()
    for _ in range(max_turns):
        resp = ai.chat.completions.create(model=model, messages=messages, tools=tools, temperature=0.2)
        msg = resp.choices[0].message
        messages.append({"role": "assistant", "content": msg.content or "",
                         **({"tool_calls": [tc.model_dump() for tc in msg.tool_calls]} if msg.tool_calls else {})})
        if not msg.tool_calls:
            return msg.content or "", None
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == stop_tool:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": "recorded"})
                return None, args
            handler = handlers.get(name)
            result = handler(**args) if handler else {"error": f"unknown tool {name}"}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)[:12000]})
    return "Stopped: too many steps.", None


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
        return compact_consequences(rehearse(code, summary))

    final, _ = _loop(config.AGENT_MODEL, messages, SCHEMA_TOOLS + [SUBMIT_TOOL],
                     {"get_schema": _schema, "run_query": _query, "submit_plan": _submit}, emit, max_turns=14)
    return final or "", messages


def verify(task: str, code: str, consequences: dict, emit: Callable) -> dict:
    messages = [{"role": "system", "content": VERIFIER_SYSTEM},
                {"role": "user", "content": json.dumps({"human_request": task, "plan_code": code,
                                                        "measured_consequences": compact_consequences(consequences)}, default=str)}]

    def _query(sql: str):
        emit("verify", "Checking the outcome against your request", sql)
        return run_query(sql)

    _, verdict = _loop(config.VERIFIER_MODEL, messages, [SCHEMA_TOOLS[1], VERDICT_TOOL], {"run_query": _query}, emit,
                       max_turns=10, stop_tool="verdict")
    return verdict or {"verdict": "concerns", "headline": "Verifier could not finish", "summary": "Review manually.", "concerns": []}


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
