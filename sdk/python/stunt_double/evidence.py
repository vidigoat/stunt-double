"""Verify a Stunt Double evidence record offline, with nothing but the server's public key.

    from stunt_double.evidence import verify_evidence
    verify_evidence(json.load(open("stunt-double-evidence-run_x.json")), public_key="…")   # {"ok": True, ...}

Every entry is re-hashed and linked to the one before it, and the head is checked against the Ed25519 signature.
Needs the `cryptography` package for the signature (pip install "stunt-double[verify]").
"""
from __future__ import annotations

import base64
import hashlib
import json

GENESIS = "0" * 64


def _hash(seq: int, kind, body, prev: str) -> str:
    raw = json.dumps({"seq": seq, "kind": kind, "body": body, "prev": prev}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_evidence(bundle: dict, public_key: str | None = None) -> dict:
    """Returns {"ok", "entries", "head", "reason"}. Pass the public key you trust (GET /api/evidence/key) to also
    prove which server signed it."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    sealed = bundle.get("chain", bundle)
    entries = sealed.get("entries") or []
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("seq") != i or e.get("prev") != prev:
            return {"ok": False, "entries": len(entries), "reason": f"entry {i} is out of order or detached from the one before it"}
        if _hash(i, e.get("kind"), e.get("body"), prev) != e.get("hash"):
            return {"ok": False, "entries": len(entries), "reason": f"entry {i} ({e.get('kind')}) was changed after it was sealed"}
        prev = e["hash"]
    if prev != sealed.get("head"):
        return {"ok": False, "entries": len(entries), "reason": "the head doesn't match the last entry (entries were added or removed)"}
    sig = sealed.get("signature") or {}
    if public_key and sig.get("public_key") and sig["public_key"] != public_key:
        return {"ok": False, "entries": len(entries), "reason": "signed by a different key than the one you trust"}
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key or sig.get("public_key", ""))).verify(
            base64.b64decode(sig.get("signature", "")), bytes.fromhex(prev))
    except (InvalidSignature, ValueError, TypeError):
        return {"ok": False, "entries": len(entries), "reason": "the signature doesn't match"}
    return {"ok": True, "entries": len(entries), "head": prev, "key_id": sig.get("key_id"), "reason": None}
