"""The run counter of a chief session (chief-agent 15): ``chief_sessions.runs_started``.

The chief gate counts every call that starts work against the session that made it and refuses
the call past the session's limit. ``take_run_slot`` is the count and ``give_back_run_slot`` is
its undo, for a start the route then refused with a 4xx. Each is one statement, so the check and
the change are one step: two requests cannot both take the last slot.
"""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock


def take_run_slot(conn: sqlite3.Connection, run_id: str, limit: int) -> bool:
    """Count one started run for the session ``run_id`` if it has started fewer than ``limit``.

    One conditional ``UPDATE`` under the process-wide write lock decides it. False, writing
    nothing, when the session does not exist or has no room left (a ``limit`` of 0 or below
    leaves none). ``limit`` must fit in 64 bits (``chief_budget.run_limit`` clamps it).
    """
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE chief_sessions SET runs_started = runs_started + 1"
            " WHERE run_id = ? AND runs_started < ?",
            (run_id, limit),
        )
        conn.commit()
        return cur.rowcount == 1


def give_back_run_slot(conn: sqlite3.Connection, run_id: str) -> bool:
    """Take back one counted run of the session; False, writing nothing, when it has none."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE chief_sessions SET runs_started = runs_started - 1"
            " WHERE run_id = ? AND runs_started > 0",
            (run_id,),
        )
        conn.commit()
        return cur.rowcount == 1
