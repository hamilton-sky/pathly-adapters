"""Additive schema for tasks that wait on a question (chief-autopilot 06).

``comms_messages.waits`` counts the times a task was parked on an open question (``attempts``
only grows, so the attempt limit compares ``attempts - waits``). ``answered_questions`` keeps the
ids of the questions a freed task waited for, as a JSON list, for its next attempt. Both are
added with ``ALTER TABLE`` to a database that has the table without them.
"""

from __future__ import annotations

import sqlite3


def _has_column(conn: sqlite3.Connection, name: str) -> bool:
    return any(
        row[1] == name for row in conn.execute("PRAGMA table_info(comms_messages)")
    )


def _add_column(conn: sqlite3.Connection, name: str, ddl: str) -> None:
    """Add one column once. Another connection may add it between the check and the
    ``ALTER`` ("duplicate column name"); only a column still missing after the error fails.
    """
    if _has_column(conn, name):
        return
    try:
        conn.execute(ddl)
    except sqlite3.OperationalError:
        if not _has_column(conn, name):
            raise


def add_task_waits(conn: sqlite3.Connection) -> None:
    """Add ``comms_messages.waits`` and ``comms_messages.answered_questions``. Idempotent."""
    _add_column(
        conn,
        "waits",
        "ALTER TABLE comms_messages ADD COLUMN waits INTEGER NOT NULL DEFAULT 0",
    )
    _add_column(
        conn,
        "answered_questions",
        "ALTER TABLE comms_messages ADD COLUMN answered_questions TEXT",
    )
    conn.commit()
