"""Workspaces: rehearse against the demo business or against a database you upload (SQLite, up to 20 MB).

Every run belongs to a workspace. The engine reads the workspace's database through `db_path()`, which defaults to
the workspace bound to the current thread (`use()`), so the sandbox, the agent's read-only queries, apply and rollback
all follow the run's workspace without threading a parameter through every call.
"""
import contextvars
import json
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path

from . import config

DEMO = "demo"
MAX_BYTES = 20 * 1024 * 1024
MAX_WORKSPACES = 25
DIR = config.DATA_DIR / "workspaces"
REGISTRY = DIR / "registry.json"
_current: contextvars.ContextVar[str] = contextvars.ContextVar("workspace", default=DEMO)


def _load() -> dict:
    try:
        return json.loads(REGISTRY.read_text())
    except (OSError, ValueError):
        return {}


def _save(reg: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2))


def all_workspaces() -> list[dict]:
    demo = {"id": DEMO, "name": "Bean There Coffee Co.", "kind": "demo", "description": "Demo business with three traps"}
    return [demo, *sorted(_load().values(), key=lambda w: w["created_at"])]


def exists(ws: str) -> bool:
    return ws == DEMO or ws in _load()


def db_path(ws: str | None = None) -> Path:
    ws = ws or _current.get()
    if ws == DEMO:
        return config.PROD_DB
    if ws not in _load():
        raise KeyError(f"unknown workspace {ws!r}")
    return DIR / f"{ws}.db"


def use(ws: str) -> contextvars.Token:
    return _current.set(ws)


def name(ws: str) -> str:
    return next((w["name"] for w in all_workspaces() if w["id"] == ws), ws)


def describe(ws: str) -> dict:
    db = sqlite3.connect(f"file:{db_path(ws)}?mode=ro", uri=True)
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts = {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}  # noqa: S608 - names from sqlite_master
    db.close()
    return {"id": ws, "name": name(ws), "tables": counts}


def _validate(path: Path) -> dict:
    with open(path, "rb") as f:
        if f.read(16) != b"SQLite format 3\x00":
            raise ValueError("That isn't a SQLite database file")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("The database failed SQLite's integrity check")
        rows = db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        if not rows:
            raise ValueError("The database has no tables")
        for t, sql in rows:
            if (sql or "").upper().startswith("CREATE VIRTUAL"):
                raise ValueError(f"Virtual table {t!r} isn't supported yet")
            try:
                db.execute(f'SELECT rowid FROM "{t}" LIMIT 1')  # noqa: S608
            except sqlite3.OperationalError as e:
                raise ValueError(f"Table {t!r} has no rowid (WITHOUT ROWID tables aren't supported yet)") from e
        return {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t, _ in rows}  # noqa: S608
    finally:
        db.close()


def create(display_name: str, data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError("Databases up to 20 MB, please")
    reg = _load()
    if len(reg) >= MAX_WORKSPACES:
        raise ValueError("This demo server has reached its workspace limit")
    DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=DIR, suffix=".upload", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        tables = _validate(tmp_path)
    except (ValueError, sqlite3.DatabaseError) as e:
        tmp_path.unlink(missing_ok=True)
        raise ValueError(str(e) if isinstance(e, ValueError) else "That file isn't a readable SQLite database") from e
    ws = "ws-" + uuid.uuid4().hex[:8]
    tmp_path.replace(DIR / f"{ws}.db")
    entry = {"id": ws, "name": (display_name.strip() or "My database")[:60], "kind": "upload", "created_at": time.time(),
             "tables": len(tables), "rows": sum(tables.values()), "description": f"{len(tables)} tables, {sum(tables.values()):,} rows"}
    reg[ws] = entry
    _save(reg)
    return entry
