"""Approval policy: rules every rehearsal is checked against. 'block' rules lock the Approve button."""
import json

from . import config

PATH = config.DATA_DIR / "policy.json"

DEFAULTS: dict = {
    "max_refund_total_usd": 10000,        # warn above this
    "max_emails_per_run": 500,            # warn above this
    "max_delete_pct": 5,                  # block deleting more than this % of any table
    "protected_tables": ["customers"],    # block ANY delete in these tables
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


def save(update: dict) -> dict:
    merged = {**load(), **validate(update)}
    PATH.write_text(json.dumps(merged, indent=2))
    return merged


def reset() -> dict:
    PATH.unlink(missing_ok=True)
    return load()
