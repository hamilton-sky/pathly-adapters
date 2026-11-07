"""No success over an unfinished task: the end-of-run task check for board and single runs.

A board or single run (executor-owned telemetry) has no per-task retry of its own:
``task_retry.resolve_task_failure`` is called only by the loop scheduler, and ``claim_task``
needs ``pending``. So a run that claimed a task and ended with it still ``in_progress`` used to
end ``success`` and leave the task stuck for good (chief-autopilot 05, spike S6).

``settle_run_tasks`` runs once at the end of such a run. When the run still holds an
``in_progress`` task (``claimed_by`` is the run id since ticket 11), it:

* frees each task: back to ``pending`` with ``fail_reason='task_unfinished'``, counting the
  attempt the claim already took; at ``goal.task_max_attempts`` it is failed instead, its
  dependents blocked and an escalation posted (the loop's ``task_retry`` helpers);
* records the run as failed for ``_settle_spawn_identity`` (``run_history`` status ``error``);
* when the agent wrote its own ``AGENT_DONE`` that does not say failed, appends a
  ``RUN_OUTCOME`` event. A second ``AGENT_DONE`` would give the run a second invocation row;
  the projection ignores ``RUN_OUTCOME``, and ``GET /runs/<id>`` reads it over the AGENT_DONE.

A run that posted a question to ``human`` (or ``*``) that is still unanswered parks those tasks
instead (chief-autopilot 06, ``db/queries/task_waits.py``): ``blocked`` with
``fail_reason='waiting_for_answer:<ids>'`` and ``waits + 1``, freed by any answer; the run is
failed with ``waiting_for_answer``. ``counted_attempts`` is ``attempts - waits``, so a wait never
spends a retry.

It returns the error (``task_unfinished`` or ``waiting_for_answer``) so the caller's synthetic
``AGENT_DONE`` can carry ``outcome: failed``, or None when the run is unchanged. A spawn that raises (non-zero exit,
timeout, stop) never reaches it: ``free_tasks_of_failed_spawn`` frees (or parks) its tasks
from the spawn's ``finally`` instead. Loop tasks are the scheduler's
(``sched-`` run ids, the ``goal-loop`` flow) and are never touched here. Best-effort: never
raises into the spawn path.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from .state import RunnerState, logger

TASK_UNFINISHED = "task_unfinished"
WAITING_FOR_ANSWER = "waiting_for_answer"

_failed_runs: set[str] = set()
_failed_lock = threading.Lock()


def counted_attempts(task: dict) -> int:
    """The attempts that count against ``goal.task_max_attempts``: every claim minus the
    ones that only waited on a question (``waits``)."""
    return int(task.get("attempts") or 0) - int(task.get("waits") or 0)


def _owns_its_tasks(state: RunnerState, run_id: str) -> bool:
    """A board or single run: executor-owned, not a loop task (the scheduler owns those)."""
    if not getattr(state, "executor_owned_telemetry", False) or not run_id:
        return False
    return (state.flow or "").lower() != "goal-loop" and not run_id.startswith("sched-")


def _free_task(conn, task: dict, limit: int) -> None:
    """Back to ``pending`` for another attempt, or failed with an escalation past the limit."""
    from pathly_orchestrator.db.queries.comms_task_fail import fail_task

    from .task_retry import _post_escalation, retry_task

    attempts = counted_attempts(task)
    if attempts < limit:
        retry_task(conn, task["id"], TASK_UNFINISHED)
        return
    fail_task(conn, task["id"], reason=TASK_UNFINISHED)
    _post_escalation(
        task["board"],
        task["scope"],
        task.get("goal_id"),
        task["id"],
        task.get("text") or "",
        TASK_UNFINISHED,
        attempts,
    )


def _record_run_outcome(storage: Path, run_id: str, error: str) -> None:
    from pathly_orchestrator import eventlog

    eventlog.append_event(
        str(storage),
        {
            "type": "RUN_OUTCOME",
            "run_id": run_id,
            "outcome": "failed",
            "error": error,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )


def _free_unfinished(run_id: str) -> tuple[Optional[str], int]:
    """Park (open question) or free every task the run left ``in_progress``: the error and
    the number of tasks, or ``(None, 0)`` when it left none."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_tasks_by_run import (
        get_unfinished_tasks_of_run,
    )
    from pathly_orchestrator.db.queries.task_waits import (
        open_questions_by_run,
        park_and_recheck,
    )

    from .task_retry import resolve_max_attempts

    conn = get_db()
    tasks = get_unfinished_tasks_of_run(conn, run_id)
    if not tasks:
        return None, 0
    questions = open_questions_by_run(conn, run_id)
    if questions:
        for task in tasks:
            park_and_recheck(conn, task["id"], questions)
        return WAITING_FOR_ANSWER, len(tasks)
    limit = resolve_max_attempts()
    for task in tasks:
        _free_task(conn, task, limit)
    return TASK_UNFINISHED, len(tasks)


def settle_run_tasks(
    state: RunnerState,
    run_id: str,
    storage: Path,
    own_agent_done: Optional[dict] = None,
    *,
    always_record: bool = False,
) -> Optional[str]:
    """Free the tasks this run left ``in_progress`` and mark the run failed (module doc).

    ``own_agent_done`` is the agent's own ``AGENT_DONE`` for this run, or None when it wrote
    none (the caller then writes the synthetic one with the returned error). With
    ``always_record`` the ``RUN_OUTCOME`` is written even without one, for a caller that
    writes no synthetic ``AGENT_DONE``."""
    if not _owns_its_tasks(state, run_id):
        return None
    try:
        error, freed = _free_unfinished(run_id)
        if not error:
            return None
        with _failed_lock:
            _failed_runs.add(run_id)
        own_failed = (own_agent_done or {}).get("outcome") == "failed"
        if (own_agent_done is not None or always_record) and not own_failed:
            _record_run_outcome(storage, run_id, error)
        logger.info(
            "run %s left %d task(s) unfinished: run failed (%s)",
            run_id[:8],
            freed,
            error,
        )
        return error
    except Exception:
        logger.warning("settle_run_tasks failed for run %s", run_id, exc_info=True)
        return None


def settle_early_advance(
    state: RunnerState,
    run_id: str,
    storage: Path,
    agent_done: Optional[dict],
    result: dict,
) -> None:
    """The early-advance path: the feature's latest ``AGENT_DONE`` counts as this run's own
    only when its ``run_id`` is this run's. No synthetic ``AGENT_DONE`` follows here, so the
    failure is always recorded as a ``RUN_OUTCOME``, and ``result`` (what the spawn returns)
    is marked failed so the caller does not report success."""
    own = agent_done if (agent_done or {}).get("run_id") == run_id else None
    error = settle_run_tasks(state, run_id, storage, own, always_record=True)
    if error:
        mark_failed(result, error)


def mark_failed(result: dict, error: str) -> None:
    """Put ``outcome: failed`` and ``error`` on a spawn's returned result dict."""
    result["outcome"] = "failed"
    result["error"] = error


def mark_pty_failed(data: Optional[dict], error: str) -> None:
    """Mark a PTY result (``data['result']`` is what the spawn returns) failed."""
    if not isinstance(data, dict):
        return
    result = data.get("result")
    if not isinstance(result, dict):
        result = {}
        data["result"] = result
    mark_failed(result, error)


def free_tasks_of_failed_spawn(state: RunnerState, run_id: str) -> None:
    """A spawn that raised (non-zero exit, timeout, stop) frees the tasks it left
    ``in_progress`` (or parks them on its open questions), nothing else: its ``run_history``
    row already says ``error``, and no ``AGENT_DONE`` or ``RUN_OUTCOME`` is written."""
    if not _owns_its_tasks(state, run_id):
        return
    try:
        error, freed = _free_unfinished(run_id)
        if freed:
            logger.info(
                "failed run %s left %d task(s) unfinished: %s",
                run_id[:8],
                freed,
                error,
            )
    except Exception:
        logger.warning(
            "free_tasks_of_failed_spawn failed for run %s", run_id, exc_info=True
        )


def take_run_failure(run_id: str) -> bool:
    """True once for a run ``settle_run_tasks`` failed; read by ``_settle_spawn_identity``."""
    with _failed_lock:
        if run_id in _failed_runs:
            _failed_runs.discard(run_id)
            return True
        return False
