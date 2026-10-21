"""Additive schema for the chief agent's sessions, human messages and citations.

``chief_sessions.runs_started`` (the runs a session has started, counted by the chief gate) is a
column added after the table existed, so it is added with ``ALTER TABLE`` to a database that has
the table without it; ``CREATE TABLE IF NOT EXISTS`` alone would never add it.
"""

from __future__ import annotations

import sqlite3


def _has_runs_started(conn: sqlite3.Connection) -> bool:
    return any(
        row[1] == "runs_started"
        for row in conn.execute("PRAGMA table_info(chief_sessions)")
    )


def _add_runs_started(conn: sqlite3.Connection) -> None:
    """Add ``chief_sessions.runs_started`` once. Another connection may add it between the check
    and the ``ALTER`` (the error is then "duplicate column name"); only a column still missing
    after the error is a failure.
    """
    if _has_runs_started(conn):
        return
    try:
        conn.execute(
            "ALTER TABLE chief_sessions"
            " ADD COLUMN runs_started INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
        if not _has_runs_started(conn):
            raise


def add_chief_tables(conn: sqlite3.Connection) -> None:
    """Create chief_sessions, chief_human_messages and chief_citations. Idempotent.

    The columns of ``chief_sessions`` that came later (``runs_started``) are added to a table
    made before them, once.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chief_sessions ("
        " run_id TEXT PRIMARY KEY,"
        " project_root TEXT NOT NULL,"
        " preset TEXT,"
        " tier TEXT NOT NULL,"
        " engine TEXT NOT NULL,"
        " tab_id TEXT,"
        " cli_session_id TEXT,"
        " hook_secret_hash TEXT,"
        " settings_dir TEXT,"
        " opened_at REAL NOT NULL,"
        " closed_at REAL,"
        " close_reason TEXT)"
    )
    _add_runs_started(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chief_sessions_project_root"
        " ON chief_sessions(project_root)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chief_human_messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " run_id TEXT NOT NULL,"
        " project_root TEXT,"
        " kind TEXT NOT NULL,"
        " text TEXT NOT NULL,"
        " ts REAL NOT NULL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chief_human_messages_run_id"
        " ON chief_human_messages(run_id)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chief_citations ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " run_id TEXT NOT NULL,"
        " message_id INTEGER NOT NULL UNIQUE,"
        " route TEXT NOT NULL,"
        " target TEXT,"
        " ts REAL NOT NULL)"
    )
    conn.commit()
