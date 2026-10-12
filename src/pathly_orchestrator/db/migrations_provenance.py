"""Additive schema for run provenance (role-read-policy)."""

from __future__ import annotations

import sqlite3


def add_run_tokens(conn: sqlite3.Connection) -> None:
    """Create the run_tokens table (server-issued identity of one spawn). Idempotent."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS run_tokens ("
        " token_hash TEXT PRIMARY KEY,"
        " run_id TEXT NOT NULL,"
        " role TEXT,"
        " feature TEXT,"
        " project_root TEXT,"
        " board TEXT,"
        " scope TEXT,"
        " created_at REAL NOT NULL,"
        " revoked_at REAL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_run_tokens_run_id ON run_tokens(run_id)"
    )
    conn.commit()


_COMMS_PROVENANCE_COLUMNS = ("author_role", "author_run_id", "author_source")

# An agent_invocations row only counts as a join when it recorded a role.
_INVOCATION_WITH_ROLE = (
    "SELECT 1 FROM agent_invocations ai"
    " WHERE ai.run_id = comms_messages.run_id AND COALESCE(ai.agent_role, '') != ''"
)


def add_comms_provenance(conn: sqlite3.Connection) -> None:
    """Add author_role / author_run_id / author_source to comms_messages, then backfill.

    ``author_source`` is one of token | system | legacy | none. Every row whose source is
    still NULL is marked ``legacy`` with a best-effort role: a server-internal author is
    ``system``; else the role of the agent_invocations row its run_id joins; else
    ``from_agent`` as stored. ``author_run_id`` stays NULL (the old run_id came from the
    request body, so it is not provenance). The NULL filter makes a second run touch no row,
    and a row stamped after the upgrade already has its source. Idempotent.

    ``agent_invocations.run_id`` is indexed first: without it the backfill scans
    ``agent_invocations`` once per message that has a run_id, which is quadratic.
    """
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_invocations_run_id"
        " ON agent_invocations(run_id)"
    )
    have = {row[1] for row in conn.execute("PRAGMA table_info(comms_messages)")}
    for col in _COMMS_PROVENANCE_COLUMNS:
        if col not in have:
            try:
                conn.execute(f"ALTER TABLE comms_messages ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError as exc:
                # another process added it between the check above and this ALTER
                if "duplicate column name" not in str(exc):
                    raise
    conn.execute(
        "UPDATE comms_messages SET author_role = 'system', author_source = 'legacy'"
        " WHERE author_source IS NULL AND from_agent IN ('supervisor', 'system')"
    )
    conn.execute(
        "UPDATE comms_messages SET author_source = 'legacy', author_role = ("
        " SELECT ai.agent_role FROM agent_invocations ai"
        " WHERE ai.run_id = comms_messages.run_id AND COALESCE(ai.agent_role, '') != ''"
        " ORDER BY ai.id DESC LIMIT 1)"
        " WHERE author_source IS NULL AND COALESCE(run_id, '') != ''"
        f" AND EXISTS ({_INVOCATION_WITH_ROLE})"
    )
    conn.execute(
        "UPDATE comms_messages SET author_role = from_agent, author_source = 'legacy'"
        " WHERE author_source IS NULL"
    )
    conn.commit()
