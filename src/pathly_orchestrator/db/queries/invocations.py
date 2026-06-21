"""Query helpers for the agent_invocations table."""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock


def write_agent_invocation(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    invocation_dict: dict,
) -> int:
    """Insert an agent invocation record. Returns the new id."""
    d = invocation_dict
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO agent_invocations "
            "(project_root, feature, run_id, stage, agent_role, started_at, finished_at, "
            " tokens_in, tokens_out, cost_usd, session_id, summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root,
                feature,
                d.get("run_id"),
                d.get("stage"),
                d.get("agent_role"),
                d.get("started_at"),
                d.get("finished_at"),
                d.get("tokens_in"),
                d.get("tokens_out"),
                d.get("cost_usd"),
                d.get("session_id"),
                d.get("summary"),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_agent_invocations(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> list[dict]:
    """Return all agent invocations for *project_root*/*feature*."""
    rows = conn.execute(
        "SELECT * FROM agent_invocations WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchall()
    return [dict(r) for r in rows]
