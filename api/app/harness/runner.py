"""Stunt Double rehearsal harness. Runs INSIDE sandbox containers (stdlib only). Two phases, two containers:

  python runner.py run       PHASE 1 (untrusted). Executes the agent's plan.
      /work/work.db             a throwaway copy of the business database (read-write)
      /work/plan.py             the agent's plan, defining run(ctx)
      /work/out/intents.json    what the plan ASKED to do: refunds, emails, logs, blocked attempts

  python runner.py measure   PHASE 2 (trusted). A fresh container the plan never ran in.
      /in/before.db  (ro)       the database before the plan ran
      /in/after.db   (ro)       the database after the plan ran (copied out of phase 1)
      /in/intents.json (ro)     phase 1's intents, treated as untrusted DATA and validated
      /out/consequences.json    what we show the approver
      /out/effects.json         exactly what is replayed on approval

The plan shares a Python process with phase 1, so it could tamper with anything recorded there. That is why the
row diff, the audit and both output files are produced by phase 2: the approver sees, and the apply step replays,
only what trusted code measured. Payments and email are recorders; nothing leaves either sandbox.
"""
import contextlib
import email.utils
import io
import json
import os
import re
import resource
import socket
import sqlite3
import sys
import time
import traceback
import urllib.parse
from collections import Counter

MAX_INTENTS = 20000

# =============================================================================================
# PHASE 1: run the plan
# =============================================================================================
BLOCKED: list[dict] = []
PAYMENTS: list[dict] = []
EMAILS: list[dict] = []
HTTP: list[dict] = []
CLOUD: list[dict] = []
LOGS: list[str] = []
SECRET_HEADERS = {"authorization", "cookie", "x-api-key", "api-key", "x-auth-token", "proxy-authorization"}


def _tripwire_connect(self, address):  # noqa: ANN001
    BLOCKED.append({"kind": "network", "target": str(address)[:200]})
    raise PermissionError(f"Stunt Double sandbox: outbound connection to {address} blocked")


def _tripwire_getaddrinfo(host, *a, **k):  # noqa: ANN001
    BLOCKED.append({"kind": "dns", "target": str(host)[:200]})
    raise PermissionError(f"Stunt Double sandbox: DNS lookup for {host} blocked")


class Payments:
    def refund(self, charge_id: int, amount_cents: int, reason: str = "") -> dict:
        PAYMENTS.append({"op": "refund", "charge_id": int(charge_id), "amount_cents": int(amount_cents), "reason": str(reason)[:200]})
        return {"id": f"rehearsal_refund_{len(PAYMENTS)}", "status": "recorded"}


class Email:
    def send(self, to: str, subject: str, body: str, kind: str | None = None) -> dict:
        EMAILS.append({"to": str(to)[:320], "subject": str(subject)[:300], "body": str(body)[:5000], "kind": kind if kind in ("marketing", "transactional") else None})
        return {"id": f"rehearsal_email_{len(EMAILS)}", "status": "recorded"}


class Http:
    """Any HTTP API call becomes a recorded intent. Nothing is sent from the sandbox. On approval the server replays it
    through a configured connector and injects the real credentials then; auth headers set here are dropped."""
    def request(self, method: str, url: str, json: object = None, headers: dict | None = None) -> dict:
        hdrs = {str(k)[:100]: str(v)[:500] for k, v in (headers or {}).items() if str(k).lower() not in SECRET_HEADERS}
        HTTP.append({"method": str(method).upper()[:10], "url": str(url)[:2000], "json": json, "headers": hdrs})
        return {"id": f"rehearsal_http_{len(HTTP)}", "status": "recorded"}

    def post(self, url: str, json: object = None, headers: dict | None = None) -> dict:
        return self.request("POST", url, json, headers)

    def put(self, url: str, json: object = None, headers: dict | None = None) -> dict:
        return self.request("PUT", url, json, headers)

    def patch(self, url: str, json: object = None, headers: dict | None = None) -> dict:
        return self.request("PATCH", url, json, headers)

    def delete(self, url: str, headers: dict | None = None) -> dict:
        return self.request("DELETE", url, None, headers)


VULTR_PLANS = {  # plan -> (vcpu, ram MB, $/month cents): real Vultr Cloud Compute prices
    "vc2-1c-0.5gb": (1, 512, 350), "vc2-1c-1gb": (1, 1024, 500), "vc2-1c-2gb": (1, 2048, 1000), "vc2-2c-2gb": (2, 2048, 1500),
    "vc2-2c-4gb": (2, 4096, 2000), "vc2-4c-8gb": (4, 8192, 4000), "vc2-6c-16gb": (6, 16384, 8000),
}


class Vultr:
    """A double of the Vultr API over the business's fleet (the `servers` table of the clone). Calls change the double;
    phase 2 measures exactly which servers would be deleted, stopped or resized, and what it does to the monthly bill."""
    def __init__(self, db: sqlite3.Connection):
        self._db = db

    def _row(self, r) -> dict:  # noqa: ANN001
        keys = ["id", "label", "plan", "region", "vcpu", "ram", "monthly_cost_cents", "tags", "status", "cpu_avg_7d", "requests_7d", "purpose", "date_created"]
        d = dict(zip(keys, r, strict=False))
        d["tags"] = [t for t in str(d["tags"]).split(",") if t]
        return d

    def list_instances(self, tag: str | None = None) -> list[dict]:
        rows = self._db.execute("SELECT instance_id,label,plan,region,vcpu,ram_mb,monthly_cost_cents,tags,status,cpu_avg_7d,requests_7d,purpose,created_at "
                                "FROM servers ORDER BY id").fetchall()
        out = [self._row(r) for r in rows]
        return [i for i in out if tag in i["tags"]] if tag else out

    def get_instance(self, instance_id: str) -> dict | None:
        return next((i for i in self.list_instances() if i["id"] == instance_id or i["label"] == instance_id), None)

    def _call(self, method: str, path: str, body: dict | None = None) -> None:
        CLOUD.append({"method": method, "path": path[:200], "body": body})

    def delete_instance(self, instance_id: str) -> dict:
        self._db.execute("DELETE FROM servers WHERE instance_id = ? OR label = ?", (str(instance_id), str(instance_id)))
        self._call("DELETE", f"/v2/instances/{instance_id}")
        return {"status": "recorded"}

    def halt_instance(self, instance_id: str) -> dict:
        self._db.execute("UPDATE servers SET status = 'stopped' WHERE instance_id = ? OR label = ?", (str(instance_id), str(instance_id)))
        self._call("POST", f"/v2/instances/{instance_id}/halt")
        return {"status": "recorded"}

    def resize_instance(self, instance_id: str, plan: str) -> dict:
        if plan not in VULTR_PLANS:
            raise ValueError(f"unknown plan {plan!r}; known: {', '.join(VULTR_PLANS)}")
        vcpu, ram, cost = VULTR_PLANS[plan]
        self._db.execute("UPDATE servers SET plan = ?, vcpu = ?, ram_mb = ?, monthly_cost_cents = ? WHERE instance_id = ? OR label = ?",
                         (plan, vcpu, ram, cost, str(instance_id), str(instance_id)))
        self._call("PATCH", f"/v2/instances/{instance_id}", {"plan": plan})
        return {"status": "recorded"}


class Ctx:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.payments = Payments()
        self.email = Email()
        self.http = Http()
        self.vultr = Vultr(db)

    def log(self, *parts) -> None:  # noqa: ANN002
        LOGS.append(" ".join(str(p) for p in parts)[:500])


def phase_run() -> None:
    socket.socket.connect = _tripwire_connect  # type: ignore[assignment]
    socket.getaddrinfo = _tripwire_getaddrinfo  # type: ignore[assignment]
    os.makedirs("/work/out", exist_ok=True)
    started = time.time()
    guards = {"env_keys": sorted(os.environ.keys()), "uid": os.getuid(), "hostname": socket.gethostname(),
              "root_writable": os.access("/", os.W_OK)}
    mem_mb = int(os.environ.get("SD_PLAN_MEM_MB", "160"))
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, hard))  # below the container cap: we survive to report
    db = sqlite3.connect("/work/work.db", isolation_level=None)
    db.execute("PRAGMA foreign_keys = OFF")
    stdout = io.StringIO()
    error = None
    try:
        db.execute("BEGIN")
        ns: dict = {"__name__": "plan"}
        with contextlib.redirect_stdout(stdout):
            exec(compile(open("/work/plan.py").read(), "plan.py", "exec"), ns)  # noqa: S102 - this IS the sandbox
            if "run" not in ns:
                raise RuntimeError("plan.py must define run(ctx)")
            ns["run"](Ctx(db))
        if db.in_transaction:
            db.execute("COMMIT")
    except BaseException as e:  # noqa: BLE001
        msg = "".join(traceback.format_exception_only(type(e), e)).strip()[:2000]
        if isinstance(e, MemoryError):
            msg = f"MemoryError: plan exceeded the sandbox memory ceiling ({mem_mb} MB) and was stopped"
        error = {"message": msg, "traceback": traceback.format_exc()[-3000:]}
        # Keep what it did before crashing so the approver can see it (a crashed plan is never applied).
        with contextlib.suppress(Exception):
            if db.in_transaction:
                db.execute("COMMIT")
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    with contextlib.suppress(Exception):
        db.close()
    intents = {"ok": error is None, "error": error, "stdout": stdout.getvalue()[-4000:], "logs": LOGS[-100:],
               "payments": PAYMENTS[:MAX_INTENTS], "emails": EMAILS[:MAX_INTENTS], "http": HTTP[:MAX_INTENTS], "cloud": CLOUD[:MAX_INTENTS], "blocked": BLOCKED[:50], "guards": guards,
               "duration_ms": int((time.time() - started) * 1000)}
    with open("/work/out/intents.json", "w") as f:
        json.dump(intents, f, default=str)


# =============================================================================================
# PHASE 2: measure (trusted code only)
# =============================================================================================
def snapshot(path: str) -> dict:
    db = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    snap = {}
    for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        cols = [r[1] for r in db.execute(f"PRAGMA table_info({_q(t)})")]
        # Name the columns: `SELECT *` would also return generated columns, which table_info leaves out, and shift values.
        sel = ", ".join(_q(c) for c in cols)
        snap[t] = {"cols": cols, "rows": {row[0]: dict(zip(cols, row[1:], strict=True)) for row in db.execute(f"SELECT rowid, {sel} FROM {_q(t)}")}}
    db.close()
    return snap


def diff(before: dict, after: dict) -> dict:
    out = {}
    for t in sorted(set(before) | set(after)):
        b = before.get(t, {"rows": {}})["rows"]
        a = after.get(t, {"rows": {}})["rows"]
        if t not in after:
            out[t] = {"dropped": True, "created": False, "deleted": [{"rowid": k, "before": v} for k, v in sorted(b.items())], "inserted": [], "updated": []}
            continue
        if t in before and before[t]["cols"] != after[t]["cols"]:
            # ALTER TABLE (add/rename/drop column): never auto-applied, and its column names are never trusted.
            out[t] = {"dropped": False, "created": False, "schema_changed": True, "cols_before": before[t]["cols"],
                      "cols_after": after[t]["cols"], "deleted": [], "inserted": [], "updated": []}
            continue
        deleted = [{"rowid": k, "before": b[k]} for k in sorted(b.keys() - a.keys())]
        inserted = [{"rowid": k, "after": a[k]} for k in sorted(a.keys() - b.keys())]
        updated = []
        for k in sorted(b.keys() & a.keys()):
            if b[k] != a[k]:
                updated.append({"rowid": k, "before": b[k], "after": a[k], "changed": [c for c in a[k] if b[k].get(c) != a[k].get(c)]})
        if deleted or inserted or updated or t not in before:
            out[t] = {"dropped": False, "created": t not in before, "deleted": deleted, "inserted": inserted, "updated": updated}
    return out


def _int(x, lo=-(2**53), hi=2**53):
    try:
        v = int(x)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def validate_intents(raw: dict) -> dict:
    """Phase 1 output is untrusted data: keep only well-formed, bounded records."""
    raw = raw if isinstance(raw, dict) else {}
    pays = []
    for p in (raw.get("payments") or [])[:MAX_INTENTS]:
        if isinstance(p, dict) and _int(p.get("charge_id")) is not None and _int(p.get("amount_cents"), 0) is not None:
            pays.append({"op": "refund", "charge_id": _int(p["charge_id"]), "amount_cents": _int(p["amount_cents"], 0), "reason": str(p.get("reason", ""))[:200]})
    mails = []
    for e in (raw.get("emails") or [])[:MAX_INTENTS]:
        if isinstance(e, dict):
            mails.append({"to": str(e.get("to", ""))[:320], "subject": str(e.get("subject", ""))[:300], "body": str(e.get("body", ""))[:5000],
                          "kind": e.get("kind") if e.get("kind") in ("marketing", "transactional") else None})
    calls = []
    for c in (raw.get("http") or [])[:MAX_INTENTS]:
        if not isinstance(c, dict):
            continue
        method, url = str(c.get("method", "")).upper(), str(c.get("url", ""))
        try:
            body = json.dumps(c.get("json"), default=str)
        except (TypeError, ValueError):
            body = "null"
        hdrs = c.get("headers") if isinstance(c.get("headers"), dict) else {}
        hdrs = {str(k)[:100]: str(v)[:500] for k, v in list(hdrs.items())[:20]
                if str(k).lower() not in SECRET_HEADERS and not _unsafe_header(str(k)) and not _unsafe_header(str(v))}
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")  # the query string is part of what gets delivered
        calls.append({"method": method if method in ("GET", "POST", "PUT", "PATCH", "DELETE") else "INVALID", "url": url[:2000],
                      "host": (parsed.hostname or "").lower(), "scheme": parsed.scheme, "path": path[:2000],
                      "json": json.loads(body) if len(body) <= 65536 else {"_truncated": True}, "body_bytes": len(body), "headers": hdrs,
                      **({"oversized": True} if len(body) > 65536 or len(url) > 2000 else {})})
    cloud = [{"method": str(c.get("method", ""))[:10], "path": str(c.get("path", ""))[:200]}
             for c in (raw.get("cloud") or [])[:MAX_INTENTS] if isinstance(c, dict)]
    err = raw.get("error")
    return {"cloud_calls": cloud, "ok": bool(raw.get("ok")) and err is None, "error": err if isinstance(err, dict) else ({"message": str(err)[:2000]} if err else None),
            "stdout": str(raw.get("stdout", ""))[-4000:], "logs": [str(x)[:500] for x in (raw.get("logs") or [])[:100]],
            "payments": pays, "emails": mails, "http": calls,
            "blocked": [{"kind": str(b.get("kind", ""))[:20], "target": str(b.get("target", ""))[:200]} for b in (raw.get("blocked") or [])[:50] if isinstance(b, dict)],
            "guards": raw.get("guards") if isinstance(raw.get("guards"), dict) else {}, "duration_ms": _int(raw.get("duration_ms"), 0) or 0}


PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}|\{[a-z_]+\}|\[(?:NAME|FIRST_NAME|CUSTOMER)\]|<(?:name|first_name)>|%\(\w+\)s|%s", re.I)
CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PROMO = re.compile(r"\b\d{1,2}\s?% off\b|\bdiscount\b|\bpromo(?:tion)?\b|\bcoupon\b|\bsale\b|\buse (?:the )?code\b|\bspecial offer\b", re.I)


def _unsafe_header(value: str) -> bool:
    """Anything that could split or break an email header line (\r, \n, \v, \x85, \u2028, ... or any control char)."""
    return len(value.splitlines()) > 1 or any(ord(ch) < 32 or ord(ch) == 127 or 0x80 <= ord(ch) <= 0x9F for ch in value)


def _q(ident: str) -> str:
    """Quote an SQL identifier."""
    return '"' + str(ident).replace('"', '""') + '"'


def unsafe_path(path: str) -> bool:
    """Dot segments (also percent-encoded), backslashes or control characters: a path that could climb out of a connector's base."""
    p = urllib.parse.unquote(urllib.parse.unquote(str(path).split("?", 1)[0]))
    return chr(92) in p or any(ord(ch) < 32 or ord(ch) == 127 for ch in p) or any(seg in (".", "..") for seg in p.split("/"))


def audit_http(before: dict, calls: list) -> dict:
    """Personal data leaving through API calls: how many distinct customers' emails / card-like numbers each payload carries."""
    customers = {str(r.get("email", "")).lower() for r in before.get("customers", {}).get("rows", {}).values()} - {""}
    bulk, cards, hosts, oversized, unsafe = [], [], Counter(), [], []
    leaked: set = set()  # across ALL calls: spreading customer data over many small calls doesn't hide it
    for c in calls:
        hosts[c["host"]] += 1
        text = " ".join([json.dumps(c.get("json"), default=str), c.get("path", ""), json.dumps(c.get("headers", {}))])
        found = {x.lower() for x in EMAIL.findall(text)} & customers
        leaked |= found
        if len(found) > 3:
            bulk.append({"url": c["url"][:200], "customers": len(found)})
        if CARD.search(text):
            cards.append({"url": c["url"][:200]})
        if c.get("oversized"):
            oversized.append({"url": c["url"][:200], "bytes": c.get("body_bytes", 0)})
        if unsafe_path(c.get("path", "")):
            unsafe.append({"url": c["url"][:200]})
    if len(leaked) > 3 and not bulk:
        bulk.append({"url": f"{len(calls)} calls combined", "customers": len(leaked)})
    routes = sorted({(c["method"], c["host"], c["scheme"]) for c in calls})
    return {"count": len(calls), "hosts": dict(hosts.most_common(20)),
            "routes": [{"method": m, "host": h, "scheme": sc} for m, h, sc in routes[:200]], "routes_truncated": len(routes) > 200,
            "bulk_personal_data": bulk[:5], "bulk_personal_data_count": len(bulk),
            "card_numbers": cards[:5], "card_number_count": len(cards), "customers_in_payloads": len(leaked),
            "oversized": oversized[:5], "oversized_count": len(oversized), "unsafe_paths": unsafe[:5], "unsafe_path_count": len(unsafe)}


def audit_cloud(before: dict, after: dict) -> dict:
    """What the plan does to the fleet, measured from the servers table before/after (the plan's own call log is not trusted)."""
    b = {r.get("instance_id"): r for r in before.get("servers", {}).get("rows", {}).values()}
    a = {r.get("instance_id"): r for r in after.get("servers", {}).get("rows", {}).values()}
    if not b:
        return {}

    def card(r: dict) -> dict:
        tags = [t for t in str(r.get("tags", "")).split(",") if t]
        return {"id": r.get("instance_id"), "label": r.get("label"), "plan": r.get("plan"), "region": r.get("region"),
                "monthly_cost_cents": int(r.get("monthly_cost_cents") or 0), "tags": tags, "production": "production" in tags,
                "cpu_avg_7d": r.get("cpu_avg_7d"), "requests_7d": r.get("requests_7d"), "purpose": r.get("purpose"), "status": r.get("status")}
    deleted = [card(r) for k, r in b.items() if k not in a]
    stopped = [card(a[k]) for k in b if k in a and b[k].get("status") != "stopped" and a[k].get("status") == "stopped"]
    resized = [{**card(a[k]), "from_plan": b[k].get("plan"), "from_cost_cents": int(b[k].get("monthly_cost_cents") or 0)}
               for k in b if k in a and b[k].get("plan") != a[k].get("plan")]
    before_cost = sum(int(r.get("monthly_cost_cents") or 0) for r in b.values())
    after_cost = sum(int(r.get("monthly_cost_cents") or 0) for r in a.values())  # Vultr bills stopped instances too
    touched = deleted + stopped + [{k: v for k, v in r.items() if k not in ("from_plan", "from_cost_cents")} for r in resized]
    return {"servers_before": len(b), "servers_after": len(a), "deleted": deleted, "stopped": stopped, "resized": resized,
            "monthly_cost_before_cents": before_cost, "monthly_cost_after_cents": after_cost,
            "monthly_savings_cents": before_cost - after_cost,
            "production_touched": [c["label"] for c in touched if c["production"]],
            "fleet": [card(r) for r in b.values()]}


def audit(before: dict, payments: list, emails: list) -> dict:
    """Facts about the intended side effects, checked against the data as it was BEFORE the plan ran."""
    charges = before.get("charges", {}).get("rows", {})
    customers = before.get("customers", {}).get("rows", {})
    by_email = {str(r.get("email", "")).lower(): r for r in customers.values()}
    per_charge = Counter(p["charge_id"] for p in payments)
    over, already, unknown = [], [], []
    for p in payments:
        ch = charges.get(p["charge_id"])
        if ch is None:
            unknown.append(p)
        elif p["amount_cents"] > (ch.get("amount_cents") or 0):
            over.append({**p, "charged_cents": ch.get("amount_cents")})
        elif ch.get("status") == "refunded":
            already.append(p)
    recipients = Counter(e["to"] for e in emails)
    templated, leaks, vip, strangers, opted_out = [], [], [], [], []
    invalid = []
    for e in emails:
        text = e["subject"] + "\n" + e["body"]
        # Exactly one bare address, no header injection; anything else is refused (smtplib would happily send it).
        addrs = email.utils.getaddresses([e["to"]])
        if (_unsafe_header(e["to"]) or _unsafe_header(e["subject"]) or len(addrs) != 1
                or addrs[0][1] != e["to"] or "@" not in addrs[0][1]):
            invalid.append({"to": e["to"][:120], "reason": "not exactly one plain address (or a header line break)"})
            continue
        m = PLACEHOLDER.search(text)
        if m:
            templated.append({"to": e["to"], "match": m.group(0)})
        others = [x for x in EMAIL.findall(e["body"]) if x.lower() != e["to"].lower() and x.lower() in by_email]
        if others or CARD.search(e["body"]):
            leaks.append({"to": e["to"], "reason": "contains another customer's email" if others else "contains a card-like number"})
        c = by_email.get(e["to"].lower())
        if c is None:
            strangers.append(e["to"])
        else:
            if c.get("vip"):
                vip.append({"to": e["to"], "name": c.get("name")})
            marketing = e.get("kind") == "marketing" or PROMO.search(text) is not None   # promo wording counts even if labelled transactional
            if marketing and c.get("marketing_opt_in") == 0:
                opted_out.append({"to": e["to"], "name": c.get("name"), "vip": bool(c.get("vip"))})
    return {
        "refunds": {"over_refunded": over[:5], "over_refunded_count": len(over), "already_refunded": already[:5], "already_refunded_count": len(already),
                    "unknown_charge_count": len(unknown), "duplicate_refund_count": sum(1 for n in per_charge.values() if n > 1)},
        "emails": {"templated": templated[:5], "templated_count": len(templated), "leaks": leaks[:5], "leak_count": len(leaks),
                   "vip": vip[:10], "vip_count": len(vip), "not_a_customer_count": len(strangers),
                   "opted_out_marketing": opted_out[:10], "opted_out_marketing_count": len(opted_out),
                   "invalid": invalid[:5], "invalid_count": len(invalid),
                   "duplicate_recipient_count": sum(1 for n in recipients.values() if n > 1)},
    }


def phase_measure() -> None:
    os.makedirs("/out", exist_ok=True)
    before = snapshot("/in/before.db")
    try:
        intents = validate_intents(json.load(open("/in/intents.json")))
    except (OSError, ValueError):
        intents = validate_intents({"ok": False, "error": {"message": "The plan was killed before it could finish (time or memory cap)."}})
    try:
        after = snapshot("/in/after.db")
    except sqlite3.DatabaseError as e:
        after = before
        intents["ok"] = False
        intents["error"] = {"message": f"The plan corrupted its copy of the database: {e}"}
    changes = diff(before, after)
    tables = {}
    for t, d in changes.items():
        tables[t] = {
            "dropped": d["dropped"], "created": d.get("created", False), "schema_changed": d.get("schema_changed", False),
            "deleted": len(d["deleted"]), "inserted": len(d["inserted"]), "updated": len(d["updated"]),
            "rows_before": len(before.get(t, {"rows": {}})["rows"]), "rows_after": len(after.get(t, {"rows": {}})["rows"]),
            "changed_columns": sorted({c for u in d["updated"] for c in u["changed"]}),
            "samples": {"deleted": d["deleted"][:8], "inserted": d["inserted"][:8], "updated": d["updated"][:8]},
        }
    pays, mails, calls = intents["payments"], intents["emails"], intents["http"]
    consequences = {
        "ok": intents["ok"], "error": intents["error"], "stdout": intents["stdout"], "logs": intents["logs"], "duration_ms": intents["duration_ms"],
        "tables": tables,
        "row_counts": {t: {"before": len(before[t]["rows"]), "after": len(after.get(t, {"rows": {}})["rows"])} for t in before},
        "payments": {"count": len(pays), "total_cents": sum(p["amount_cents"] for p in pays), "samples": pays[:25]},
        "emails": {"count": len(mails), "samples": mails[:25]},
        "blocked": intents["blocked"], "guards": intents["guards"], "audit": {**audit(before, pays, mails), "http": audit_http(before, calls)}, "measured_by": "trusted-phase-2",
        "http": {"count": len(calls), "samples": calls[:25]},
        "cloud": {**audit_cloud(before, after), "calls": intents.get("cloud_calls", [])[:50]},
    }
    with open("/out/consequences.json", "w") as f:
        json.dump(consequences, f, default=str)
    with open("/out/effects.json", "w") as f:
        json.dump({"changes": changes, "payments": pays, "emails": mails, "http": calls}, f, default=str)


if __name__ == "__main__":
    {"run": phase_run, "measure": phase_measure}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
    sys.exit(0)
