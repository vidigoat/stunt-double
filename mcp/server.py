"""Stunt Double MCP server: let ANY agent (Claude Code, Cursor, custom) rehearse before it acts.

Tools
  describe_business()          tables + the plan API (ctx.db, payments, email, http, browser, vultr), so the agent can write a plan
  rehearse(task, plan_code)    run the plan on a throwaway copy in an isolated sandbox; returns the consequences,
                               policy flags and verdict, plus a link where a HUMAN approves
  get_run_status(run_id)       has a human approved / rejected it yet? what was applied?
  list_connectors()            which external APIs plans may call (ctx.http) and with which methods
  request_undo(run_id)         ask humans to roll back an applied run's data changes (two people must approve)

There is deliberately no approve tool: an agent can never approve its own plan.

Run:
  python server.py                       # stdio (Claude Code: `claude mcp add stunt-double -- python mcp/server.py`)
  python server.py --http --port 8001    # streamable HTTP at /mcp (hosted on the Vultr VM)
Env:
  STUNT_DOUBLE_API     API base URL (default http://localhost:8000)
  STUNT_DOUBLE_PUBLIC  public site URL used in approval links (default = API base)
  STUNT_DOUBLE_ALLOWED_HOSTS  comma-separated public hostnames allowed to reach /mcp over HTTP
"""
import argparse
import os
import time

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

API = os.environ.get("STUNT_DOUBLE_API", "http://localhost:8000").rstrip("/")
PUBLIC = os.environ.get("STUNT_DOUBLE_PUBLIC", API).rstrip("/")
ACTIVE = {"queued", "planning", "rehearsing", "verifying", "applying"}
# DNS-rebinding protection stays ON; the public hostname (e.g. 1-2-3-4.sslip.io) is allowed explicitly.
HOSTS = [h.strip() for h in os.environ.get("STUNT_DOUBLE_ALLOWED_HOSTS", "").split(",") if h.strip()]
SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *HOSTS, *[f"{h}:*" for h in HOSTS]],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*", *[f"https://{h}" for h in HOSTS]],
)

mcp = FastMCP(
    "stunt-double",
    instructions=(
        "Before you change real business data, issue refunds or send emails, call `rehearse` with your plan. "
        "It runs on a throwaway copy inside an isolated sandbox and tells you exactly what would happen. "
        "If the result has blocking flags or the verdict is not 'looks_right', fix your plan and rehearse again. "
        "If its decision is 'cut', part of the plan is right: keep_only_what_is_right re-rehearses just that part. "
        "To know what a request means before you write a plan, call what_does_this_mean. "
        "Only a human can approve: share the approval_url with them. Never claim a plan was applied unless "
        "get_run_status says status == 'applied'."
    ),
    transport_security=SECURITY,
)


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=30)


def _summarise(run: dict) -> dict:
    att = run["attempts"][-1] if run.get("attempts") else None
    c = att["consequences"] if att else {}
    flags = (att or {}).get("flags", [])
    return {
        "run_id": run["id"],
        "status": run["status"],
        "approval_url": f"{PUBLIC}/app?run={run['id']}",
        "ran_ok": c.get("ok"),
        "error": (c.get("error") or {}).get("message") if isinstance(c.get("error"), dict) else c.get("error"),
        "money_out_usd": c.get("payments", {}).get("total_cents", 0) / 100,
        "refunds": c.get("payments", {}).get("count", 0),
        "emails": c.get("emails", {}).get("count", 0),
        "email_samples": c.get("emails", {}).get("samples", [])[:2],
        "row_changes": {t: {k: v[k] for k in ("deleted", "inserted", "updated", "rows_before")} for t, v in c.get("tables", {}).items()},
        "blocked_by_policy": [f["title"] for f in flags if f["severity"] == "critical"],
        "warnings": [f["title"] for f in flags if f["severity"] != "critical"],
        "blocked_side_effects": c.get("blocked", []),
        "verdict": run.get("verdict"),
        "api_calls": (c.get("http") or {}).get("count", 0),
        "approvals_required": (att or {}).get("approvals_required", 1),
        "irreversible": c.get("irreversible"),
        "vultr_fleet": ({k: (c["cloud"].get(k) if k not in ("deleted", "stopped", "resized") else [x.get("label") for x in c["cloud"].get(k, [])])
                         for k in ("deleted", "stopped", "resized", "monthly_savings_cents", "production_touched")}
                        if (c.get("cloud") or {}).get("servers_before") else None),
        "browser_steps": [f"{b['n']}. {b['action']} {b['target']}" for b in (c.get("browser") or {}).get("steps", [])] or None,
        "learned_rules_broken": [r["title"] for r in c.get("rules", []) if r.get("violations")] or None,
        "decision": ({k: run["decision"][k] for k in ("decision", "headline")} | {"layers": {x["key"]: f"{x['status']}: {x['reason']}" for x in run["decision"]["layers"]}}
                     if run.get("decision") else None),
        "intent_contract": [{"promise": p["text"], "kind": p["kind"], "status": p["status"], "rows_today": p["today"], "rows_after": p.get("after")}
                            for p in (c.get("contract") or {}).get("promises", [])] or None,
        "proof_of_effect": (c.get("provenance") or {}).get("status"),
        "surgical_offer": ({k: (run["surgical"]["offer"] or {}).get(k) for k in ("units_kept", "units_total", "kept", "dropped")}
                           if (run.get("surgical") or {}).get("offer") and not (att or {}).get("surgical_of") else None),
        "plan_sha256": (att or {}).get("plan_sha256"),
        "sandbox": c.get("sandbox"),
        "approval": run.get("approval"),
        "apply_result": run.get("apply_result"),
        "next_step": ("Part of this plan is right: call keep_only_what_is_right to re-rehearse just that part, or fix the plan."
                      if (run.get("decision") or {}).get("decision") == "cut" and run["status"] == "review"
                      else "Fix the plan: it is blocked by policy." if any(f["severity"] == "critical" for f in flags)
                      else "Ask a human to review and approve at approval_url." if run["status"] == "review"
                      else f"Run is {run['status']}."),
    }


@mcp.tool()
def describe_business(workspace: str = "demo") -> dict:
    """Tables, columns, row counts and the plan API (ctx.db / ctx.payments / ctx.email / ctx.http) of a workspace."""
    with _client() as c:
        return c.get("/api/schema", params={"ws": workspace}).raise_for_status().json()


@mcp.tool()
def list_workspaces() -> dict:
    """Databases you can rehearse against: the demo business and any uploaded SQLite databases."""
    with _client() as c:
        return c.get("/api/workspaces").raise_for_status().json()


@mcp.tool()
def rehearse(task: str, plan_code: str, wait_seconds: int = 120, workspace: str = "demo") -> dict:
    """Rehearse a plan on a throwaway copy of the business in an isolated sandbox (no network, no secrets).

    Args:
        task: the human's request in plain English (used to check the outcome matches the intent).
        plan_code: a Python module defining `def run(ctx):` (see describe_business for the ctx API).
        wait_seconds: how long to wait for the rehearsal and verification.
        workspace: which database to rehearse against (see list_workspaces).
    Returns the measured consequences, policy flags, verdict and an approval_url for a human.
    """
    with _client() as c:
        r = c.post("/api/runs/manual", json={"task": task, "code": plan_code, "workspace": workspace})
        if r.status_code >= 400:
            return {"error": r.json().get("detail", r.text)}
        rid = r.json()["id"]
        deadline = time.time() + max(5, min(wait_seconds, 600))
        run = c.get(f"/api/runs/{rid}").json()
        while run["status"] in ACTIVE and time.time() < deadline:
            time.sleep(0.5)
            run = c.get(f"/api/runs/{rid}").json()
        return _summarise(run)


@mcp.tool()
def what_does_this_mean(task: str, workspace: str = "demo") -> dict:
    """Before you write a plan: the promises any correct plan for this request must keep, written from the request,
    the business glossary and the schema (the work to be done, with today's count, and what must not be touched).
    A second model from another lab reads it too; if they disagree, the request is ambiguous: ask the human.
    Your plan's rehearsal is checked against these same promises."""
    with _client() as c:
        r = c.post("/api/contract/preview", json={"task": task, "workspace": workspace}, timeout=200)
        if r.status_code >= 400:
            return {"error": r.json().get("detail", r.text)}
        d = r.json()
        return {"promises": [{"promise": p["text"], "kind": "work to do" if p["kind"] == "obligation" else "must not happen",
                              "rows_today": p["today"]} for p in d.get("promises", [])],
                "cross_check": d.get("cross_check"), "written_by": d.get("model")}


@mcp.tool()
def keep_only_what_is_right(run_id: str, wait_seconds: int = 180) -> dict:
    """When a rehearsal's decision is "cut", re-rehearse only the units of work that pass every check that fired.

    The Consequence Engine drops each wrong refund together with its email, rebuilds the rest without running your
    plan again, and measures and checks it in a fresh sandbox. It does not approve anything: a human still does, at
    approval_url."""
    with _client() as c:
        before = len(c.get(f"/api/runs/{run_id}").json().get("attempts") or [])
        r = c.post(f"/api/runs/{run_id}/surgical")
        if r.status_code >= 400:
            return {"error": r.json().get("detail", r.text)}
        deadline = time.time() + max(5, min(wait_seconds, 600))
        run = c.get(f"/api/runs/{run_id}").json()
        while (len(run.get("attempts") or []) <= before or run["status"] in ACTIVE) and time.time() < deadline:
            time.sleep(0.5)
            run = c.get(f"/api/runs/{run_id}").json()
        return _summarise(run)


@mcp.tool()
def list_connectors() -> dict:
    """External APIs a plan may call with ctx.http (host + allowed methods). Credentials are added by Stunt Double after approval."""
    with _client() as c:
        return c.get("/api/connectors").raise_for_status().json()


@mcp.tool()
def request_undo(run_id: str) -> dict:
    """Ask humans to roll back an APPLIED run's data changes. Creates a rollback that two different people must approve.
    Refunds, emails and API calls that already happened cannot be undone and are listed as irreversible."""
    with _client() as c:
        r = c.post(f"/api/runs/{run_id}/rollback")
        if r.status_code >= 400:
            return {"error": r.json().get("detail", r.text)}
        return _summarise(c.get(f"/api/runs/{r.json()['id']}").json())


@mcp.tool()
def get_run_status(run_id: str) -> dict:
    """Current status of a rehearsal: awaiting approval, applied (with what was applied), rejected or drifted."""
    with _client() as c:
        r = c.get(f"/api/runs/{run_id}")
        if r.status_code == 404:
            return {"error": "run not found"}
        return _summarise(r.raise_for_status().json())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP at /mcp instead of stdio")
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 only inside a container behind a proxy")
    ap.add_argument("--port", type=int, default=8001)
    a = ap.parse_args()
    if a.http:
        mcp.settings.host, mcp.settings.port = a.host, a.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
