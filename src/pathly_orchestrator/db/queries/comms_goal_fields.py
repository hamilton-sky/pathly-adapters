"""Goal-message field accessors — the goal-specific COLUMNS on ``comms_messages``.

``executor``, ``slug`` and the ``(board, scope)`` a goal lives on are read and written
per-goal-message rather than as part of the general message CRUD in
``comms_messages.py``, so they live together here (SOLID rule #1) — the write-side
counterpart to ``comms_goals_read.py``'s rollup read-model.

Extracted from ``comms_messages.py``, which sits on the 400-line ratchet and had to
shrink to gain the scheduler's ``lane`` column. Every name is re-exported from
``comms_messages`` and from the ``comms`` shim, so no call site moved.
"""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock


def set_goal_executor(conn: sqlite3.Connection, message_id: str, executor: str) -> None:
    """Persist the chosen executor on a goal message (UI selector override)."""
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET executor=? WHERE id=? AND type='goal'",
            (executor, message_id),
        )
        conn.commit()


def set_message_slug(conn: sqlite3.Connection, message_id: str, slug: str) -> None:
    """Persist the filesystem slug on a goal message."""
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET slug=? WHERE id=?",
            (slug, message_id),
        )
        conn.commit()


def read_message_slug(conn: sqlite3.Connection, message_id: str) -> dict | None:
    """Read slug + text for a goal message. Returns None if not found."""
    row = conn.execute(
        "SELECT slug, text FROM comms_messages WHERE id=? AND type='goal'",
        (message_id,),
    ).fetchone()
    if row is None:
        return None
    return {"slug": row["slug"], "text": row["text"]}


def get_goal_board_scope(
    conn: sqlite3.Connection, goal_id: str
) -> tuple[str, str] | None:
    """Return ``(board, scope)`` for a goal message, or None if not a live goal.

    Used to decouple the *board scope* a goal's decompose agents post to (the
    parent feature/project board the goal lives on) from the *run identity* the
    consultation FSM uses on disk (the goal slug). Without this the consultation
    posts to a throwaway slug-scoped board instead of the board it was spawned from.
    """
    if not goal_id:
        return None
    row = conn.execute(
        "SELECT board, scope FROM comms_messages "
        "WHERE id=? AND type='goal' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    board = (row["board"] or "").strip()
    scope = (row["scope"] or "").strip()
    if not board or not scope:
        return None
    return board, scope
