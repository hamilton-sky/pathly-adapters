"""Board-DAG completeness gate — ``require_tasks_done``.

Goal-scoped when a ``goal_id`` is present (goal executor); else feature-scoped across the
whole ``(board, scope)`` — the linear team pipeline has no single goal_id. Skipped when
neither is set.
"""

from __future__ import annotations

from pathlib import Path

from ._helpers import gate_failed


def _count_incomplete(
    goal_id: str | None, feature_scope: str | None, board: str
) -> int:
    try:
        from pathly_orchestrator.db.connection import get_db

        if goal_id:
            from pathly_orchestrator.db.queries.comms_tasks import (
                count_incomplete_tasks_for_goal,
            )

            return count_incomplete_tasks_for_goal(get_db(), goal_id)
        if feature_scope:
            from pathly_orchestrator.db.queries.comms_tasks import (
                count_incomplete_tasks_for_scope,
            )

            return count_incomplete_tasks_for_scope(
                get_db(), board or "feature", feature_scope
            )
    except Exception:
        return 0  # DB read error → fail-open (never wedge on a read hiccup)
    return 0


def check_require_tasks_done(
    gate: dict,
    storage_path: Path,
    prev_state: str,
    next_state: str,
    goal_id: str | None = None,
    feature_scope: str | None = None,
    board: str = "feature",
    **_: object,
) -> dict | None:
    incomplete = _count_incomplete(goal_id, feature_scope, board)
    if incomplete <= 0:
        return None
    reason = (
        f"{incomplete} task(s) are not done — the flow cannot advance while tasks "
        f"remain unfinished or failed. Build/repair the remaining tasks (they are on "
        f"the board's DAG), then the flow can advance."
    )
    return gate_failed(
        storage_path, gate, "require_tasks_done", prev_state, next_state, reason
    )
