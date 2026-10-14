"""Task reads for build proof, and the human-set floor allow list (build-proof).

``claim_task`` freezes a task's text into ``claimed_text`` on its first claim. These queries
read a task back with that frozen copy, list a run window's claimed or completed tasks, and
store the floor categories a human allowed for one task (``floor_allow``, a JSON list).

The two ``*_since`` queries are goal-scoped when ``goal_id`` is given, else scoped to
``(board, scope)``, and return nothing when neither is set: the same rule as
``fsm/gates/tasks.py::_count_incomplete``. Their windows compare parsed times, not strings,
because ``claim_task`` stamps ``+00:00`` while event ``ts`` values end in ``Z``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone

from ..connection import _get_write_lock


def get_task(conn: sqlite3.Connection, message_id: str) -> dict | None:
    """The live row ``message_id`` names, of any ``type`` (a caller checks it is a task).

    ``None`` when no row has that id or it was soft-deleted.
    """
    row = conn.execute(
        "SELECT * FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def instant(value: str | datetime | None) -> datetime | None:
    """``value`` as an aware datetime (naive means UTC); ``None`` when it is not a time."""
    if isinstance(value, datetime):
        when = value
    elif isinstance(value, str) and value.strip():
        try:
            when = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)


def _since(rows: list[sqlite3.Row], column: str, since: str | datetime) -> list[dict]:
    start = instant(since)
    if start is None:
        raise ValueError("since is not an ISO 8601 time: %r" % (since,))
    kept: list[tuple[datetime, dict]] = []
    for row in rows:
        when = instant(row[column])
        if when is not None and when >= start:
            kept.append((when, dict(row)))
    kept.sort(key=lambda pair: pair[0])
    return [task for _, task in kept]


def tasks_claimed_since(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    goal_id: str | None,
    since: str | datetime,
) -> list[dict]:
    """Live tasks with ``claimed_at >= since``, in any status, oldest claim first."""
    if goal_id:
        rows = conn.execute(
            "SELECT * FROM comms_messages "
            "WHERE goal_id=? AND type='task' AND deleted_at IS NULL "
            "AND claimed_at IS NOT NULL",
            (goal_id,),
        ).fetchall()
    elif scope:
        rows = conn.execute(
            "SELECT * FROM comms_messages "
            "WHERE board=? AND scope=? AND type='task' AND deleted_at IS NULL "
            "AND claimed_at IS NOT NULL",
            (board, scope),
        ).fetchall()
    else:
        rows = []
    return _since(rows, "claimed_at", since)


def tasks_completed_since(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    goal_id: str | None,
    since: str | datetime,
) -> list[dict]:
    """Live tasks with ``task_status='done'`` and ``completed_at >= since``, oldest first."""
    if goal_id:
        rows = conn.execute(
            "SELECT * FROM comms_messages "
            "WHERE goal_id=? AND type='task' AND task_status='done' "
            "AND deleted_at IS NULL AND completed_at IS NOT NULL",
            (goal_id,),
        ).fetchall()
    elif scope:
        rows = conn.execute(
            "SELECT * FROM comms_messages "
            "WHERE board=? AND scope=? AND type='task' AND task_status='done' "
            "AND deleted_at IS NULL AND completed_at IS NOT NULL",
            (board, scope),
        ).fetchall()
    else:
        rows = []
    return _since(rows, "completed_at", since)


def set_floor_allow(
    conn: sqlite3.Connection,
    message_id: str,
    allow: Iterable[str],
    refreeze: bool = False,
) -> bool:
    """Store ``allow`` (de-duplicated, sorted) as the task's ``floor_allow`` JSON list.

    With ``refreeze``, also copy the live ``text`` into ``claimed_text``: how a human corrects
    a task's checks. The caller validates ``allow`` (``proof.floor.parse_allow``). Returns
    ``False`` when no live task row has that id.
    """
    value = json.dumps(sorted(set(allow)))
    with _get_write_lock(conn):
        if refreeze:
            cur = conn.execute(
                "UPDATE comms_messages SET floor_allow=?, claimed_text=text "
                "WHERE id=? AND type='task' AND deleted_at IS NULL",
                (value, message_id),
            )
        else:
            cur = conn.execute(
                "UPDATE comms_messages SET floor_allow=? "
                "WHERE id=? AND type='task' AND deleted_at IS NULL",
                (value, message_id),
            )
        conn.commit()
    return cur.rowcount == 1
