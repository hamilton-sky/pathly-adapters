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


def scheduler_loop(
    state,
    board: str,
    scope: str,
    *,
    isolation,
    broadcast_fn: Optional[Callable] = None,
    spawn_fn: Optional[Callable] = None,
    abort_check: Optional[Callable[[], bool]] = None,
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
        Optional SSE broadcast callable: broadcast_fn(event_type: str, payload: dict).
        Called best-effort; exceptions are swallowed.
    spawn_fn:
        Callable(state, instructions, adapter, model, run_id, broadcast_fn) -> dict.
        Defaults to supervisor.terminal._run_stage_via_terminal (lazy import) when None.
        In tests, inject a fake that records timestamps and returns immediately.
    abort_check:
        Optional callable() -> bool. If it returns True the loop exits early.

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
        reclaim_stale_claims,
    )

    if spawn_fn is None:
        from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal as _default_spawn
        spawn_fn = _default_spawn

    conn = get_db()

    # 1. Reclaim any orphaned in_progress tasks from a previous crashed run.
    reclaimed = reclaim_stale_claims(conn, board, scope)
    if reclaimed:
        logger.info("scheduler: reclaimed %d stale claims for %s/%s", len(reclaimed), board, scope)

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

    def _worker(task: dict, task_run_id: str, ws) -> None:
        """Run in a daemon thread. Calls spawn_fn and pushes result onto completion_q."""
        task_id = task["id"]
        instructions = task.get("text", "")
        adapter = task.get("adapter") or (state.current_adapter if hasattr(state, "current_adapter") else "")
        model = task.get("model") or (state.model if hasattr(state, "model") else "")

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
            logger.info("scheduler: abort signalled, exiting loop for %s/%s", board, scope)
            break

        ready = get_ready_tasks(conn, boards=[board], scopes=[scope])

        # Determine which ready tasks can be scheduled now.
        ready_lanes = {t.get("lane") or t["id"] for t in ready}
        max_workers = isolation.max_concurrency(ready_lanes)
        capacity = max_workers - in_flight_count

        schedulable = [
            t for t in ready
            if (t.get("lane") or t["id"]) not in in_flight_lanes
        ][:max(0, capacity)]

        for task in schedulable:
            task_id = task["id"]
            lane = task.get("lane") or task_id

            task_run_id = f"sched-{task_id}"
            won = claim_task(conn, task_id, run_id=task_run_id)
            if not won:
                # Another scheduler instance (or a race) claimed it first.
                continue

            _broadcast(broadcast_fn, "TASK_CLAIMED", {"task_id": task_id, "lane": lane, "board": board, "scope": scope})

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
            logger.warning("scheduler: 5-minute timeout waiting for worker, checking abort")
            continue

        if item is _ABORT_SENTINEL:
            break

        task_id, lane, _outcome, exc = item
        in_flight_count -= 1
        in_flight_lanes.discard(lane)
        ws = workspaces.pop(task_id, None)

        succeeded = exc is None
        if not succeeded:
            reason = str(exc)[:500]
            logger.warning("scheduler: task %s failed: %s", task_id, reason)
            blocked_ids = fail_task(conn, task_id, reason=reason)
            result_failed.append(task_id)
            result_blocked.extend(blocked_ids)
            _broadcast(broadcast_fn, "TASK_FAILED", {"task_id": task_id, "lane": lane, "reason": reason, "blocked": blocked_ids})
        else:
            complete_task(conn, task_id)
            result_completed.append(task_id)
            _broadcast(broadcast_fn, "TASK_DONE", {"task_id": task_id, "lane": lane})

        # Release the SAME workspace lease we acquired for this task.
        if ws is not None:
            try:
                isolation.release(ws, success=succeeded)
            except Exception:
                pass

    return {
        "completed": result_completed,
        "failed": result_failed,
        "blocked": result_blocked,
    }


def _broadcast(broadcast_fn: Optional[Callable], event_type: str, payload: dict) -> None:
    """Call broadcast_fn best-effort; never raise."""
    if broadcast_fn is None:
        return
    try:
        broadcast_fn(event_type, payload)
    except Exception:
        pass
