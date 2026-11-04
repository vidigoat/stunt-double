"""`sd`: rehearse plans from the terminal or CI.

  sd rehearse plan.py --task "Refund double charges"     exit 0 = ready for review, 2 = blocked by policy, 1 = error
  sd status <run_id>                                      current status and consequences
  sd wait <run_id> [--timeout 3600]                       block until a human decides; exit 0 only if applied
  sd connectors                                           APIs plans may call

Server: --url or $STUNT_DOUBLE_URL (default http://localhost:8000).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import Rehearsal, StuntDouble


def _print(r: Rehearsal, as_json: bool) -> None:
    if as_json:
        print(json.dumps({k: v for k, v in r.__dict__.items() if k != "raw"}, indent=2, default=str))
        return
    print(f"run       {r.run_id}  ({r.status})")
    print(f"outcome   {r.summary}")
    if r.approvals_required > 1:
        print(f"approvals {r.approvals_required} different people required")
    for b in r.blocked_by_policy:
        print(f"BLOCKED   {b}")
    for w in r.warnings:
        print(f"warning   {w}")
    if r.verdict:
        print(f"verdict   {r.verdict.get('verdict')}: {r.verdict.get('headline')}")
    print(f"review    {r.approval_url}")


def main(argv: list[str] | None = None, http=None) -> int:
    ap = argparse.ArgumentParser(prog="sd", description="Rehearse AI agent plans before they touch production.")
    ap.add_argument("--url", default=os.environ.get("STUNT_DOUBLE_URL", "http://localhost:8000"))
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rehearse", help="rehearse a plan file (defines run(ctx))")
    r.add_argument("plan", type=Path)
    r.add_argument("--task", required=True, help="the request the plan is judged against")
    s = sub.add_parser("status")
    s.add_argument("run_id")
    w = sub.add_parser("wait")
    w.add_argument("run_id")
    w.add_argument("--timeout", type=float, default=3600)
    sub.add_parser("connectors")
    a = ap.parse_args(argv)
    sd = StuntDouble(a.url, http=http)
    try:
        if a.cmd == "rehearse":
            res = sd.rehearse(a.task, a.plan.read_text())
            _print(res, a.json)
            return 2 if res.blocked else 0
        if a.cmd == "status":
            _print(sd.status(a.run_id), a.json)
            return 0
        if a.cmd == "wait":
            final = sd.wait_for_decision(a.run_id, timeout=a.timeout)
            print(final)
            return 0 if final == "applied" else 3
        if a.cmd == "connectors":
            for c in sd.connectors():
                print(f"{c['name']:10} {', '.join(c['methods']):12} https://{c['host']}/…   {c['description']}")
            return 0
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
