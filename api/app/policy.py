"""Approval policy: rules every rehearsal is checked against. 'block' rules lock the Approve button."""
import json

from . import config

PATH = config.DATA_DIR / "policy.json"

DEFAULTS: dict = {
    "max_refund_total_usd": 10000,        # warn above this
    "max_emails_per_run": 500,            # warn above this
    "max_http_per_run": 200,              # warn above this many API calls
    "two_person_over_usd": 10000,         # payouts above this need two different approvers
    "two_person_over_rows": 1000,         # changing more rows than this needs two different approvers
    "approval_expires_hours": 24,         # a rehearsal older than this can't be approved: the world moved on, rehearse again
    "two_person_for_rollbacks": True,     # undoing an applied run needs two different approvers
    "notify_connector": "slack",          # post "approval needed" to this connector ("" = off)
    "max_delete_pct": 5,                  # block deleting more than this % of any table
    "protected_tables": ["customers"],    # block ANY delete in these tables
    "max_update_pct_protected": 20,       # block rewriting more than this % of a protected table
    "block_schema_changes": True,         # block DROP/CREATE TABLE
    "block_network_attempts": True,       # block plans that tried to reach the internet
    "block_over_refunds": True,           # block refunds larger than the original charge, or of unknown/already-refunded charges
    "block_broken_templates": True,       # block emails with unfilled placeholders like {{name}}
    "block_data_leaks": True,             # block emails containing another customer's email or card-like numbers
    "warn_vip_emails": True,              # warn when VIP customers would be emailed
    "block_marketing_to_opted_out": True, # block marketing emails to customers who unsubscribed
    # Business glossary: how THIS company defines its terms. Only Stunt Double's verifier reads it.
    "glossary": [
        {"term": "double-charged", "definition": "A customer was double-charged when two successful charges exist for the SAME order_id. "
                                                 "Two separate orders for the same item on the same day are NOT a double charge."},
        {"term": "refund for a double charge", "definition": "Refund only the extra charge(s) of that order, never the first one, and only charges with status 'succeeded'."},
        {"term": "VIP", "definition": "customers.vip = 1."},
        {"term": "marketing email", "definition": "Any email with a promotion, discount or code. Customers with marketing_opt_in = 0 must never receive one. "
                                                  "Refund and order notices are transactional and always allowed."},
    ],
}

SCHEMA = {k: type(v) for k, v in DEFAULTS.items()}


def approvals_required(consequences: dict, mode: str, pol: dict | None = None) -> tuple[int, list[str]]:
    """How many different people must approve, and why."""
    p = pol or load()
    reasons = []
    money = consequences.get("payments", {}).get("total_cents", 0)
    rows = sum(t.get("deleted", 0) + t.get("updated", 0) + t.get("inserted", 0) for t in consequences.get("tables", {}).values())
    if money > p["two_person_over_usd"] * 100:
        reasons.append(f"payout over ${p['two_person_over_usd']:,}")
    if rows > p["two_person_over_rows"]:
        reasons.append(f"more than {p['two_person_over_rows']:,} rows change")
    if mode == "rollback" and p["two_person_for_rollbacks"]:
        reasons.append("it undoes an applied run")
    return (2 if reasons else 1), reasons


def load() -> dict:
    try:
        saved = json.loads(PATH.read_text())
    except (OSError, ValueError):
        saved = {}
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def validate(update: dict) -> dict:
    clean = {}
    for k, v in update.items():
        if k not in SCHEMA:
            raise ValueError(f"unknown policy '{k}'")
        want = SCHEMA[k]
        if want is bool and not isinstance(v, bool):
            raise ValueError(f"'{k}' must be true/false")
        if want is int:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise ValueError(f"'{k}' must be a non-negative number")
            v = int(v)
        if want is str:
            from . import connectors
            if not isinstance(v, str) or (v and v not in connectors.registry()):
                raise ValueError(f"'{k}' must be empty or one of: {', '.join(connectors.registry())}")
        if k == "glossary":
            if not isinstance(v, list) or len(v) > 50 or not all(
                    isinstance(x, dict) and isinstance(x.get("term"), str) and isinstance(x.get("definition"), str)
                    and 0 < len(x["term"]) <= 80 and 0 < len(x["definition"]) <= 600 for x in v):
                raise ValueError("'glossary' must be up to 50 {term, definition} entries (term <= 80, definition <= 600 chars)")
            v = [{"term": x["term"].strip(), "definition": x["definition"].strip()} for x in v]
        elif want is list and (not isinstance(v, list) or not all(isinstance(x, str) and x.isidentifier() for x in v)):
            raise ValueError(f"'{k}' must be a list of table names")
        clean[k] = v
    return clean


HISTORY = config.DATA_DIR / "policy-history.jsonl"


def save(update: dict, editor: str = "") -> dict:
    before = load()
    merged = {**before, **validate(update)}
    PATH.write_text(json.dumps(merged, indent=2))
    changes = {k: [before.get(k), v] for k, v in merged.items() if before.get(k) != v}
    if changes:  # every rule change is on the record: who, when, old -> new
        import time
        with open(HISTORY, "a") as f:
            f.write(json.dumps({"at": time.time(), "by": " ".join(editor.split())[:80] or "Unnamed editor", "changes": changes}, default=str) + "\n")
    return merged


def history(limit: int = 50) -> list[dict]:
    try:
        lines = HISTORY.read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines[-limit:]):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def reset() -> dict:
    PATH.unlink(missing_ok=True)
    HISTORY.unlink(missing_ok=True)
    return load()
