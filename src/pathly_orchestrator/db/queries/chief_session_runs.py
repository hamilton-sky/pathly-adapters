"""The runs a chief session started, and the notices they become (chief-autopilot 08).

A chief token's call that starts work records a row (``record_session_run``, from the
``after_request`` hook in ``http_server/chief_run_record.py``). ``ended_unread_runs`` lists the
project's rows whose run reached a terminal status in ``run_history`` (``done``, ``error``,
``aborted`` and ``parked``: the ends ``registry._set_status`` and ``terminal_identity`` write; a
parked run's row is final too, because resuming it starts a NEW run id,
``supervisor/api.resume_parked_run``) and that nobody marked read; ``mark_runs_read`` marks them.
Recording a run deletes the project's rows marked read more than ``READ_KEPT_SECONDS`` (30 days)
ago, so the table does not grow forever.
``run_notice`` reads what a notice shows of one run with the helpers behind ``GET /runs/<id>``,
without its stages, logs, board posts or artifacts, with the run's routed questions
(``run_consults``). ``open_questions_on_board`` counts the
questions and escalations to the person (``human`` or ``*``) still open on a board: the rows that
park a task (ticket 06). Rows outlive the session that made them, so the next chief of the project
sees them.

Every SQL here is one literal.
"""

from __future__ import annotations

import sqlite3
import time

from ..connection import _get_write_lock
from .run_consults import consult_fields
from .run_history_read import _classify_kind, _run_cost, _run_outcome

READ_KEPT_SECONDS = 30 * 86400
DEFAULT_NOTICES = 50


def record_session_run(
    conn: sqlite3.Connection,
    session_run_id: str,
    run_id: str,
    project_root: str,
    started_at: float | None = None,
) -> bool:
    """Record that the chief session ``session_run_id`` started ``run_id`` in ``project_root``.

    False, writing nothing, when the run is already recorded (a run id is recorded once). Deletes
    the project's rows marked read more than ``READ_KEPT_SECONDS`` ago either way.
    """
    now = time.time()
    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM chief_session_runs"
            " WHERE project_root = ? AND read_at IS NOT NULL AND read_at < ?",
            (project_root, now - READ_KEPT_SECONDS),
        )
        cur = conn.execute(
            "INSERT OR IGNORE INTO chief_session_runs"
            " (run_id, session_run_id, project_root, started_at)"
            " VALUES (?, ?, ?, ?)",
            (run_id, session_run_id, project_root, started_at or now),
        )
        conn.commit()
        return cur.rowcount == 1


def ended_unread_runs(
    conn: sqlite3.Connection, project_root: str, limit: int = DEFAULT_NOTICES
) -> list[dict]:
    """The project's recorded runs that ended and are unread, oldest
    first, at most ``limit``: ``{run_id, session_run_id, started_at}``."""
    rows = conn.execute(
        "SELECT s.run_id, s.session_run_id, s.started_at FROM chief_session_runs s"
        " JOIN run_history h ON h.run_id = s.run_id"
        " WHERE s.project_root = ? AND s.read_at IS NULL"
        " AND h.status IN ('done', 'error', 'aborted', 'parked')"
        " ORDER BY s.started_at ASC, s.run_id ASC LIMIT ?",
        (project_root, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def run_notice(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """What a notice shows of ``run_id``: ``{kind, status, outcome, error, cost_usd,
    finished_at, board, consults, waiting_for_person}``, read as ``GET /runs/<id>`` reads them (``run_history_read``), or None
    for a run with no ``run_history`` row. ``board`` is the run's ``board_scope``, else its
    feature."""
    row = conn.execute(
        "SELECT * FROM run_history WHERE run_id = ?", (run_id,)
    ).fetchone()
    if row is None:
        return None
    kind = _classify_kind(row["run_id"], row["adapter"])
    notice = {
        "kind": kind,
        "status": row["status"],
        "cost_usd": _run_cost(conn, row, kind)[0],
        "finished_at": row["finished_at"],
        "board": row["board_scope"] or row["feature"],
    }
    notice.update(_run_outcome(conn, row["feature"], row["run_id"]))
    notice.update(consult_fields(conn, row))
    return notice


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

    ``comms_messages`` has no project column: a board is its scope, so two projects with a
    feature of the same name share one board in the database, and the count includes both.
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
