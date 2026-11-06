"""Additive schema for routed questions (chief-autopilot-round-two 01).

``consult_routes`` keeps one row per board question that was routed to a role's consult run or
handed on to the person: the role, the asking task, its goal key, the asking and the consult run,
the status (``queued``, ``running``, ``answered``, ``to_person``, ``withheld``, ``failed``) and the
reason. The caps, the drain wait, the notices and the startup cleanup all read it.
"""

from __future__ import annotations

import sqlite3


def add_consult_routes(conn: sqlite3.Connection) -> None:
    """Create ``consult_routes`` and its goal index. Idempotent."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS consult_routes ("
        " question_id TEXT PRIMARY KEY,"
        " role TEXT NOT NULL,"
        " task_id TEXT,"
        " goal_key TEXT,"
        " asking_run_id TEXT,"
        " consult_run_id TEXT,"
        " status TEXT NOT NULL,"
        " reason TEXT,"
        " created_at REAL NOT NULL,"
        " ended_at REAL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_consult_routes_goal ON consult_routes(goal_key)"
    )
    conn.commit()
