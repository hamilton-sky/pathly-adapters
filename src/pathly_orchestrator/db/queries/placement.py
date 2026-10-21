"""Where an id lives: the project a run was recorded for, the board a message is on.

Read only, one static statement each. The chief gate (``http_server/chief_bind``) asks these to
tell whether the run, goal, task or message a chief names by id belongs to the chief's project.
"""

from __future__ import annotations

import sqlite3


def run_project_root(conn: sqlite3.Connection, run_id: str) -> str | None:
    """The project root ``run_history`` recorded for ``run_id`` (forward slashes, as stored), or
    None when the history does not know the run. Every spawn writes this row before its process
    starts and a finished run keeps it, so it is the run's identity map.
    """
    row = conn.execute(
        "SELECT project_root FROM run_history WHERE run_id=?", (run_id,)
    ).fetchone()
    return None if row is None else row["project_root"]


def message_board_scope(
    conn: sqlite3.Connection, message_id: str
) -> tuple[str | None, str | None] | None:
    """``(board, scope)`` of the ``comms_messages`` row ``message_id`` (a goal and a task are such
    rows), exactly as stored, or None when no row has the id. A row in the trash is still a row:
    it is found, so a soft delete does not make another project's message look unknown.
    """
    row = conn.execute(
        "SELECT board, scope FROM comms_messages WHERE id=?", (message_id,)
    ).fetchone()
    return None if row is None else (row["board"], row["scope"])
