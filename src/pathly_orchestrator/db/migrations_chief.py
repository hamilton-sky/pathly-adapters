"""Additive schema for the chief agent's sessions, human messages and citations."""

from __future__ import annotations

import sqlite3


def add_chief_tables(conn: sqlite3.Connection) -> None:
    """Create chief_sessions, chief_human_messages and chief_citations. Idempotent."""
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
