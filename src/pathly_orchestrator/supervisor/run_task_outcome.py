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

It returns the error (``task_unfinished``) so the caller's synthetic ``AGENT_DONE`` can carry
``outcome: failed``, or None when the run is unchanged. Loop tasks are the scheduler's
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

_failed_runs: set[str] = set()
_failed_lock = threading.Lock()


def counted_attempts(task: dict) -> int:
    """The attempts that count against ``goal.task_max_attempts``: every claim, for now.
    (Ticket 06 subtracts the attempts that only waited on a question.)"""
    return int(task.get("attempts") or 0)


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


def settle_run_tasks(
    state: RunnerState,
    run_id: str,
    storage: Path,
    own_agent_done: Optional[dict] = None,
) -> Optional[str]:
    """Free the tasks this run left ``in_progress`` and mark the run failed (module doc).

    ``own_agent_done`` is the agent's own ``AGENT_DONE`` for this run, or None when it wrote
    none (the caller then writes the synthetic one with the returned error)."""
    if not _owns_its_tasks(state, run_id):
        return None
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_tasks_by_run import (
            get_unfinished_tasks_of_run,
        )

        from .task_retry import resolve_max_attempts

        conn = get_db()
        tasks = get_unfinished_tasks_of_run(conn, run_id)
        if not tasks:
            return None
        limit = resolve_max_attempts()
        for task in tasks:
            _free_task(conn, task, limit)
        with _failed_lock:
            _failed_runs.add(run_id)
        if own_agent_done is not None and own_agent_done.get("outcome") != "failed":
            _record_run_outcome(storage, run_id, TASK_UNFINISHED)
        logger.info(
            "run %s left %d task(s) unfinished: run failed, tasks freed",
            run_id[:8],
            len(tasks),
        )
        return TASK_UNFINISHED
    except Exception:
        logger.warning("settle_run_tasks failed for run %s", run_id, exc_info=True)
        return None


def take_run_failure(run_id: str) -> bool:
    """True once for a run ``settle_run_tasks`` failed; read by ``_settle_spawn_identity``."""
    with _failed_lock:
        if run_id in _failed_runs:
            _failed_runs.discard(run_id)
            return True
        return False
