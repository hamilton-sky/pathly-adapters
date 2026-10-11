"""Additive schema for write provenance (role-read-policy)."""

from __future__ import annotations

import sqlite3


def add_run_tokens(conn: sqlite3.Connection) -> None:
    """Create the run_tokens table (hashed server-issued spawn identity). Idempotent."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS run_tokens ("
        " token_hash TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT, feature TEXT,"
        " project_root TEXT, board TEXT, scope TEXT,"
        " created_at REAL NOT NULL, revoked_at REAL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_tokens_run_id ON run_tokens(run_id)"
    )
    conn.commit()
