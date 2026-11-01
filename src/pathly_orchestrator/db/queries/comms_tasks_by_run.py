"""Tasks held by one run: the board tasks a run claimed and left ``in_progress``.

Since chief-autopilot 11, ``claimed_by`` is the run id of the run that claimed the task, so the
end of a board or single run can find the tasks it left unfinished (chief-autopilot 05). Kept out
of ``comms_tasks.py``, which is near its 400-line limit. Read only.
"""

from __future__ import annotations

import sqlite3


def get_unfinished_tasks_of_run(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """The tasks still ``in_progress`` with ``claimed_by`` = ``run_id``, oldest first.

    Each row carries what freeing, parking or failing it needs: id, board, scope, goal_id,
    text, attempts (the count the claim already raised) and waits (the parks on a question,
    chief-autopilot 06). A blank ``run_id`` matches nothing.
    """
    if not run_id:
        return []
    rows = conn.execute(
        "SELECT id, board, scope, goal_id, text, attempts, waits FROM comms_messages "
        "WHERE type='task' AND task_status='in_progress' AND claimed_by=? "
        "AND deleted_at IS NULL ORDER BY ts ASC",
        (run_id,),
    ).fetchall()
    return [dict(r) for r in rows]
