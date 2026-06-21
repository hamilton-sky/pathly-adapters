"""Connection management for pathly_orchestrator SQLite database."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path

from .migrations import _run_migrations

_VEC_AVAILABLE: bool = False  # set on first connection
_FTS_AVAILABLE: bool = False  # set on first connection, after migrations
_local = threading.local()  # per-thread connection storage
_init_lock = threading.Lock()  # guards one-time initialization
_init_once_done = False
# Process-wide write serialization. SQLite allows a single writer at a time, and
# every thread holds its OWN connection, so a per-connection lock never serializes
# cross-thread writers — they race on SQLite directly and intermittently hit
# "database is locked" / drop a write under WAL. One global lock fixes that.
# RLock (reentrant) so a write path that nests another write under the lock on the
# same thread can't deadlock.
_global_write_lock = threading.RLock()


def _load_vec(conn: sqlite3.Connection) -> bool:
    """Try to load sqlite_vec into *conn*. Returns True on success."""
    try:
        conn.enable_load_extension(True)
        import sqlite_vec

        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass
        return False


def _make_conn(db_path: str) -> sqlite3.Connection:
    """Open a new SQLite connection with standard PRAGMAs."""
    conn = sqlite3.connect(db_path, check_same_thread=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-4096")  # 4 MB in-process page cache
    if _VEC_AVAILABLE:
        _load_vec(conn)
    return conn


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    from pathly_orchestrator.seed import seed_if_empty as _real_seed

    _real_seed(conn)


def _refresh_catalog(conn: sqlite3.Connection) -> None:
    try:
        from pathly_orchestrator.db.queries.catalog_items import rebuild_catalog

        rebuild_catalog(conn)
    except Exception:
        pass


def _refresh_flows(conn: sqlite3.Connection) -> None:
    try:
        from pathly_orchestrator.db.queries.flow_defs import (
            _refresh_flows as _do_refresh,
        )

        _do_refresh(conn)
    except Exception:
        pass


def _wal_checkpoint_loop(db_path: str) -> None:
    """Run WAL checkpoint every 5 minutes in a background daemon thread."""
    import time

    while True:
        time.sleep(300)
        try:
            conn = sqlite3.connect(db_path, check_same_thread=True)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception:
            pass


def get_db(_deprecated_path=None) -> sqlite3.Connection:
    """Return a per-thread sqlite3.Connection for ~/.pathly/pathly.db.

    The first call (any thread) runs one-time initialization: migrations,
    seed, catalog refresh, flows refresh, and the WAL checkpoint thread.
    Subsequent calls return (or create) the calling thread's own connection.
    """
    global _init_once_done, _VEC_AVAILABLE, _FTS_AVAILABLE

    db_dir = Path(os.environ.get("PATHLY_DB_DIR", str(Path.home() / ".pathly")))
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = os.environ.get("PATHLY_DB_PATH") or str(db_dir / "pathly.db")

    # Create this thread's connection if it doesn't have one yet. Serialize the
    # open+PRAGMA setup under the global write lock: `PRAGMA journal_mode=WAL`
    # briefly needs an exclusive DB lock, so concurrent first-time opens from many
    # threads otherwise race and intermittently raise "database is locked".
    if not hasattr(_local, "conn") or _local.conn is None:
        with _global_write_lock:
            _local.conn = _make_conn(db_path)

    conn = _local.conn

    # One-time initialization -- runs exactly once across all threads.
    if not _init_once_done:
        with _init_lock:
            if not _init_once_done:
                try:
                    # Determine vec availability on this first connection.
                    if _load_vec(conn):
                        _VEC_AVAILABLE = True
                    else:
                        _VEC_AVAILABLE = False
                        logging.warning(
                            "sqlite-vec unavailable - comms board uses recency-only retrieval"
                        )
                    _run_migrations(conn, vec_available=_VEC_AVAILABLE)
                    # Probe for FTS5 table AFTER migrations — comms_fts is created there.
                    try:
                        conn.execute("SELECT * FROM comms_fts LIMIT 0")
                        _FTS_AVAILABLE = True
                    except Exception:
                        _FTS_AVAILABLE = False
                    _seed_if_empty(conn)
                    _refresh_catalog(conn)
                    _refresh_flows(conn)
                    threading.Thread(
                        target=_wal_checkpoint_loop,
                        args=(db_path,),
                        daemon=True,
                        name="pathly-wal-checkpoint",
                    ).start()
                finally:
                    _init_once_done = True

    return conn


def _get_write_lock(conn: sqlite3.Connection) -> "threading.RLock":  # noqa: ARG001
    """Return the process-wide write lock.

    SQLite permits only one writer at a time, and every thread holds its own
    connection — so a per-connection lock never serializes cross-thread writers;
    they race on SQLite directly and intermittently hit "database is locked" or
    drop a write. A single global lock serializes all writers in-process. The
    *conn* argument is kept for call-site compatibility
    (`with _get_write_lock(conn): conn.execute(...); conn.commit()`).
    """
    return _global_write_lock
