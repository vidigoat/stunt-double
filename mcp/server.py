"""Stunt Double MCP server: let ANY agent (Claude Code, Cursor, custom) rehearse before it acts.

Tools
  describe_business()          tables + the plan API, so the agent can write a plan
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
        "plan_sha256": (att or {}).get("plan_sha256"),
        "sandbox": c.get("sandbox"),
        "approval": run.get("approval"),
        "apply_result": run.get("apply_result"),
        "next_step": ("Fix the plan: it is blocked by policy." if any(f["severity"] == "critical" for f in flags)
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
