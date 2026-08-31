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

from . import task_retry as _task_retry

logger = logging.getLogger("pathly.scheduler")

# Sentinel pushed onto the completion queue to wake the main loop on abort.
_ABORT_SENTINEL = object()


def _outcome_is_failure(outcome) -> bool:
    """A worker's spawn returned normally, but its OUTCOME reports the task did not succeed — an
    explicit ``error``, the CLI's own ``is_error``/``api_error_status`` (e.g. a 404 that still exits
    0 with subtype "success"), a non-zero ``exit_code``, or an ``outcome``/``status`` flag of
    failed/error. Treated as a failure so a clean process exit over broken work is NOT marked done
    (silent-failure guard #2). Missing/empty signals default to success (back-compat with spawns
    that only return cost/session id)."""
    if not isinstance(outcome, dict):
        return False
    if (
        outcome.get("error")
        or outcome.get("is_error")
        or outcome.get("api_error_status")
    ):
        return True
    exit_code = outcome.get("exit_code")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    flag = str(outcome.get("outcome") or outcome.get("status") or "").lower()
    return flag in ("failed", "error", "failure")


def _post_task_status(conn, board: str, scope: str, text: str) -> None:
    """Post a GUARANTEED per-task progress status to the board from the SUPERVISOR.

    The loop supervisor owns claim/complete, so it — not the per-task agent — is the reliable source
    of started/done progress; there is no agent-side progress fragment (it would only duplicate this).
    The single executor gets the equivalent via the /comms/tasks handlers (_helpers.post_task_status).
    Best-effort: never raises, never blocks the drain."""
    try:
        from pathly_orchestrator.db.queries.comms import post_message

        post_message(
            conn,
            board=board,
            scope=scope,
            from_agent="supervisor",
            type="status",
            text=text,
        )
    except Exception:
        logger.debug("scheduler: _post_task_status failed", exc_info=True)


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
        get_ready_tasks,
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
    # Short task text kept per in-flight task so the supervisor can name it in the done/failed status it
    # posts at completion (the completion_q item carries only ids, not the text).
    task_texts: dict[str, str] = {}
    # attempts BEFORE this claim (claim_task increments the column before the worker runs) —
    # read at completion time to decide retry vs. escalate (task_retry.resolve_task_failure).
    task_attempts: dict[str, int] = {}

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
            # Stamp a concrete Pathly role so fragments that reference the agent's role
            # resolve to a recognized, full-tier value — notably code-query's `role`
            # field. A loop task agent otherwise has no role, so its code-query was
            # silently gated (the gate also now defaults unknown roles to a usable tier).
            instructions = (
                f"{_body}\n\n## Your task\n\n"
                "(Your Pathly role for this task is **builder** — use it wherever a "
                "fragment asks for your role, e.g. the code-query `role` field.)\n\n"
                f"{task_text}"
            )
        except Exception:
            instructions = task_text
        instructions += _task_retry.build_retry_context(task)
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
            prior_attempts = int(task.get("attempts") or 0)

            # run_id carries the ATTEMPT number (#N), not just the task_id: with retry
            # (task_retry.py) one task_id can spawn more than once, and run_id is the
            # identity the whole billing chain keys off (TERMINAL_SPAWN, the PTY result
            # callback, _reconciliation_window's async patch, agent_invocations.run_id).
            # A shared run_id across attempts let a LATE-arriving reconciliation for
            # attempt N fold its real cost onto attempt N+1's row instead of its own
            # (invocation_projection matches a BILLING_UPDATE to the MOST RECENT
            # AGENT_DONE sharing its run_id) — silently mis-billing retried tasks. "#" is
            # a safe separator: task_id is a uuid4 (hex + hyphens only).
            task_run_id = f"sched-{task_id}#{prior_attempts + 1}"
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
            # Guaranteed supervisor-side progress (not agent-dependent): Started on claim.
            task_texts[task_id] = task.get("text", "") or ""
            task_attempts[task_id] = prior_attempts
            _post_task_status(
                conn, board, scope, f"Started: {(task.get('text') or task_id)[:110]}"
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
                    outcome.get("error")
                    or outcome.get("outcome")
                    or "task reported failure"
                )[:500]
            current_attempt = task_attempts.pop(task_id, 0) + 1
            decision, blocked_ids = _task_retry.resolve_task_failure(
                conn,
                task_id,
                current_attempt,
                reason,
                board=board,
                scope=scope,
                goal_id=goal_id,
                text=task_texts.pop(task_id, ""),
                lane=lane,
                broadcast=lambda ev, pl: _broadcast(event_broadcast_fn, scope, ev, pl),
                post_status=lambda t: _post_task_status(conn, board, scope, t),
            )
            if decision == "escalated":
                result_failed.append(task_id)
                result_blocked.extend(blocked_ids)
        else:
            complete_task(conn, task_id)
            result_completed.append(task_id)
            _broadcast(
                event_broadcast_fn,
                scope,
                "task_done",
                {"task_id": task_id, "lane": lane, "text": task_texts.get(task_id, "")},
            )
            _post_task_status(
                conn,
                board,
                scope,
                f"Done: {(task_texts.pop(task_id, '') or task_id)[:110]}",
            )

        # Release the SAME workspace lease we acquired for this task.
        if ws is not None:
            try:
                isolation.release(ws, success=succeeded)
            except Exception:
                pass

    # ── Deadlock guard ──────────────────────────────────────────────────────────
    # After a NORMAL drain (not an abort), any task still 'pending' has an unsatisfiable
    # dependency (cycle, or a depends_on that will never complete) — get_ready_tasks
    # silently excludes it, so without this the loop would return a clean-looking result
    # while the work sits stuck forever. Extracted to task_retry.detect_deadlocks (Phase 1
    # universal deadlock detection) so any drain path with DB access can reuse it, not just
    # this loop.
    result_deadlocked: list[str] = []
    if not aborted:
        result_deadlocked = _task_retry.detect_deadlocks(conn, board, scope, goal_id)
        result_blocked.extend(result_deadlocked)
        if result_deadlocked:
            _broadcast(
                event_broadcast_fn,
                scope,
                "task_deadlocked",
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
