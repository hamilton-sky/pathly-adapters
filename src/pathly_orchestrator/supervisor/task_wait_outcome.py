"""A loop task that waits on its question: park it in the scheduler, end the run, give it the answer.

Loop tasks (``executor: loop``, the ``goal-loop`` flow) run inside an FSM fan-out stage, and the
scheduler, not the agent, completes or retries them. Before chief-autopilot 12 a task whose agent
posted a question to ``human`` (or ``*``) was completed over the open question, or retried, which
set it ``pending`` and spent an attempt.

* ``park_if_asked``: the scheduler's completion handler calls it first. When the spawn's run
  (``sched-<task>#N``) left open questions (``db/queries/task_waits.open_questions_by_run``),
  the task is parked with ``task_waits.park_and_recheck`` (``blocked``,
  ``fail_reason='waiting_for_answer:<ids>'``, ``waits + 1``; freed at once when the questions
  were answered before the park), whatever the spawn reported; the handler then calls neither
  ``complete_task`` nor ``resolve_task_failure``, so no attempt is counted, and a
  ``task_waiting`` event is broadcast. The next claim builds its run id from
  ``attempts``, which only grows, so the asking run id is never reused.
* ``note_run_waits`` / ``take_run_waits``: ``fan_out._drain`` records the parked tasks that
  still wait on the run (one released and run again in the drain does not); ``orchestrator_stage._resolve_stage_supervised`` takes them before ``complete_stage`` and
  ends the run in error with ``waiting_for_answer``. The other ready tasks have drained by then,
  and the join's ``require_tasks_done`` would otherwise send ``INCOMPLETE_TASKS`` to a builder.
* ``answered_questions_block``: when the task is claimed again, its prompt carries each answered
  question and its answer (the ids ticket 06's ``release_waiting_tasks`` kept).

Best-effort: a failure here is logged and the task is treated as not waiting.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger("pathly.task_wait_outcome")

WAITING_FOR_ANSWER = "waiting_for_answer"
_RUN_ATTR = "_waiting_tasks"


def sched_run_id(task_id: str, prior_attempts: int) -> str:
    """The loop scheduler's run id for a task's next spawn: ``sched-<task>#<attempts + 1>``."""
    return f"sched-{task_id}#{prior_attempts + 1}"


def park_if_asked(
    conn,
    task_id: str,
    task_attempts: dict,
    task_texts: dict,
    broadcast_fn: Optional[Callable],
    scope: str,
) -> bool:
    """Park the task when its spawn left an open question; True when it waits.

    ``task_waits.park_and_recheck`` parks it, and frees it at once when the questions were
    answered before the park: that task is ``pending`` again and still counts as a wait (True,
    no attempt spent), so the scheduler's next frontier read claims it with the answers. A park
    that parks nothing (the task is no longer ``in_progress``) logs a warning and returns False.

    The run id comes from ``task_attempts`` (the attempts before the claim, as the claim built
    it). On a park the task's entries in ``task_attempts`` and ``task_texts`` are dropped, so the
    attempt is never counted, and ``task_waiting`` is broadcast on the comms stream.
    """
    from pathly_orchestrator.db.queries.task_waits import (
        open_questions_by_run,
        park_and_recheck,
        task_status,
    )

    run_id = sched_run_id(task_id, int(task_attempts.get(task_id, 0)))
    try:
        question_ids = open_questions_by_run(conn, run_id)
        if not question_ids:
            return False
        parked = park_and_recheck(conn, task_id, question_ids)
        if parked == "not_parked":
            logger.warning(
                "loop task %s asked %s but was not parked (task_status %s): "
                "handled as not waiting",
                task_id,
                question_ids,
                task_status(conn, task_id),
            )
            return False
    except Exception:
        logger.warning("parking loop task %s failed", task_id, exc_info=True)
        return False
    task_attempts.pop(task_id, None)
    task_texts.pop(task_id, None)
    logger.info(
        "loop task %s waits on question(s) %s (%s)", task_id, question_ids, parked
    )
    from .scheduler import _broadcast

    _broadcast(
        broadcast_fn,
        scope,
        "task_waiting",
        {"task_id": task_id, "run_id": run_id, "questions": question_ids},
    )
    return True


def note_run_waits(state, task_ids: list) -> None:
    """Record on the run the loop tasks its last drain parked that still wait ([] clears it).

    A task released by an answer and run again in the same drain no longer waits
    (``task_waits.still_waiting``); an unreadable row keeps the whole list."""
    waiting = list(task_ids)
    if waiting:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.task_waits import still_waiting

            waiting = still_waiting(get_db(), waiting)
        except Exception:
            logger.warning("re-reading waiting tasks %s failed", waiting, exc_info=True)
    setattr(state, _RUN_ATTR, waiting)


def waits_for_answer(result) -> bool:
    """True when a stage result is a drain that parked tasks (``error`` starts with
    ``waiting_for_answer``, ``fan_out._merge_drain_result``)."""
    error = (result or {}).get("error") if isinstance(result, dict) else None
    return str(error or "").startswith(WAITING_FOR_ANSWER)


def take_run_waits(state) -> list:
    """The parked loop tasks ``note_run_waits`` recorded, cleared once read."""
    waiting = list(getattr(state, _RUN_ATTR, None) or [])
    if waiting:
        setattr(state, _RUN_ATTR, [])
    return waiting


def answered_questions_block(task: dict) -> str:
    """A prompt block with each question the task waited on and its answer, or ''.

    ``answered_questions`` is the raw JSON list of question ids on the task row (ticket 06).
    """
    raw = task.get("answered_questions")
    try:
        ids = json.loads(raw) if isinstance(raw, str) and raw else raw
        if not isinstance(ids, list) or not ids:
            return ""
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_waits import question_answers

        pairs = question_answers(get_db(), [str(q) for q in ids])
    except Exception:
        logger.debug(
            "answered questions of %s unreadable", task.get("id"), exc_info=True
        )
        return ""
    if not pairs:
        return ""
    lines = [
        "\n\n## Answers to your questions\n\n"
        "An earlier attempt at this task asked these questions and stopped to wait. They "
        "are answered now: use the answers and do not ask them again.\n"
    ]
    for pair in pairs:
        answer = pair.get("answer")
        lines.append(
            f"\n- Q: {pair.get('question') or ''}\n  A: {answer or '(no text)'}"
        )
    return "".join(lines) + "\n"
