"""Connectors: how a recorded HTTP intent becomes a real call, after approval.

Inside the sandbox a plan can only *describe* a call (`ctx.http.post(url, json=...)`). On approval, Stunt Double
replays each call through the connector whose host matches, injecting that connector's credentials server-side.
The sandbox never sees a secret, and a call to a host without a connector is blocked by policy (fails closed).

Connectors are configured in SD_CONNECTORS (JSON) or fall back to the demo set below, whose deliveries land in
Stunt Double's own "outbox" so the demo is fully observable without third-party accounts.
"""
import json
import os
import sqlite3
import time

import httpx

from . import config

DEMO_CONNECTORS = {
    "slack": {"label": "Slack · #ops channel", "host": "hooks.slack.com", "methods": ["POST"], "deliver_to": "outbox:slack",
              "description": "Team notifications"},
    "crm": {"label": "Bean CRM", "host": "api.beancrm.example", "methods": ["POST", "PATCH"], "deliver_to": "outbox:crm",
            "description": "Customer notes and tags"},
}

OUTBOX_DB = config.DATA_DIR / "outbox.db"


def registry() -> dict:
    raw = os.environ.get("SD_CONNECTORS")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    return DEMO_CONNECTORS


def public() -> list[dict]:
    """Connector list for the UI / agents: never includes secrets or delivery targets."""
    return [{"name": k, "label": v.get("label", k), "host": v["host"], "methods": v.get("methods", ["POST"]),
             "description": v.get("description", ""),
             "credential": "injected after approval" if v.get("token_env") or v.get("url_env") else "demo outbox (no credential needed)"}
            for k, v in registry().items()]


def match(call: dict) -> tuple[str, dict] | tuple[None, None]:
    for name, c in registry().items():
        if call.get("host") == c["host"].lower():
            return name, c
    return None, None


def check(call: dict) -> str | None:
    """Why this call can't be replayed, or None if it can."""
    if call.get("scheme") != "https":
        return "only https calls can be replayed"
    name, c = match(call)
    if not name:
        return f"no connector for {call.get('host') or 'this URL'}"
    if call.get("method") not in c.get("methods", ["POST"]):
        return f"{call.get('method')} is not allowed for {c.get('label', name)}"
    return None


# ---- delivery ---------------------------------------------------------------------------------------------
def _outbox() -> sqlite3.Connection:
    db = sqlite3.connect(OUTBOX_DB)
    db.execute("CREATE TABLE IF NOT EXISTS deliveries (id INTEGER PRIMARY KEY, connector TEXT, method TEXT, path TEXT, body TEXT, "
               "run_id TEXT, created_at TEXT, status INTEGER)")
    return db


def deliver(call: dict, run_id: str) -> dict:
    name, c = match(call)
    if not name or check(call):
        return {"connector": name, "ok": False, "error": check(call) or "no connector"}
    target = c.get("deliver_to", "")
    if target.startswith("outbox:"):
        db = _outbox()
        with db:
            db.execute("INSERT INTO deliveries (connector, method, path, body, run_id, created_at, status) VALUES (?,?,?,?,?,?,?)",
                       (name, call["method"], call.get("path", ""), json.dumps(call.get("json"), default=str)[:65536], run_id,
                        time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), 200))
        return {"connector": name, "ok": True, "status": 200, "delivered_to": target}
    # Real delivery: the URL and credential come from the server's environment, never from the plan.
    #   {"url_env": "SD_SLACK_WEBHOOK_URL", "append_path": false}   or   {"url_env": "SD_CRM_BASE_URL", "token_env": "SD_CRM_TOKEN", "append_path": true}
    base = os.environ.get(c.get("url_env", ""), "")
    if not base.startswith("https://"):
        return {"connector": name, "ok": False, "error": "connector has no https delivery URL configured"}
    url = base.rstrip("/") + (call.get("path", "") if c.get("append_path") else "")
    token = os.environ.get(c.get("token_env", ""), "")
    headers = {**call.get("headers", {}), **({"Authorization": f"Bearer {token}"} if token else {})}
    try:
        r = httpx.request(call["method"], url, json=call.get("json"), headers=headers, timeout=10)
        return {"connector": name, "ok": r.status_code < 400, "status": r.status_code}
    except httpx.HTTPError as e:
        return {"connector": name, "ok": False, "error": str(e)[:200]}


def deliveries(limit: int = 100) -> dict:
    db = _outbox()
    rows = db.execute("SELECT id, connector, method, path, body, run_id, created_at, status FROM deliveries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    total = db.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
    return {"count": total, "deliveries": [dict(zip(["id", "connector", "method", "path", "body", "run_id", "created_at", "status"], r, strict=False)) for r in rows]}


def reset() -> None:
    OUTBOX_DB.unlink(missing_ok=True)
