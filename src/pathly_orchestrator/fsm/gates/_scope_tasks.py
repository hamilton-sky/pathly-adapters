"""The board half of ``scope_gate``'s declared scope: the ``files`` of the planned tasks.

A task claimed since ``build_baseline.started_at`` declares its ``files`` only when it was
posted before that stamp (its server-stamped ``ts``) and not by a builder (its stamped
``author_role``). So a builder cannot widen its own scope by posting a task and claiming it, in
this build or for a later one. ``db`` is imported lazily, as in the other gates.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("pathly.gates.scope")


def _task_files(task: dict) -> set[str]:
    """A task row's declared ``files`` (a JSON list), or nothing when absent or malformed."""
    try:
        parsed = json.loads(task.get("files") or "[]")
    except (TypeError, ValueError):
        return set()
    if not isinstance(parsed, list):
        return set()
    return {str(f).strip() for f in parsed if str(f).strip()}


def claimed_files(
    since: str | None, goal_id: str | None, feature_scope: str | None, board: str
) -> set[str] | None:
    """The ``files`` of the planned tasks claimed since ``since``; None when unreadable.

    Goal-scoped when ``goal_id`` is set, else ``(board, feature_scope)``
    (``task_proof.tasks_claimed_since``). Nothing without ``since`` or a scope.
    """
    if not since or not (goal_id or feature_scope):
        return set()
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import (
            instant,
            tasks_claimed_since,
        )

        tasks = tasks_claimed_since(
            get_db(), board or "feature", feature_scope or "", goal_id, since
        )
    except Exception:
        logger.warning("scope_gate could not read the claimed tasks", exc_info=True)
        return None
    start = instant(since)
    files: set[str] = set()
    for task in tasks:
        posted = instant(task.get("ts"))
        by_builder = str(task.get("author_role") or "").strip().lower() == "builder"
        if start and posted and posted <= start and not by_builder:
            files |= _task_files(task)
    return files
