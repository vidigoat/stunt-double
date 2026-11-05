"""Stunt Double Python SDK: rehearse a plan before it touches production, then wait for a human decision."""
from __future__ import annotations

import inspect
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

import httpx

__all__ = ["StuntDouble", "Rehearsal", "Plan"]
__version__ = "0.1.0"
_ACTIVE = {"queued", "planning", "rehearsing", "verifying", "applying"}
_DECIDED = {"applied", "rejected", "drifted", "failed"}


@dataclass
class Rehearsal:
    run_id: str
    status: str
    approval_url: str
    money_out_usd: float
    refunds: int
    emails: int
    api_calls: int
    rows_changed: int
    blocked_by_policy: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    approvals_required: int = 1
    verdict: dict | None = None
    decision: dict | None = None     # the Consequence Engine: approve | review | blocked | cut, with a reason per layer
    error: str | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_by_policy) or self.error is not None

    @property
    def summary(self) -> str:
        if self.error:
            return f"The plan failed in the sandbox: {self.error}"
        return (f"If approved: ${self.money_out_usd:,.2f} across {self.refunds} refunds, {self.emails} emails, "
                f"{self.api_calls} API calls, {self.rows_changed} rows changed.")


class Plan:
    """A function `run(ctx)` that can be rehearsed. Created with `@sd.plan(task)`."""

    def __init__(self, client: StuntDouble, task: str, fn: Callable):
        self.client, self.task, self.fn = client, task, fn
        src = textwrap.dedent(inspect.getsource(fn))
        lines = [ln for ln in src.splitlines() if not ln.lstrip().startswith("@")]
        self.code = "\n".join(lines).replace(f"def {fn.__name__}(", "def run(", 1) + "\n"

    def rehearse(self, wait_seconds: float = 120) -> Rehearsal:
        return self.client.rehearse(self.task, self.code, wait_seconds=wait_seconds)


class StuntDouble:
    def __init__(self, base_url: str, http: httpx.Client | None = None, timeout: float = 30, workspace: str = "demo"):
        self.base_url = base_url.rstrip("/")
        self.workspace = workspace
        self.http = http or httpx.Client(base_url=self.base_url, timeout=timeout)

    # -- discovery ----------------------------------------------------------------------------------------
    def describe(self) -> dict:
        """Tables, columns and the plan API (ctx.db, ctx.payments, ctx.email, ctx.http)."""
        return self.http.get("/api/schema", params={"ws": self.workspace}).raise_for_status().json()

    def workspaces(self) -> list[dict]:
        return self._get("/api/workspaces")["workspaces"]

    def connectors(self) -> list[dict]:
        return self._get("/api/connectors")["connectors"]

    # -- rehearse --------------------------------------------------------------------------------------------
    def plan(self, task: str) -> Callable[[Callable], Plan]:
        return lambda fn: Plan(self, task, fn)

    def rehearse(self, task: str, code: str, wait_seconds: float = 120) -> Rehearsal:
        r = self.http.post("/api/runs/manual", json={"task": task, "code": code, "workspace": self.workspace})
        if r.status_code >= 400:
            raise RuntimeError(r.json().get("detail", r.text))
        run_id = r.json()["id"]
        deadline = time.monotonic() + wait_seconds
        run = self._get(f"/api/runs/{run_id}")
        while run["status"] in _ACTIVE and time.monotonic() < deadline:
            time.sleep(0.4)
            run = self._get(f"/api/runs/{run_id}")
        return self._rehearsal(run)

    # -- after a human looks at it ---------------------------------------------------------------------------
    def status(self, run_id: str) -> Rehearsal:
        return self._rehearsal(self._get(f"/api/runs/{run_id}"))

    def what_does_this_mean(self, task: str) -> dict:
        """The promises any correct plan for this request must keep, written before any plan exists, and a second
        model's reading of the same request (if they disagree, the request is ambiguous)."""
        r = self.http.post("/api/contract/preview", json={"task": task, "workspace": self.workspace}, timeout=200)
        r.raise_for_status()
        return r.json()

    def keep_only_what_is_right(self, run_id: str, wait_seconds: float = 180) -> Rehearsal:
        """When the decision is "cut", re-rehearse just the part of the plan that passes every check. Approves nothing."""
        before = len(self._get(f"/api/runs/{run_id}").get("attempts") or [])
        self.http.post(f"/api/runs/{run_id}/surgical").raise_for_status()
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            run = self._get(f"/api/runs/{run_id}")
            if len(run.get("attempts") or []) > before and run["status"] not in ("queued", "planning", "rehearsing", "verifying"):
                return self._rehearsal(run)
            time.sleep(1)
        raise TimeoutError(f"The subset of {run_id} wasn't ready within {wait_seconds}s")

    def wait_for_decision(self, run_id: str, timeout: float = 3600, poll: float = 2.0) -> str:
        """Block until a human approves (and it's applied), rejects, or it drifts/fails. Returns the final status."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self._get(f"/api/runs/{run_id}")["status"]
            if status in _DECIDED:
                return status
            time.sleep(poll)
        raise TimeoutError(f"No decision on {run_id} within {timeout}s")

    # -- internals -------------------------------------------------------------------------------------------
    def _get(self, path: str) -> Any:
        r = self.http.get(path)
        r.raise_for_status()
        return r.json()

    def _rehearsal(self, run: dict) -> Rehearsal:
        att = run["attempts"][-1] if run.get("attempts") else {}
        c = att.get("consequences", {})
        flags = att.get("flags", [])
        err = c.get("error")
        return Rehearsal(
            run_id=run["id"], status=run["status"], approval_url=f"{self.base_url}/app?run={run['id']}",
            money_out_usd=c.get("payments", {}).get("total_cents", 0) / 100, refunds=c.get("payments", {}).get("count", 0),
            emails=c.get("emails", {}).get("count", 0), api_calls=(c.get("http") or {}).get("count", 0),
            rows_changed=sum(t["deleted"] + t["updated"] + t["inserted"] for t in c.get("tables", {}).values()),
            blocked_by_policy=[f["title"] for f in flags if f["severity"] == "critical"],
            warnings=[f["title"] for f in flags if f["severity"] != "critical"],
            approvals_required=att.get("approvals_required", 1), verdict=run.get("verdict"), decision=run.get("decision"),
            error=(err or {}).get("message") if isinstance(err, dict) else err, raw=run,
        )
