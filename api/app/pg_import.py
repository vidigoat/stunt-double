"""Build a double of a real PostgreSQL database: connect once, read-only, copy the tables of one schema into a SQLite
double, and forget the connection string.

The connection string is never stored, logged, put in a run or passed to a sandbox. Private, loopback and link-local
addresses are refused (the server must not be pointed at internal services). The way back to the real database is the
drift-guarded SQL export of an approved rehearsal, run through your own pipeline, so this server never needs write access.
"""
from __future__ import annotations

import datetime as dt
import decimal
import ipaddress
import json
import socket
import sqlite3
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

from . import config

MAX_TABLES = 40
MAX_ROWS_PER_TABLE = 50_000
MAX_TOTAL_ROWS = 200_000


class PgImportError(Exception):
    pass


def _check_host(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("postgres", "postgresql") or not u.hostname:
        raise PgImportError("Use a postgresql://user:password@host:5432/database connection string")
    if config.PG_ALLOW_PRIVATE:
        return
    try:
        addrs = {a[4][0] for a in socket.getaddrinfo(u.hostname, u.port or 5432, proto=socket.IPPROTO_TCP)}
    except socket.gaierror:
        raise PgImportError("That database host doesn't resolve") from None
    for a in addrs:
        ip = ipaddress.ip_address(a)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise PgImportError("That host is a private or internal address; use a publicly reachable database")


SQLITE_TYPE = {"integer": "INTEGER", "bigint": "INTEGER", "smallint": "INTEGER", "boolean": "INTEGER", "real": "REAL",
               "double precision": "REAL", "numeric": "NUMERIC", "bytea": "BLOB"}


def _val(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat(sep=" ") if isinstance(v, dt.datetime) else v.isoformat()
    if isinstance(v, (uuid.UUID, dt.timedelta, ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return str(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    if isinstance(v, memoryview):
        return bytes(v)
    return v


def import_db(url: str, schema: str = "public") -> tuple[bytes, dict]:
    """Returns (SQLite bytes, meta) where meta = {"tables": n, "rows": n, "pks": {...}, "types": {...}, "server": "PostgreSQL 16"}."""
    import psycopg  # imported lazily: only this feature needs it

    _check_host(url)
    try:
        con = psycopg.connect(url, connect_timeout=10, options="-c default_transaction_read_only=on -c statement_timeout=15000")
    except psycopg.Error as e:
        raise PgImportError(f"Couldn't connect ({type(e).__name__}). Check the host, credentials and that it accepts outside connections.") from None
    meta: dict = {"pks": {}, "types": {}, "rows": 0}
    try:
        with con, tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pg.db"
            out = sqlite3.connect(path)
            cur = con.cursor()
            meta["server"] = "PostgreSQL " + str(con.info.server_version // 10000)
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name", (schema,))
            tables = [r[0] for r in cur.fetchall()]
            if not tables:
                raise PgImportError(f"No tables in schema '{schema}'")
            if len(tables) > MAX_TABLES:
                raise PgImportError(f"Up to {MAX_TABLES} tables in the public demo")
            for t in tables:
                cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position", (schema, t))
                cols = cur.fetchall()
                cur.execute("""SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                               WHERE i.indrelid = (quote_ident(%s) || '.' || quote_ident(%s))::regclass AND i.indisprimary""", (schema, t))
                pk = [r[0] for r in cur.fetchall()]
                meta["pks"][t], meta["types"][t] = pk, {c: ty for c, ty in cols}
                q = lambda n: '"' + n.replace('"', '""') + '"'  # noqa: E731
                coldefs = [f"{q(c)} {SQLITE_TYPE.get(ty, 'TEXT')}" for c, ty in cols]
                if pk:
                    coldefs.append(f"PRIMARY KEY ({', '.join(q(c) for c in pk)})")
                out.execute(f"CREATE TABLE {q(t)} ({', '.join(coldefs)})")
                cur.execute(f"SELECT {', '.join(q(c) for c, _ in cols)} FROM {q(schema)}.{q(t)} LIMIT %s", (MAX_ROWS_PER_TABLE + 1,))
                rows = cur.fetchall()
                if len(rows) > MAX_ROWS_PER_TABLE:
                    raise PgImportError(f"Table {t} has more than {MAX_ROWS_PER_TABLE:,} rows (the public demo's limit)")
                meta["rows"] += len(rows)
                if meta["rows"] > MAX_TOTAL_ROWS:
                    raise PgImportError(f"More than {MAX_TOTAL_ROWS:,} rows in total (the public demo's limit)")
                out.executemany(f"INSERT INTO {q(t)} VALUES ({', '.join('?' for _ in cols)})", [tuple(_val(v) for v in r) for r in rows])
            out.commit()
            out.close()
            meta["tables"] = len(tables)
            return path.read_bytes(), meta
    except psycopg.Error as e:
        raise PgImportError(f"The database refused a read ({type(e).__name__})") from None
    finally:
        con.close()
