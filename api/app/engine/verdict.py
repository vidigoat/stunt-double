"""One decision, with a reason from every layer of the engine.

A rehearsal is judged by six independent layers. Each says pass, warn or fail in one plain sentence, and the decision
follows from them by fixed rules (no AI decides here; the jury is one layer among six):

    measured     did the plan run, and what did a separate sandbox measure?
    proof        is every measured change explained by a statement the plan ran?       (Proof of Effect)
    contract     does it keep the promises written before the plan existed?           (Intent Contracts)
    rules        the business's policy and the rules it learned from earlier catches
    jury         three models from three labs on Vultr Serverless Inference
    approval     who has to sign

    blocked      a deterministic layer failed and no part of the plan can be saved
    cut          a deterministic layer failed, and the engine can prove a subset that passes   (surgical approval)
    review       nothing deterministic failed, but a person must judge (the jury objected, or work is left undone)
    approve      every layer passed
"""
from __future__ import annotations

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"


def _n(x: int, one: str, many: str | None = None) -> str:
    return f"{x:,} {one if x == 1 else (many or one + 's')}"


def _measured(c: dict) -> dict:
    if not c.get("ok"):
        err = c.get("error") or {}
        return {"status": FAIL, "reason": f"The plan crashed in the sandbox: {(err.get('message') if isinstance(err, dict) else err) or 'unknown error'}"[:240]}
    rows = sum(t.get("updated", 0) + t.get("deleted", 0) + t.get("inserted", 0) for t in (c.get("tables") or {}).values())
    pays, mails = (c.get("payments") or {}).get("count", 0), (c.get("emails") or {}).get("count", 0)
    calls = (c.get("http") or {}).get("count", 0)
    parts = [_n(rows, "row change")] + ([_n(pays, "refund")] if pays else []) + ([_n(mails, "email")] if mails else []) + ([_n(calls, "API call")] if calls else [])
    return {"status": PASS, "reason": f"Ran sealed; a second sandbox measured {', '.join(parts)}."}


def _proof(c: dict) -> dict:
    p = c.get("provenance") or {}
    s = p.get("status")
    if s == "proven":
        return {"status": PASS, "reason": f"Replaying its {_n(p.get('statements') or 0, 'statement')} reproduces all {_n(p.get('rows_measured') or 0, 'change')}."}
    if s == "derived":
        return {"status": PASS, "reason": "Cut by the engine from a proven rehearsal; no plan code ran again."}
    if s == "unexplained":
        return {"status": FAIL, "reason": f"{_n(p.get('unexplained') or 0, 'change')} happened by no statement on record."}
    if not c.get("ok"):
        return {"status": SKIP, "reason": "Nothing to prove: the plan crashed."}
    return {"status": WARN, "reason": f"The record couldn't be replayed ({p.get('reason') or 'no record'})."}


def _contract(c: dict, contract: dict | None) -> dict:
    out = _contract_layer(c, contract)
    struck = (contract or {}).get("struck") or []
    if struck:
        out["reason"] += f" {len(struck)} struck by {', '.join(sorted({x['by'] for x in struck}))}."
    return out


def _contract_layer(c: dict, contract: dict | None) -> dict:
    res = c.get("contract") or {}
    ps = res.get("promises") or []
    if not ps:
        why = (contract or {}).get("reason") or ("still being written" if (contract or {}).get("status") == "writing" else "none was written for this run")
        return {"status": SKIP, "reason": f"No contract: {why}."[:240]}
    broken = [p for p in ps if p["status"] == "broken"]
    unmet = [p for p in ps if p["status"] == "unmet"]
    unknown = [p for p in ps if p["status"] not in ("kept", "met", "broken", "unmet")]
    if broken:
        p = broken[0]
        return {"status": FAIL, "reason": f"Breaks “{p['text']}” ({_n(p['after'], 'row')}).", "promises": len(ps), "broken": len(broken)}
    if unmet:
        p = unmet[0]
        return {"status": WARN, "reason": f"Leaves {p['after']:,} of {p['today']:,} undone: “{p['text']}”.", "promises": len(ps), "unmet": len(unmet)}
    if unknown:
        return {"status": WARN, "reason": f"Couldn't check {_n(len(unknown), 'promise')} of {len(ps)}: “{unknown[0]['text']}”.", "promises": len(ps)}
    work = [p["today"] for p in ps if p["kind"] == "obligation"]
    keeps = "Keeps its one promise" if len(ps) == 1 else f"Keeps all {len(ps)} promises"
    done = "" if not work else f" and finishes the work ({work[0]:,} of {work[0]:,})." if len(set(work)) == 1 else f" and finishes all {len(work)} pieces of work."
    return {"status": PASS, "reason": keeps + (done or "."), "promises": len(ps)}


def _rules(flags: list[dict]) -> dict:
    own = [f for f in flags if f.get("rule") not in ("contract", "provenance")]
    crit = [f for f in own if f.get("severity") == "critical"]
    high = [f for f in own if f.get("severity") == "high"]
    if crit:
        return {"status": FAIL, "reason": crit[0]["title"] + (f" (+{len(crit) - 1} more)" if len(crit) > 1 else "")}
    if high:
        return {"status": WARN, "reason": high[0]["title"] + (f" (+{len(high) - 1} more)" if len(high) > 1 else "")}
    return {"status": PASS, "reason": "Every policy check and learned rule passed." if not own else f"Passed, with {_n(len(own), 'note')}."}


def _jury(v: dict | None) -> dict:
    if not v:
        return {"status": SKIP, "reason": "No AI check ran for this rehearsal."}
    if v.get("source") == "learned_rule":
        return {"status": SKIP, "reason": "Not needed: a rule this business learned from an earlier catch decided, with no AI."}
    j = v.get("jury") or {}
    who = f" ({j['agree']} of {j['cast']} models agree)" if j.get("cast") else ""
    st = {"looks_right": PASS, "concerns": WARN, "dangerous": FAIL}.get(v.get("verdict"), WARN)
    return {"status": st, "reason": (v.get("headline") or "Checked") + who}


def decide(run: dict) -> dict | None:
    """The decision for the run's latest rehearsal, or None while there is nothing to decide."""
    if not run.get("attempts") or run.get("status") in ("queued", "planning", "rehearsing", "verifying"):
        return None
    att = run["attempts"][-1]
    c = att.get("consequences") or {}
    need = att.get("approvals_required") or 1
    layers = [
        {"key": "measured", "title": "Measured", **_measured(c)},
        {"key": "proof", "title": "Proof of effect", **_proof(c)},
        {"key": "contract", "title": "Intent contract", **_contract(c, run.get("contract"))},
        {"key": "rules", "title": "Policy and rules", **_rules(att.get("flags") or [])},
        {"key": "jury", "title": "AI jury", **_jury(run.get("verdict"))},
        {"key": "approval", "title": "Sign-off", "status": PASS,
         "reason": "Two different people must approve: " + ", ".join(att.get("approval_reasons") or []) if need > 1 else "One person approves."},
    ]
    # deterministic layers lock approval; the jury's objection alone asks a person to decide, with a written reason
    failed = [x for x in layers if x["status"] == FAIL and x["key"] != "jury"]
    warned = [x for x in layers if x["status"] == WARN or (x["status"] == FAIL and x["key"] == "jury")]
    offer = (run.get("surgical") or {}).get("offer") if not att.get("surgical_of") else None
    jury_failed = any(x["key"] == "jury" and x["status"] == FAIL for x in layers)
    if offer and (failed or jury_failed):
        decision = "cut"
        headline = f"Approve just the {offer['units_kept']:,} of {offer['units_total']:,} changes that pass the check"
    elif failed:
        decision, headline = "blocked", f"Blocked: {failed[0]['title'].lower()} failed"
    elif jury_failed:
        decision, headline = "review", "The AI jury objected: approving needs a written reason"
    elif warned:
        decision, headline = "review", f"A person should decide: {', '.join(x['title'].lower() for x in warned)}"
    elif all(x["status"] == SKIP for x in layers if x["key"] in ("contract", "jury")):
        decision, headline = "review", "The rules pass, but nothing checked the meaning: a person should read it"
    else:
        decision, headline = "approve", "Every layer passed"
    return {"decision": decision, "headline": headline, "attempt": att["n"], "layers": layers,
            "failed": [x["key"] for x in failed], "warned": [x["key"] for x in warned]}
