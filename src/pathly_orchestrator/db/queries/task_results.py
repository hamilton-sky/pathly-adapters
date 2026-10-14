"""What a DAG task reported when its agent finished (build-proof).

A task agent writes an ``AGENT_DONE`` event whose ``run_id`` is ``sched-<task id>#<attempt>``
(``supervisor/scheduler.py`` names the run, ``supervisor/terminal.py`` substitutes it for the
``<run_id>`` placeholder). The newest one's ``summary`` is the task's result: no result
column and no new write path, so a task prompt can show it to the tasks that depend on it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def latest_task_summaries(
    conn: sqlite3.Connection, task_ids: Iterable[str]
) -> dict[str, str]:
    """The newest ``AGENT_DONE`` ``summary`` of each task's ``sched-<id>#<n>`` runs.

    Only ids that have such an event with a non-empty summary appear in the result.
    """
    found: dict[str, str] = {}
    for task_id in task_ids:
        row = conn.execute(
            "SELECT json_extract(payload, '$.summary') FROM fsm_events "
            "WHERE event_type='AGENT_DONE' "
            "AND json_extract(payload, '$.run_id') LIKE ? "
            "ORDER BY seq DESC LIMIT 1",
            (f"sched-{task_id}#%",),
        ).fetchone()
        if row is not None and isinstance(row[0], str) and row[0].strip():
            found[task_id] = row[0]
    return found
