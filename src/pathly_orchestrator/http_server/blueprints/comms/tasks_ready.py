"""The answers a task waited for, on its ``GET /comms/tasks`` row (chief-autopilot 06).

A task parked on a question (``db/queries/task_waits.py``) and freed by an answer keeps the
question ids in its ``answered_questions`` column (a JSON list). Here each row's raw column is
replaced by ``[{question, answer}]``, so the single agent that claims it next (drain-dag reads
the ready list) sees what the person answered. A task that never waited carries ``[]``.
"""

from __future__ import annotations

import json


def _ids(raw) -> list[str]:
    try:
        ids = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return [str(i) for i in ids] if isinstance(ids, list) else []


def add_answered_questions(conn, tasks: list[dict]) -> None:
    """Set ``answered_questions`` on each task row to its ``[{question, answer}]``."""
    from pathly_orchestrator.db.queries.task_waits import question_answers

    for task in tasks:
        ids = _ids(task.get("answered_questions"))
        task["answered_questions"] = question_answers(conn, ids) if ids else []
