"""Rollback: the exact inverse of an applied run's data changes, rehearsed and approved like any other change.

Updated rows go back to their approved "before" values, inserted rows are deleted, deleted rows are restored. The
drift check then guarantees we only undo rows that still look exactly like what was applied. Refunds, emails and API
calls already left the building, so they are listed as irreversible rather than pretended away.
"""
import hashlib
import json
from pathlib import Path


def inverse(effects: dict) -> dict:
    changes = {}
    for table, d in effects.get("changes", {}).items():
        changes[table] = {
            "dropped": False, "created": False,
            "updated": [{"rowid": u["rowid"], "before": u["after"], "after": u["before"], "changed": u["changed"]} for u in d.get("updated", [])],
            "deleted": [{"rowid": i["rowid"], "before": i["after"]} for i in d.get("inserted", [])],
            # A deleted cloud server can't be brought back: its row is not re-created (it's listed as irreversible).
            "inserted": [] if table == "servers" else [{"rowid": x["rowid"], "after": x["before"]} for x in d.get("deleted", [])],
        }
    return {"changes": changes, "payments": [], "emails": [], "http": []}


def consequences(inv: dict, source: dict, rows_now: dict[str, int], rid: str) -> dict:
    """The approver-facing summary of a rollback, in the same shape a sandbox rehearsal produces."""
    tables = {}
    for t, d in inv["changes"].items():
        n = rows_now.get(t, 0)
        tables[t] = {"dropped": False, "created": False, "schema_changed": False, "deleted": len(d["deleted"]), "inserted": len(d["inserted"]),
                     "updated": len(d["updated"]), "rows_before": n, "rows_after": n - len(d["deleted"]) + len(d["inserted"]),
                     "changed_columns": sorted({c for u in d["updated"] for c in u["changed"]}),
                     "samples": {"deleted": d["deleted"][:8], "inserted": d["inserted"][:8], "updated": d["updated"][:8]}}
    return {
        "ok": True, "error": None, "stdout": "", "logs": [], "duration_ms": 0, "tables": tables,
        "row_counts": {t: {"before": v["rows_before"], "after": v["rows_after"]} for t, v in tables.items()},
        "payments": {"count": 0, "total_cents": 0, "samples": []}, "emails": {"count": 0, "samples": []}, "http": {"count": 0, "samples": []},
        "blocked": [], "guards": {}, "audit": {},
        "irreversible": {"refunds": len(source.get("payments", [])), "refund_total_cents": sum(p["amount_cents"] for p in source.get("payments", [])),
                         "emails": len(source.get("emails", [])), "http": len(source.get("http", [])),
                         "servers_deleted": len(source.get("changes", {}).get("servers", {}).get("deleted", []))},
        "measured_by": "inverse-of-approved-effects",
        "sandbox": {"id": rid, "runtime": "none (derived)", "network": "none", "memory": "-", "timeout_s": 0, "read_only_root": True,
                    "exit_code": 0, "killed": None, "run_ms": 0, "wall_ms": 0, "destroyed": True},
    }


def build(source_effects_path: str, out_dir: Path, rid: str, rows_now: dict[str, int]) -> tuple[dict, str, str]:
    source = json.loads(Path(source_effects_path).read_text())
    inv = inverse(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(inv, default=str).encode()
    (out_dir / "effects.json").write_bytes(body)
    return consequences(inv, source, rows_now, rid), str(out_dir / "effects.json"), hashlib.sha256(body).hexdigest()
