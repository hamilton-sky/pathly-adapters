"""A run's routed questions (chief-autopilot-round-two 09).

db/ layer, read only. ``consults_of_run`` lists the ``consult_routes`` rows (ticket 01) asked by a
run or by one of its children (a loop parent's ``sched-`` tasks, a flow's stages:
``run_history_read._child_rows``); ``waiting_for_person`` counts those handed to the person
(``to_person``) or withheld whose question no live ``answer`` row replies to yet. ``GET
/runs/<id>`` and the chief's notices both read them.

Every SQL here is one literal.
"""

from __future__ import annotations

import json
import sqlite3

from .consult_routes import CONSULT_RUN_PREFIX

CONSULT_KIND = "consult"
_WAITS = ("to_person", "withheld")


def is_consult_run(run_id: str | None) -> bool:
    """True for a consult run's id (``consult-<hex>``, ``supervisor/consult_run``)."""
    return (run_id or "").startswith(CONSULT_RUN_PREFIX)


def consults_of_run(conn: sqlite3.Connection, run_row: sqlite3.Row) -> list[dict]:
    """``[{question_id, role, status, consult_run_id, reason}]`` asked by the run of ``run_row``
    or one of its children, oldest first."""
    from .run_history_read import _child_rows, _is_parent

    ids = [run_row["run_id"]]
    if _is_parent(run_row["run_id"], run_row["adapter"]):
        ids += [r["run_id"] for r in _child_rows(conn, run_row)]
    rows = conn.execute(
        "SELECT question_id, role, status, consult_run_id, reason FROM consult_routes"
        " WHERE asking_run_id IN (SELECT value FROM json_each(?))"
        " ORDER BY created_at ASC, question_id ASC",
        (json.dumps(ids),),
    ).fetchall()
    return [dict(r) for r in rows]


def waiting_for_person(conn: sqlite3.Connection, consults: list[dict]) -> int:
    """How many of ``consults`` were handed to the person or withheld and are unanswered."""
    ids = [c["question_id"] for c in consults if c["status"] in _WAITS]
    if not ids:
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM json_each(?) q WHERE NOT EXISTS ("
        "SELECT 1 FROM comms_messages a WHERE a.type = 'answer'"
        " AND a.reply_to = q.value AND a.deleted_at IS NULL)",
        (json.dumps(ids),),
    ).fetchone()
    return int(row[0])


def consult_fields(conn: sqlite3.Connection, run_row: sqlite3.Row) -> dict:
    """``{consults, waiting_for_person}`` of the run of ``run_row``."""
    consults = consults_of_run(conn, run_row)
    return {
        "consults": consults,
        "waiting_for_person": waiting_for_person(conn, consults),
    }
