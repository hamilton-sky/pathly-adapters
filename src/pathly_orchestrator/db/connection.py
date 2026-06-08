"""Connection management for pathly_orchestrator SQLite database."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .migrations import _run_migrations

_conn_cache: dict[str, sqlite3.Connection] = {}
_cache_lock = threading.Lock()
# Per-connection write lock keyed by id(conn).
# Python's sqlite3 module is not thread-safe for concurrent writes on a shared
# connection even with check_same_thread=False; this serialises them.
_write_locks: dict[int, threading.Lock] = {}


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    from pathly_orchestrator.seed import seed_if_empty as _real_seed
    _real_seed(conn)


def _refresh_catalog(conn: sqlite3.Connection) -> None:
    """Rebuild the catalog_items index on every server start. Never raises."""
    try:
        from pathly_orchestrator.db.queries.catalog_items import rebuild_catalog
        rebuild_catalog(conn)
    except Exception:
        pass  # never block server start due to catalog failures


def get_db(_deprecated_path=None) -> sqlite3.Connection:
    """Return a cached sqlite3.Connection for ~/.pathly/pathly.db.

    _deprecated_path is accepted for backward compat but ignored.
    Always opens ~/.pathly/pathly.db (resolved at call time so tests can patch Path.home()).
    """
    db_dir = Path.home() / ".pathly"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / "pathly.db")

    with _cache_lock:
        if db_path in _conn_cache:
            return _conn_cache[db_path]
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _run_migrations(conn)
        _conn_cache[db_path] = conn
        conn_id: int = id(conn)
        _write_locks[conn_id] = threading.Lock()

    _seed_if_empty(conn)
    _refresh_catalog(conn)
    return conn


def _get_write_lock(conn: sqlite3.Connection) -> threading.Lock:
    """Return the write lock for *conn*, keyed by connection identity."""
    conn_id: int = id(conn)
    with _cache_lock:
        if conn_id not in _write_locks:
            _write_locks[conn_id] = threading.Lock()
        return _write_locks[conn_id]
