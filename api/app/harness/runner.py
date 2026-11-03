"""Stunt Double rehearsal harness. Runs INSIDE the sandbox container (stdlib only).

Contract:
  /work/business.db   a throwaway copy of the business database (read-write)
  /work/plan.py       the agent's plan, defining run(ctx)
  /work/out/          results: consequences.json (summary) and effects.json (exact changes)

Payments and email are recorders: nothing leaves the sandbox. Any other attempt to reach the
outside world is logged as a blocked side effect (the container has no network anyway).
"""
import contextlib
import io
import json
import os
import resource
import socket
import sqlite3
import sys
import time
import traceback

WORK = "/work"
OUT = os.path.join(WORK, "out")
BLOCKED: list[dict] = []
PAYMENTS: list[dict] = []
EMAILS: list[dict] = []
LOGS: list[str] = []

# ---- tripwires: log, then refuse, any attempt to reach the network ----------------------------
_real_connect = socket.socket.connect


def _tripwire_connect(self, address):  # noqa: ANN001
    BLOCKED.append({"kind": "network", "target": str(address)})
    raise PermissionError(f"Stunt Double sandbox: outbound connection to {address} blocked")


socket.socket.connect = _tripwire_connect  # type: ignore[assignment]
_real_getaddrinfo = socket.getaddrinfo


def _tripwire_getaddrinfo(host, *a, **k):  # noqa: ANN001
    BLOCKED.append({"kind": "dns", "target": str(host)})
    raise PermissionError(f"Stunt Double sandbox: DNS lookup for {host} blocked")


socket.getaddrinfo = _tripwire_getaddrinfo  # type: ignore[assignment]


# ---- the ctx object the agent's plan receives -------------------------------------------------
class Payments:
    def refund(self, charge_id: int, amount_cents: int, reason: str = "") -> dict:
        rec = {"op": "refund", "charge_id": int(charge_id), "amount_cents": int(amount_cents), "reason": str(reason)[:200]}
        PAYMENTS.append(rec)
        return {"id": f"rehearsal_refund_{len(PAYMENTS)}", "status": "recorded"}


class Email:
    def send(self, to: str, subject: str, body: str) -> dict:
        EMAILS.append({"to": str(to), "subject": str(subject)[:300], "body": str(body)[:5000]})
        return {"id": f"rehearsal_email_{len(EMAILS)}", "status": "recorded"}


class Ctx:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.payments = Payments()
        self.email = Email()

    def log(self, *parts) -> None:  # noqa: ANN002
        LOGS.append(" ".join(str(p) for p in parts)[:500])


# ---- snapshot / diff --------------------------------------------------------------------------
def snapshot(db: sqlite3.Connection) -> dict:
    snap = {}
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for t in tables:
        cols = [r[1] for r in db.execute(f'PRAGMA table_info("{t}")')]
        rows = {}
        for row in db.execute(f'SELECT rowid, * FROM "{t}"'):
            rows[row[0]] = dict(zip(cols, row[1:]))
        snap[t] = {"cols": cols, "rows": rows}
    return snap


def diff(before: dict, after: dict) -> dict:
    out = {}
    for t in sorted(set(before) | set(after)):
        b = before.get(t, {"rows": {}})["rows"]
        a = after.get(t, {"rows": {}})["rows"]
        if t not in after:
            out[t] = {"dropped": True, "deleted": [{"rowid": k, "before": v} for k, v in b.items()], "inserted": [], "updated": []}
            continue
        deleted = [{"rowid": k, "before": b[k]} for k in b.keys() - a.keys()]
        inserted = [{"rowid": k, "after": a[k]} for k in a.keys() - b.keys()]
        updated = []
        for k in b.keys() & a.keys():
            if b[k] != a[k]:
                changed = [c for c in a[k] if b[k].get(c) != a[k].get(c)]
                updated.append({"rowid": k, "before": b[k], "after": a[k], "changed": changed})
        if deleted or inserted or updated or t not in before:
            out[t] = {"dropped": False, "created": t not in before, "deleted": sorted(deleted, key=lambda r: r["rowid"]),
                      "inserted": sorted(inserted, key=lambda r: r["rowid"]), "updated": sorted(updated, key=lambda r: r["rowid"])}
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    started = time.time()
    guards = {
        "env_keys": sorted(os.environ.keys()),
        "uid": os.getuid(),
        "hostname": socket.gethostname(),
        "root_writable": os.access("/", os.W_OK),
    }
    # Soft memory ceiling below the container's hard cap, so the harness survives to report what happened.
    mem_mb = int(os.environ.get("SD_PLAN_MEM_MB", "160"))
    orig_soft, orig_hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, orig_hard))
    db = sqlite3.connect(os.path.join(WORK, "business.db"), isolation_level=None)
    db.execute("PRAGMA foreign_keys = OFF")
    before = snapshot(db)
    stdout = io.StringIO()
    ok, error = True, None
    try:
        db.execute("BEGIN")
        src = open(os.path.join(WORK, "plan.py")).read()
        ns: dict = {"__name__": "plan"}
        with contextlib.redirect_stdout(stdout):
            exec(compile(src, "plan.py", "exec"), ns)  # noqa: S102 - this IS the sandbox
            if "run" not in ns:
                raise RuntimeError("plan.py must define run(ctx)")
            ns["run"](Ctx(db))
        if db.in_transaction:
            db.execute("COMMIT")
    except BaseException as e:  # noqa: BLE001
        ok = False
        msg = "".join(traceback.format_exception_only(type(e), e)).strip()[:2000]
        if isinstance(e, MemoryError):
            msg = f"MemoryError: plan exceeded the sandbox memory ceiling ({mem_mb} MB) and was stopped"
        error = {"message": msg, "traceback": traceback.format_exc()[-3000:]}
    # Diff even on failure: shows what the plan did before it crashed (never applied - it failed).
    resource.setrlimit(resource.RLIMIT_AS, (orig_soft, orig_hard))
    after = snapshot(db)
    changes = diff(before, after)
    with contextlib.suppress(Exception):
        if db.in_transaction:
            db.execute("ROLLBACK")

    tables = {}
    for t, d in changes.items():
        tables[t] = {
            "dropped": d["dropped"], "deleted": len(d["deleted"]), "inserted": len(d["inserted"]), "updated": len(d["updated"]),
            "rows_before": len(before.get(t, {"rows": {}})["rows"]), "rows_after": len(after.get(t, {"rows": {}})["rows"]),
            "changed_columns": sorted({c for u in d["updated"] for c in u["changed"]}),
            "samples": {"deleted": d["deleted"][:8], "inserted": d["inserted"][:8], "updated": d["updated"][:8]},
        }
    consequences = {
        "ok": ok, "error": error, "stdout": stdout.getvalue()[-4000:], "logs": LOGS[-100:],
        "duration_ms": int((time.time() - started) * 1000),
        "tables": tables,
        "row_counts": {t: {"before": len(before[t]["rows"]), "after": len(after.get(t, {"rows": {}})["rows"])} for t in before},
        "payments": {"count": len(PAYMENTS), "total_cents": sum(p["amount_cents"] for p in PAYMENTS), "samples": PAYMENTS[:25]},
        "emails": {"count": len(EMAILS), "samples": EMAILS[:25]},
        "blocked": BLOCKED[:50],
        "guards": guards,
    }
    with open(os.path.join(OUT, "consequences.json"), "w") as f:
        json.dump(consequences, f, default=str)
    with open(os.path.join(OUT, "effects.json"), "w") as f:
        json.dump({"changes": changes, "payments": PAYMENTS, "emails": EMAILS}, f, default=str)


if __name__ == "__main__":
    main()
    sys.exit(0)
