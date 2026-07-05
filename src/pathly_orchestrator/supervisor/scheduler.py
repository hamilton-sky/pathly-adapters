"""DAG task scheduler for the Pathly supervisor.

Implements the frontier-driven parallel execution loop described in:
  pathly/plans/comms-board/DAG-SCHEDULER-ARCHITECTURE.md §1.2, §1.3, §2

Phase 2a: fully testable in isolation via dependency injection.
NOT wired into orchestrator.py or api.py yet (that is a later step).

Design principles:
- Board is authoritative: DB rows are the single source of truth.
- Event-driven: blocks on completion_q.get(); no busy-wait or sleep-poll.
- Lane partition: at most one worker per lane at any time.
- Pluggable isolation: Isolation impl (LaneIsolation or future WorktreeIsolation)
  supplies the TaskWorkspace; scheduler code is identical for both.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger("pathly.scheduler")

# Sentinel pushed onto the completion queue to wake the main loop on abort.
_ABORT_SENTINEL = object()


def _outcome_is_failure(outcome) -> bool:
    """A worker's spawn returned normally, but its OUTCOME reports the task did not succeed — an
    explicit ``error``, a non-zero ``exit_code``, or an ``outcome``/``status`` flag of failed/error.
    Treated as a failure so a clean process exit over broken work is NOT marked done (silent-failure
    guard #2). Missing/empty signals default to success (back-compat with spawns that only return
    cost/session id)."""
    if not isinstance(outcome, dict):
        return False
    if outcome.get("error"):
        return True
    exit_code = outcome.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    flag = str(outcome.get("outcome") or outcome.get("status") or "").lower()
    return flag in ("failed", "error", "failure")


def scheduler_loop(
    state,
    board: str,
    scope: str,
    *,
    isolation,
    broadcast_fn: Optional[Callable] = None,
    spawn_fn: Optional[Callable] = None,
    abort_check: Optional[Callable[[], bool]] = None,
    goal_id: Optional[str] = None,
    event_broadcast_fn: Optional[Callable] = None,
) -> dict:
    """Run the DAG frontier loop until all tasks are done, failed/blocked, or aborted.

    Parameters
    ----------
    state:
        RunnerState (or any object with .project_root / .db_path / .fsm_port).
        Used only to populate TaskWorkspace via isolation.acquire().
    board:
        The board name to query (e.g. "feature").
    scope:
        The scope to query (e.g. the feature/topic name).
    isolation:
        An Isolation impl (LaneIsolation). Provides acquire()/release()/max_concurrency().
    broadcast_fn:
        Optional SSE callable forwarded UNCHANGED to each worker's
        _run_stage_via_terminal, which calls it as broadcast_fn(topic, payload)
        on the RUNNER stream (TERMINAL_SPAWN etc.). Called best-effort.
    spawn_fn:
        Callable(state, instructions, adapter, model, run_id, broadcast_fn) -> dict.
        Defaults to supervisor.terminal._run_stage_via_terminal (lazy import) when None.
        In tests, inject a fake that records timestamps and returns immediately.
    abort_check:
        Optional callable() -> bool. If it returns True the loop exits early.
    goal_id:
        When given, the frontier is scoped to this goal's tasks only (passed to
        get_ready_tasks). The Phase-1 dispatcher uses this so a goal's loop drains
        only its own DAG. None = board+scope behavior (every task in the scope).
    event_broadcast_fn:
        Optional SSE callable for the scheduler's OWN task-state events, called as
        event_broadcast_fn(scope, payload) on the COMMS stream — a DIFFERENT channel
        than broadcast_fn (which feeds the worker's runner-stream terminals). None =
        no task-state broadcasts (correctness is unaffected; this is board UI only).

    Returns
    -------
    dict with keys:
        "completed": list of task IDs that reached done.
        "failed":    list of task IDs that failed.
        "blocked":   list of task IDs that became blocked due to upstream failure.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import (
        claim_task,
        complete_task,
        fail_task,
        get_ready_tasks,
        get_tasks,
        reclaim_stale_claims,
    )

    if spawn_fn is None:
        from pathly_orchestrator.supervisor.terminal import (
            _run_stage_via_terminal as _default_spawn,
        )

        spawn_fn = _default_spawn

    conn = get_db()

    # 1. Reclaim any orphaned in_progress tasks from a previous crashed run.
    reclaimed = reclaim_stale_claims(conn, board, scope)
    if reclaimed:
        logger.info(
            "scheduler: reclaimed %d stale claims for %s/%s",
            len(reclaimed),
            board,
            scope,
        )

    completion_q: queue.Queue = queue.Queue()
    in_flight_lanes: set[str] = set()
    in_flight_count = 0
    # Track the TaskWorkspace acquired for each in-flight task so we release the
    # SAME lease on completion. Re-acquiring would create a phantom workspace
    # (a no-op for LaneIsolation, but it would leak a real worktree under P3).
    workspaces: dict[str, Any] = {}

    result_completed: list[str] = []
    result_failed: list[str] = []
    result_blocked: list[str] = []
    aborted = False

    def _worker(task: dict, task_run_id: str, ws) -> None:
        """Run in a daemon thread. Calls spawn_fn and pushes result onto completion_q."""
        task_id = task["id"]
        task_text = task.get("text", "")
        adapter = task.get("adapter") or (
            state.current_adapter if hasattr(state, "current_adapter") else ""
        )
        model = task.get("model") or (state.model if hasattr(state, "model") else "")
        # Compose the loop task agent through the SAME fragment layer the FSM/team path
        # uses (progress-logging + comms-post + completion-report, via the execute-task
        # manifest entry) so it narrates progress, posts findings, and writes AGENT_DONE —
        # instead of running blind on the raw task text. Best-effort: fall back to the raw
        # task text if composition is unavailable.
        try:
            from pathly_orchestrator.skills.compose import compose_skill

            _body = compose_skill("development/execute-task", adapter or "claude")
            instructions = f"{_body}\n\n## Your task\n\n{task_text}"
        except Exception:
            instructions = task_text
        # Inject the same scope-aware board context (governance + memory, honoring
        # the Reads toggle) the FSM/team path gets, so loop-executor tasks aren't
        # blind to the board. Best-effort — never block a task on context.
        try:
            from pathly_orchestrator.runner.comms_context import board_context_for

            _ctx = board_context_for(
                board,
                scope,
                getattr(state, "project_root", "") or "",
                task_text,
                task_id=task_id,
            )
            if _ctx:
                instructions = f"{instructions}\n\n{_ctx}"
        except Exception:
            pass

        try:
            outcome = spawn_fn(
                state,
                instructions,
                adapter,
                model,
                task_run_id,
                broadcast_fn,
            )
            if outcome is None:
                outcome = {}
            completion_q.put((task_id, task.get("lane") or task_id, outcome, None))
        except Exception as exc:
            completion_q.put((task_id, task.get("lane") or task_id, {}, exc))

    while True:
        # Abort check.
        if abort_check and abort_check():
            logger.info(
                "scheduler: abort signalled, exiting loop for %s/%s", board, scope
            )
            aborted = True
            break

        ready = get_ready_tasks(conn, boards=[board], scopes=[scope], goal_id=goal_id)

        # Determine which ready tasks can be scheduled now.
        ready_lanes = {t.get("lane") or t["id"] for t in ready}
        max_workers = isolation.max_concurrency(ready_lanes)
        capacity = max_workers - in_flight_count

        schedulable = [
            t for t in ready if (t.get("lane") or t["id"]) not in in_flight_lanes
        ][: max(0, capacity)]

        for task in schedulable:
            task_id = task["id"]
            lane = task.get("lane") or task_id

            task_run_id = f"sched-{task_id}"
            won = claim_task(conn, task_id, run_id=task_run_id)
            if not won:
                # Another scheduler instance (or a race) claimed it first.
                continue

            _broadcast(
                event_broadcast_fn,
                scope,
                "task_claimed",
                {"task_id": task_id, "lane": lane, "board": board},
            )

            ws = isolation.acquire(task, state)
            workspaces[task_id] = ws
            in_flight_lanes.add(lane)
            in_flight_count += 1

            t = threading.Thread(
                target=_worker,
                args=(task, task_run_id, ws),
                daemon=True,
                name=f"sched-worker-{task_id[:8]}",
            )
            t.start()

        # Termination: nothing schedulable AND nothing in flight AND frontier empty.
        if not schedulable and in_flight_count == 0 and not ready:
            break

        # If nothing is in flight and nothing was schedulable, we may be stuck
        # (e.g. all remaining tasks are in_progress from a race, or truly empty).
        # Still block on queue to catch any in-flight completions.
        if in_flight_count == 0:
            # Nothing in flight and nothing to schedule — we are done.
            break

        # Block until any worker finishes.
        try:
            item = completion_q.get(timeout=300)
        except queue.Empty:
            logger.warning(
                "scheduler: 5-minute timeout waiting for worker, checking abort"
            )
            continue

        if item is _ABORT_SENTINEL:
            aborted = True
            break

        task_id, lane, outcome, exc = item
        in_flight_count -= 1
        in_flight_lanes.discard(lane)
        ws = workspaces.pop(task_id, None)

        # Success requires BOTH: the worker did not raise AND its outcome does not report failure.
        # (silent-failure guard #2 — a clean process exit over broken work is not "done".)
        succeeded = exc is None and not _outcome_is_failure(outcome)
        if not succeeded:
            if exc is not None:
                reason = str(exc)[:500]
            else:
                reason = str(
                    outcome.get("error") or outcome.get("outcome") or "task reported failure"
                )[:500]
            logger.warning("scheduler: task %s failed: %s", task_id, reason)
            blocked_ids = fail_task(conn, task_id, reason=reason)
            result_failed.append(task_id)
            result_blocked.extend(blocked_ids)
            _broadcast(
                event_broadcast_fn,
                scope,
                "task_failed",
                {
                    "task_id": task_id,
                    "lane": lane,
                    "reason": reason,
                    "blocked": blocked_ids,
                },
            )
        else:
            complete_task(conn, task_id)
            result_completed.append(task_id)
            _broadcast(
                event_broadcast_fn,
                scope,
                "task_done",
                {"task_id": task_id, "lane": lane},
            )

        # Release the SAME workspace lease we acquired for this task.
        if ws is not None:
            try:
                isolation.release(ws, success=succeeded)
            except Exception:
                pass

    # ── Deadlock guard ──────────────────────────────────────────────────────────
    # After a NORMAL drain (not an abort), any task still 'pending' has an unsatisfiable
    # dependency — a cycle, or a depends_on that will never complete. get_ready_tasks
    # silently excludes such tasks (unmet deps), so without this the loop returns a
    # clean-looking result while the work sits stuck forever. Surface it LOUDLY: mark
    # each blocked with a reason, report it, and warn.
    result_deadlocked: list[str] = []
    if not aborted:
        for row in get_tasks(conn, board, scope, task_status="pending", goal_id=goal_id):
            tid = row["id"]
            conn.execute(
                "UPDATE comms_messages SET task_status='blocked', fail_reason=? WHERE id=?",
                ("deadlocked: unsatisfiable dependency (cycle or missing depends_on)", tid),
            )
            result_deadlocked.append(tid)
            result_blocked.append(tid)
        if result_deadlocked:
            conn.commit()
            logger.warning(
                "scheduler: %d task(s) DEADLOCKED in %s/%s (unsatisfiable deps): %s",
                len(result_deadlocked), board, scope, result_deadlocked,
            )
            _broadcast(
                event_broadcast_fn, scope, "task_deadlocked",
                {"tasks": result_deadlocked, "board": board},
            )

    return {
        "completed": result_completed,
        "failed": result_failed,
        "blocked": result_blocked,
        "deadlocked": result_deadlocked,
    }


def _broadcast(
    broadcast_fn: Optional[Callable], scope: str, event: str, payload: dict
) -> None:
    """Emit a scheduler task-state event on the COMMS stream, best-effort.

    Wraps the payload as a COMMS_UPDATE so Studio's board (which already listens
    for task_unblocked/task_failed) picks up task_claimed/task_done/task_failed
    with no new event channel. Signature mirrors the comms broadcast helpers:
    broadcast_fn(scope, payload). Never raises."""
    if broadcast_fn is None:
        return
    try:
        broadcast_fn(scope, {"type": "COMMS_UPDATE", "event": event, **payload})
    except Exception:
        pass
