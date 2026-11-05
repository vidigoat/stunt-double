"""The signed record of a decision.

Every step of a run becomes one entry in a hash chain: the request, the contract written before the plan, each
rehearsal (the plan itself, the fingerprint of its measured effects, its Effect Graph, its Proof of Effect, how it
did against the contract), the AI jury's verdict, the engine's decision, the human sign-off, and what was applied.

    entry.hash = sha256(canonical JSON of {seq, kind, body, prev})        prev = the previous entry's hash

The last hash (the head) is signed with this server's Ed25519 key. Change one byte anywhere (a refund amount, a
promise, an approver's name) and the chain no longer verifies; drop or reorder an entry and it breaks too.
Anyone can check a bundle with only the public key: verify() below, the SDK, or POST /api/evidence/verify.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

GENESIS = "0" * 64
_LOCK = threading.Lock()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def entry_hash(seq: int, kind: str, body, prev: str) -> str:
    return hashlib.sha256(canonical({"seq": seq, "kind": kind, "body": body, "prev": prev})).hexdigest()


def chain(steps: list[tuple[str, object]]) -> list[dict]:
    out, prev = [], GENESIS
    for seq, (kind, body) in enumerate(steps):
        body = json.loads(canonical(body))      # exactly what a reader will parse back (int keys become strings, ...)
        h = entry_hash(seq, kind, body, prev)
        out.append({"seq": seq, "kind": kind, "body": body, "prev": prev, "hash": h})
        prev = h
    return out


def _key(data_dir: Path) -> Ed25519PrivateKey:
    path = data_dir / "evidence-key.pem"
    with _LOCK:
        if path.exists():
            return serialization.load_pem_private_key(path.read_bytes(), password=None)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        return key


def public_key(data_dir: Path) -> dict:
    raw = _key(data_dir).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"alg": "Ed25519", "public_key": base64.b64encode(raw).decode(), "key_id": hashlib.sha256(raw).hexdigest()[:16]}


def seal(steps: list[tuple[str, object]], data_dir: Path) -> dict:
    entries = chain(steps)
    head = entries[-1]["hash"] if entries else GENESIS
    pub = public_key(data_dir)
    sig = _key(data_dir).sign(bytes.fromhex(head))
    return {"entries": entries, "head": head, "signature": {**pub, "signature": base64.b64encode(sig).decode(), "signed": "head"}}


def verify(bundle: dict, trusted_public_key: str | None = None) -> dict:
    """Check a sealed record end to end. Returns {ok, entries, head, reason}. Pass the public key you trust
    (from GET /api/evidence/key) to also check who signed it; without it, the key in the bundle is used."""
    sealed = bundle.get("chain") if "chain" in bundle else bundle
    entries = sealed.get("entries") or []
    prev = GENESIS
    for i, e in enumerate(entries):
        if e.get("seq") != i or e.get("prev") != prev:
            return {"ok": False, "entries": len(entries), "reason": f"entry {i} is out of order or detached from the one before it"}
        if entry_hash(i, e.get("kind"), e.get("body"), prev) != e.get("hash"):
            return {"ok": False, "entries": len(entries), "reason": f"entry {i} ({e.get('kind')}) was changed after it was sealed"}
        prev = e["hash"]
    if prev != sealed.get("head"):
        return {"ok": False, "entries": len(entries), "reason": "the head doesn't match the last entry (entries were added or removed)"}
    s = sealed.get("signature") or {}
    key_b64 = trusted_public_key or s.get("public_key") or ""
    if trusted_public_key and s.get("public_key") and s["public_key"] != trusted_public_key:
        return {"ok": False, "entries": len(entries), "reason": "signed by a different key than the one you trust"}
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64)).verify(base64.b64decode(s.get("signature", "")), bytes.fromhex(prev))
    except (InvalidSignature, ValueError, TypeError):
        return {"ok": False, "entries": len(entries), "reason": "the signature doesn't match"}
    return {"ok": True, "entries": len(entries), "head": prev, "key_id": s.get("key_id"), "reason": None}
