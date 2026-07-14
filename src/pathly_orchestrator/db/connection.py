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
# db paths whose schema/seed have been prepared. Keyed by PATH, not by a process-global
# flag, so a connection opened against an un-prepared db is always brought up exactly once
# (and never repeats the work). In production this holds a single entry; under test isolation
# each per-test db gets one entry. This is what makes preparation correct AND contention-free
# when the db path is swapped per test — see get_db().
_prepared_paths: set[str] = set()
# Process-wide write serialization. SQLite allows a single writer at a time, and
# every thread holds its OWN connection, so a per-connection lock never serializes
# cross-thread writers — they race on SQLite directly and intermittently hit
# "database is locked" / drop a write under WAL. One global lock fixes that.
# RLock (reentrant) so a write path that nests another write under the lock on the
# same thread can't deadlock.
_global_write_lock = threading.RLock()


class _WriteGuard:
    """Context manager wrapping the process-wide write lock with commit-safety.

    Acquires `_global_write_lock` on enter; on exit, if the body raised, it ROLLS
    BACK the connection before releasing the lock. This is the critical safety net:
    without it, any write that raises *after* sqlite3's implicit BEGIN but *before*
    `conn.commit()` — a transient "database is locked", a constraint error, an
    exception between two statements — leaves the connection in an OPEN transaction.
    That connection then holds SQLite's single write slot indefinitely, so every
    later writer (any thread/connection) fails with "database is locked" forever.
    One transient error would otherwise cascade into a permanent lock.

    Drop-in replacement for the previous bare-RLock return value: every existing
    `with _get_write_lock(conn): conn.execute(...); conn.commit()` site now rolls
    back on error with no change to the call site.
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __enter__(self) -> sqlite3.Connection:
        _global_write_lock.acquire()
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        # Returns None (not False) so the original exception is never suppressed —
        # mypy's [exit-return] check rejects `-> bool` here since a falsy literal is
        # all this returns. None is falsy, so runtime behaviour is unchanged.
        try:
            if exc_type is not None:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
        finally:
            _global_write_lock.release()


def _load_vec(conn: sqlite3.Connection) -> bool:
    """Load sqlite_vec into *conn* and confirm it works. Returns True on success.

    Retries a few times: on Windows the first extension load in a fresh process/thread
    intermittently fails (native DLL init race) while an immediate retry succeeds. Because
    a permanent ``_VEC_AVAILABLE=False`` latch SILENTLY disables every embedding write and
    all semantic search (store_embedding/search_by_embedding no-op / fall back to recency),
    the probe must be robust, not one-shot. We also run ``vec_version()`` to confirm the
    extension actually registered — ``load()`` returning without raising is not sufficient.
    """
    try:
        import sqlite_vec
    except Exception:
        return False
    last_exc: Exception | None = None
    for _ in range(3):
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            conn.execute("SELECT vec_version()").fetchone()  # confirm it registered
            return True
        except Exception as exc:
            last_exc = exc
            try:
                conn.enable_load_extension(False)
            except Exception:
                pass
    logging.debug("sqlite-vec load failed after retries: %r", last_exc)
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
    """Run WAL checkpoint every 5 minutes in a background daemon thread.

    Holds `_global_write_lock` for the checkpoint so it never collides with an
    in-process writer at the SQLite level. Such a collision can surface as a
    transient "database is locked" on the writer — and is the one in-process writer
    that bypasses the per-write lock, so serializing it here removes that trigger.
    """
    import time

    while True:
        time.sleep(300)
        try:
            conn = sqlite3.connect(db_path, check_same_thread=True)
            try:
                with _global_write_lock:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
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

    # Create this thread's connection if it doesn't have one yet — OR if the cached
    # connection was opened for a DIFFERENT db_path than the one we resolved above.
    # The path-mismatch case is the critical one: a long-lived daemon thread (the
    # supervisor `_run_and_finalize` loop, a `_reconciliation_window`, an embed worker)
    # opens its per-thread connection against one db, then calls get_db() again LATER —
    # by which point a test has repatched Path.home() to a fresh tmp db (or, in prod,
    # PATHLY_DB_PATH changed). Without this check the stale connection is reused, so the
    # per-path prep below runs _run_migrations() against the WRONG connection while
    # marking the NEW path as prepared — leaving the new db un-migrated ("no such table")
    # the next time any thread opens it. Keying the cached connection to its db_path keeps
    # the invariant "the connection we migrate and return matches the path we gate on".
    # In production db_path never changes, so this branch only fires once per thread.
    # Serialize the open+PRAGMA setup under the global write lock: `PRAGMA journal_mode=WAL`
    # briefly needs an exclusive DB lock, so concurrent first-time opens from many
    # threads otherwise race and intermittently raise "database is locked".
    if (
        not hasattr(_local, "conn")
        or _local.conn is None
        or getattr(_local, "conn_path", None) != db_path
    ):
        with _global_write_lock:
            stale = getattr(_local, "conn", None)
            if stale is not None:
                try:
                    stale.close()
                except Exception:
                    pass
            _local.conn = _make_conn(db_path)
            _local.conn_path = db_path

    conn = _local.conn

    # Initialization is split into two scopes, deliberately:
    #
    #  • PROCESS-ONCE (vec-extension probe + WAL checkpoint thread) — truly global, gated by
    #    `_init_once_done`.
    #  • PER-DB-PATH (migrate + seed + catalog/flow refresh) — gated by membership in
    #    `_prepared_paths`, NOT by a process-global flag.
    #
    # The per-PATH gate is what makes preparation correct under test isolation, where every
    # test swaps ~/.pathly to a fresh file. With the old single global flag, a leftover daemon
    # thread's get_db() (still pointing at the previous test's path) could win the lock and set
    # the flag, after which the next test's connection — to a brand-new, un-migrated db — would
    # skip migration and hit "no such table". Keying on the db path AND on the per-thread
    # connection's own path (the reopen-on-mismatch above) closes that race — the gate alone
    # was insufficient because a stale connection could migrate one db while marking another
    # prepared. It also avoids the contention/perf cost of re-migrating per connection: a path
    # is prepared exactly once. In production this set holds a single entry, so this is a cheap
    # membership check.
    if not _init_once_done:
        with _init_lock:
            if not _init_once_done:
                if _load_vec(conn):
                    _VEC_AVAILABLE = True
                else:
                    _VEC_AVAILABLE = False
                    logging.warning(
                        "sqlite-vec unavailable - comms board uses recency-only retrieval"
                    )
                threading.Thread(
                    target=_wal_checkpoint_loop,
                    args=(db_path,),
                    daemon=True,
                    name="pathly-wal-checkpoint",
                ).start()
                _init_once_done = True

    if db_path not in _prepared_paths:
        with _init_lock:
            if db_path not in _prepared_paths:
                # Create the schema FIRST and mark the path prepared only once it
                # succeeds. Marking in a blanket `finally` (the old behaviour) latched a
                # path whose _run_migrations() had raised as "prepared", so the next
                # get_db() skipped migration and hit "no such table". Migrations are
                # idempotent (CREATE TABLE IF NOT EXISTS + additive ALTERs skip existing
                # columns), so a transient failure simply retries on the next call.
                _run_migrations(conn, vec_available=_VEC_AVAILABLE)
                # Probe for FTS5 table AFTER migrations — comms_fts is created there.
                try:
                    conn.execute("SELECT * FROM comms_fts LIMIT 0")
                    _FTS_AVAILABLE = True
                except Exception:
                    _FTS_AVAILABLE = False
                # Schema is in place — safe to gate future calls off this path. Seed +
                # catalog/flow refresh are best-effort follow-ups: they must NOT be able to
                # un-prepare the path (that would loop re-migrating a valid schema forever).
                _prepared_paths.add(db_path)
                _seed_if_empty(conn)
                _refresh_catalog(conn)
                _refresh_flows(conn)

    return conn


def _get_write_lock(conn: sqlite3.Connection) -> "_WriteGuard":
    """Return a write guard for *conn* — the process-wide write lock plus
    rollback-on-exception (see `_WriteGuard`).

    SQLite permits only one writer at a time, and every thread holds its own
    connection — so a per-connection lock never serializes cross-thread writers;
    they race on SQLite directly and intermittently hit "database is locked" or
    drop a write. A single global lock serializes all writers in-process. The guard
    also rolls back on error so a failed write never leaks an open transaction that
    would hold the write slot forever. Used as
    `with _get_write_lock(conn): conn.execute(...); conn.commit()`.
    """
    return _WriteGuard(conn)


def retrieval_status(conn: sqlite3.Connection | None = None) -> dict:
    """Report semantic-retrieval health for /health and operators.

    Surfaces whether the sqlite-vec / FTS extensions loaded on this process AND how
    many embedding rows exist — so a silently-dark semantic channel (0 embeddings /
    vec unavailable) is observable instead of masquerading as recency results.
    """
    status: dict = {
        "vec_available": _VEC_AVAILABLE,
        "fts_available": _FTS_AVAILABLE,
        "embeddings_rows": None,
    }
    try:
        c = conn or get_db()
        status["embeddings_rows"] = c.execute(
            "SELECT COUNT(*) FROM comms_embeddings"
        ).fetchone()[0]
    except Exception:
        pass
    return status
