"""Size a goal run's iteration cap from its DAG (build-proof 12).

A run's ``max_iterations`` is the caller's number (10 by default), but a goal that decomposes
into dozens of tasks needs more stage passes than that: every task can be attempted up to
``goal.task_max_attempts`` times, and each attempt can be sent back ``MAX_FEEDBACK_ROUNDS``
times. :func:`refresh` raises the cap to ``tasks x attempts x (MAX_FEEDBACK_ROUNDS + 1)`` when
that is larger. It runs after every stage (``_resolve_stage_supervised``), so the budget follows
the DAG as decomposition adds tasks. It never lowers the cap: a DAG that shrinks must not cut a
running run short. The cost cap and the ``cap_exceeded`` handling are untouched.
"""

from __future__ import annotations

from .registry import _lock
from .state import MAX_FEEDBACK_ROUNDS, RunnerState, logger


def refresh(state: RunnerState) -> None:
    """Raise ``state.max_iterations`` to the DAG's budget when it is larger. Never raises."""
    if not state.goal_id:
        return
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_tasks import count_tasks_for_goal
        from pathly_orchestrator.supervisor import task_retry

        tasks = count_tasks_for_goal(get_db(), state.goal_id)
        attempts = task_retry.resolve_max_attempts()
        budget = tasks * attempts * (MAX_FEEDBACK_ROUNDS + 1)
        with _lock:
            previous = state.max_iterations
            if budget <= previous:
                return
            state.max_iterations = budget
        logger.info(
            "run budget: goal %s has %d tasks x %d attempts x %d rounds; "
            "max_iterations %d -> %d",
            state.goal_id,
            tasks,
            attempts,
            MAX_FEEDBACK_ROUNDS + 1,
            previous,
            budget,
        )
    except Exception:
        logger.warning(
            "run budget: could not size max_iterations for goal %s",
            state.goal_id,
            exc_info=True,
        )
