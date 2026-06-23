"""Regression: a write that raises inside `_get_write_lock` must roll back and
free the write slot — never leave the connection in an open transaction.

Before the `_WriteGuard` fix, a failed write (e.g. a transient "database is locked"
from the WAL-checkpoint thread, or any exception between sqlite3's implicit BEGIN and
conn.commit()) left the connection mid-transaction, holding SQLite's single writer
slot forever → every later writer got a permanent "database is locked".
"""

from __future__ import annotations

import sqlite3

import pytest


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    return conn


def test_write_guard_rolls_back_on_exception():
    from pathly_orchestrator.db.connection import _get_write_lock

    conn = _fresh_conn()

    with pytest.raises(RuntimeError):
        with _get_write_lock(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            assert conn.in_transaction  # sqlite3 issued an implicit BEGIN
            raise RuntimeError("boom before commit")

    # The guard rolled back: no leaked open transaction, the write was undone.
    assert conn.in_transaction is False
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_write_slot_usable_after_a_failed_write():
    from pathly_orchestrator.db.connection import _get_write_lock

    conn = _fresh_conn()

    with pytest.raises(RuntimeError):
        with _get_write_lock(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("boom")

    # A subsequent normal write must succeed — the writer slot is free, not stuck.
    with _get_write_lock(conn):
        conn.execute("INSERT INTO t VALUES (2)")
        conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_successful_write_still_commits():
    """The happy path is unchanged: the body's explicit commit persists the row."""
    from pathly_orchestrator.db.connection import _get_write_lock

    conn = _fresh_conn()
    with _get_write_lock(conn):
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
    assert conn.in_transaction is False
    assert conn.execute("SELECT x FROM t").fetchone()[0] == 42
