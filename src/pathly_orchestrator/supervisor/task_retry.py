"""Per-task retry/escalation + shared deadlock detection for the DAG scheduler.

``scheduler.py``'s frontier loop had no retry at all: ANY task failure (a worker
exception, or an outcome reporting failure — see ``_outcome_is_failure``) called
``fail_task()`` immediately — one bad attempt permanently failed the task and
cascade-blocked every transitive dependent. The ``attempts`` column (already
incremented by ``claim_task`` on every claim) was written but never read anywhere.

``resolve_task_failure`` is the one decision point ``scheduler.py``'s completion
handler calls on a failed task: retry (revert to ``pending`` so the frontier
re-schedules it, carrying the failure reason forward via the existing
``fail_reason`` column — read back by ``get_ready_tasks``' ``SELECT *``, so the
next attempt's prompt can show it, mirroring ``fsm_compose._retry_ladder_block``'s
"what varies by ATTEMPT" without inventing a second reason-storage field) or
escalate (permanent ``fail_task`` + a board escalation message, mirroring
``goal_verify.post_gate_failure_escalation``).

``detect_deadlocks`` is ``scheduler.py``'s former loop-only postscript, extracted
so any drain path with DB access can call it, not just ``scheduler_loop``.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Callable, Optional

logger = logging.getLogger("pathly.task_retry")

_DEFAULT_MAX_ATTEMPTS = 3


def resolve_max_attempts() -> int:
    """Read the ``goal.task_max_attempts`` app-setting. Absent/invalid/non-positive
    falls back to the default (3) — deliberately NOT fail-open to "no retry", since
    an unconfigured project should still get the safety net, not lose it."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), "goal.task_max_attempts", None)
    except Exception:
        return _DEFAULT_MAX_ATTEMPTS
    try:
        value = int(raw) if raw else None
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ATTEMPTS
    return value if value and value > 0 else _DEFAULT_MAX_ATTEMPTS


def retry_task(conn: sqlite3.Connection, task_id: str, reason: str) -> None:
    """Revert a failed task back to 'pending' so the scheduler's frontier re-schedules
    it, stamping ``reason`` into ``fail_reason`` (reused as "most recent attempt's
    failure" — no new column). Does NOT touch dependents, unlike ``fail_task``: the
    task is not failed yet, so its dependents' readiness must not change."""
    from pathly_orchestrator.db.connection import _get_write_lock

    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET task_status='pending', claimed_by=NULL, "
            "fail_reason=? WHERE id=?",
            (reason[:500], task_id),
        )
        conn.commit()


def build_retry_context(task: dict) -> str:
    """A retry-ladder block for a task's prompt, mirroring
    ``fsm_compose._retry_ladder_block``: only appended from the SECOND attempt on
    (``task["attempts"]`` is the count BEFORE this claim — 0 on a task's first
    attempt), so a first attempt's prompt is byte-identical to before this feature.
    """
    prior_attempts = int(task.get("attempts") or 0)
    reason = task.get("fail_reason")
    if prior_attempts <= 0 or not reason:
        return ""
    return (
        f"\n\n## Retry attempt {prior_attempts + 1} — the previous attempt failed\n\n"
        "What was tried before did not satisfy this task. Read the failure below "
        "before deciding what to change — repeating the same approach will fail "
        f"the same way.\n\n```\n{str(reason)[:2000]}\n```\n"
    )


def resolve_task_failure(
    conn: sqlite3.Connection,
    task_id: str,
    current_attempt: int,
    reason: str,
    *,
    board: str,
    scope: str,
    goal_id: str | None,
    text: str,
    lane: str,
    broadcast: Optional[Callable[[str, dict], None]] = None,
    post_status: Optional[Callable[[str], None]] = None,
    max_attempts: int | None = None,
) -> tuple[str, list[str]]:
    """Decide retry vs. escalate for a failed task and perform the FULL side-effect
    set for whichever branch is chosen — DB write, board broadcast, status post, and
    (on escalate) the ``fail_task`` cascade — so the caller (``scheduler.py``) only
    needs the returned ``(decision, blocked_ids)`` to update its own result lists.

    ``current_attempt`` is the attempt that just failed (1-based — the caller passes
    the pre-claim ``attempts`` value + 1, since ``claim_task`` increments the column
    before the worker runs). ``broadcast``/``post_status`` mirror
    ``scheduler.py``'s own ``_broadcast``/``_post_task_status`` shapes (event/payload
    and text respectively) — optional so this stays testable without a live board.
    """
    limit = max_attempts if max_attempts is not None else resolve_max_attempts()
    if current_attempt < limit:
        retry_task(conn, task_id, reason)
        logger.info(
            "task_retry: retrying task %s (attempt %d/%d): %s",
            task_id,
            current_attempt,
            limit,
            reason[:200],
        )
        if broadcast:
            broadcast(
                "task_retry",
                {
                    "task_id": task_id,
                    "lane": lane,
                    "reason": reason,
                    "attempt": current_attempt,
                },
            )
        if post_status:
            post_status(
                f"Retrying ({current_attempt}): {(text or task_id)[:90]} — {reason[:60]}"
            )
        return "retried", []

    from pathly_orchestrator.db.queries.comms import fail_task

    blocked_ids = fail_task(conn, task_id, reason=reason)
    logger.warning("task_retry: task %s failed permanently: %s", task_id, reason)
    if broadcast:
        broadcast(
            "task_failed",
            {
                "task_id": task_id,
                "lane": lane,
                "reason": reason,
                "blocked": blocked_ids,
                "text": text,
            },
        )
    if post_status:
        post_status(f"Failed: {(text or task_id)[:80]} — {reason[:80]}")
    _post_escalation(board, scope, goal_id, task_id, text, reason, current_attempt)
    return "escalated", blocked_ids


def _post_escalation(
    board: str,
    scope: str,
    goal_id: str | None,
    task_id: str,
    text: str,
    reason: str,
    attempts: int,
) -> None:
    """Board escalation once a task exhausts its retries — best-effort, never raises."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import post_message

        post_message(
            get_db(),
            board=board,
            scope=scope,
            from_agent="supervisor",
            type="escalation",
            text=(
                f"Task failed after {attempts} attempt(s), no retries left:\n\n"
                f"{(text or task_id)[:200]}\n\n{reason[:1500]}"
            ),
            goal_id=goal_id or None,
        )
    except Exception:
        logger.debug("task_retry: escalation post failed", exc_info=True)


def detect_deadlocks(
    conn: sqlite3.Connection, board: str, scope: str, goal_id: str | None = None
) -> list[str]:
    """Mark every still-``pending`` task as ``blocked`` (unsatisfiable dependency —
    a cycle, or a ``depends_on`` that will never complete) and return their ids.

    Call this ONLY after a normal drain (nothing left ready, nothing in flight) —
    ``get_ready_tasks`` silently excludes a task with unmet deps, so without this a
    drain can return a clean-looking result while work sits stuck forever. Shared by
    every drain path with DB access; ``scheduler_loop`` was the first and only
    caller until this extraction.
    """
    from pathly_orchestrator.db.queries.comms import get_tasks

    deadlocked: list[str] = []
    for row in get_tasks(conn, board, scope, task_status="pending", goal_id=goal_id):
        tid = row["id"]
        conn.execute(
            "UPDATE comms_messages SET task_status='blocked', fail_reason=? WHERE id=?",
            ("deadlocked: unsatisfiable dependency (cycle or missing depends_on)", tid),
        )
        deadlocked.append(tid)
    if deadlocked:
        conn.commit()
        logger.warning(
            "task_retry: %d task(s) DEADLOCKED in %s/%s (unsatisfiable deps): %s",
            len(deadlocked),
            board,
            scope,
            deadlocked,
        )
    return deadlocked
