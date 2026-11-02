"""The runs a chief session started, and the notices they become (chief-autopilot 08).

A chief token's call that starts work records a row (``record_session_run``, from the
``after_request`` hook in ``http_server/chief_run_record.py``). ``ended_unread_runs`` lists the
project's rows whose run reached a terminal status in ``run_history`` (``done``, ``error``,
``aborted``: the ends ``registry._set_status`` and ``terminal_identity`` write; ``parked`` waits
for a human and may resume, so it is not one) and that nobody marked
read; ``mark_runs_read`` marks them. ``open_questions_on_board`` counts the questions and
escalations to the person (``human`` or ``*``) still open on a board: the rows that park a task
(ticket 06). Rows outlive the session that made them, so the next chief of the project sees them.

Every SQL here is one literal.
"""

from __future__ import annotations

import sqlite3
import time

from ..connection import _get_write_lock


def record_session_run(
    conn: sqlite3.Connection,
    session_run_id: str,
    run_id: str,
    project_root: str,
    started_at: float | None = None,
) -> bool:
    """Record that the chief session ``session_run_id`` started ``run_id`` in ``project_root``.

    False, writing nothing, when the run is already recorded (a run id is recorded once).
    """
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR IGNORE INTO chief_session_runs"
            " (run_id, session_run_id, project_root, started_at)"
            " VALUES (?, ?, ?, ?)",
            (run_id, session_run_id, project_root, started_at or time.time()),
        )
        conn.commit()
        return cur.rowcount == 1


def ended_unread_runs(conn: sqlite3.Connection, project_root: str) -> list[dict]:
    """The project's recorded runs that ended and are unread, oldest
    first: ``{run_id, session_run_id, started_at}``."""
    rows = conn.execute(
        "SELECT s.run_id, s.session_run_id, s.started_at FROM chief_session_runs s"
        " JOIN run_history h ON h.run_id = s.run_id"
        " WHERE s.project_root = ? AND s.read_at IS NULL"
        " AND h.status IN ('done', 'error', 'aborted')"
        " ORDER BY s.started_at ASC, s.run_id ASC",
        (project_root,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_runs_read(
    conn: sqlite3.Connection, project_root: str, run_ids: list[str]
) -> int:
    """Mark the project's unread rows of ``run_ids`` read; the number of rows marked.

    A run of another project, or one already read, is left as it is.
    """
    now = time.time()
    marked = 0
    with _get_write_lock(conn):
        for run_id in run_ids:
            cur = conn.execute(
                "UPDATE chief_session_runs SET read_at = ?"
                " WHERE run_id = ? AND project_root = ? AND read_at IS NULL",
                (now, run_id, project_root),
            )
            marked += cur.rowcount
        conn.commit()
    return marked


def open_questions_on_board(conn: sqlite3.Connection, scope: str) -> int:
    """The questions and escalations to ``human`` or ``*`` still open on the board ``scope``.

    Open: live, not superseded, ``pending`` or ``active`` (acknowledged), and no live
    ``type: answer`` row replies to it. A blank scope matches nothing.
    """
    if not scope:
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM comms_messages q"
        " WHERE q.type IN ('question', 'escalation') AND q.scope = ?"
        " AND q.deleted_at IS NULL"
        " AND (q.superseded_by IS NULL OR q.superseded_by = '')"
        " AND lower(trim(COALESCE(q.to_agent, '*'))) IN ('human', '*')"
        " AND COALESCE(q.status, 'pending') IN ('pending', 'active')"
        " AND NOT EXISTS (SELECT 1 FROM comms_messages a WHERE a.type = 'answer'"
        " AND a.reply_to = q.id AND a.deleted_at IS NULL)",
        (scope,),
    ).fetchone()
    return int(row[0])
