"""Goal execution strategies: single, loop, and team executors."""

from __future__ import annotations

import threading
import uuid
from typing import Callable, Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"
_TEAM_FLOW = "team-build"


def _safe_call(fn: Optional[Callable], *args) -> None:
    """Invoke a lifecycle callback best-effort; a bad callback never breaks a run."""
    if fn is None:
        return
    try:
        fn(*args)
    except Exception:
        pass


def _reset_fsm_state_for_flow(flow_name: str, scope: str, project_root: str) -> None:
    """Re-seed a topic's persisted FSM state to *flow*'s initial state when it is stale.

    FSM state is keyed by TOPIC (the on-disk slug), NOT by flow — so a topic that previously
    ran any flow to ``DONE`` (or ran a *different* flow, leaving a ``current`` this flow does
    not declare) breaks a fresh FSM-driven run two ways:
      • ``current == "DONE"`` → ``next_action`` short-circuits to ``{done: True}`` and the loop
        exits having spawned ZERO stages — the "run started but no terminal opened" symptom.
      • ``current`` is a foreign state (e.g. team's ``BUILDING`` under the ``consultation`` flow)
        → ``agent_map[current]`` raises ``KeyError`` and the run errors.
    Before (re)launching an FSM flow from the goal layer we re-seed ``states[0]`` in exactly
    those two cases; a valid non-terminal state for *this* flow is left so it can resume.

    We write the raw row via ``eventlog._write_state_db`` (not ``write_state``) because
    ``write_state`` enforces transition validity and would reject ``DONE → <initial>``.
    Best-effort: callers already refuse when a run is actively running/paused/awaiting, so we
    only ever reset a finished/foreign/errored state — never a live one. Any failure is logged
    and swallowed so a reset hiccup never blocks the run.
    """
    try:
        from pathlib import Path

        from pathly_orchestrator import eventlog
        from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path

        flow_cfg = _load_flow(flow_name, project_root or None) or {}
        states = flow_cfg.get("states") or []
        if not states:
            return
        storage_path = _resolve_storage_path(flow_cfg, project_root or "", scope)
        cur = (eventlog.read_state(str(storage_path)) or {}).get("current")
        if cur is None:
            return  # no prior state — next_action defaults to states[0]
        if cur in states and cur != "DONE":
            return  # valid, non-terminal state for THIS flow — let it resume
        feature_dir = Path(str(storage_path))
        eventlog._write_state_db(feature_dir, feature_dir.name, {"current": states[0]})
    except Exception:
        import logging

        logging.getLogger(__name__).debug(
            "_reset_fsm_state_for_flow(%s, %s) failed", flow_name, scope, exc_info=True
        )


def start_goal_run(
    goal_id: str,
    *,
    executor_override: str | None = None,
    flow_override: str | None = None,
    project_root: str = "",
    adapter: str = "claude",
    model: str = "",
    progress: str = "normal",
    broadcast_fn: Optional[Callable] = None,
    event_broadcast_fn: Optional[Callable] = None,
    on_start: Optional[Callable] = None,
    on_done: Optional[Callable] = None,
    spawn_fn: Optional[Callable] = None,
    start_fn: Optional[Callable] = None,
    block: bool = False,
) -> dict:
    """Read the goal's executor and dispatch its DAG.

    Returns a dict with `ok` and, on failure, a `reason` the HTTP layer maps to a
    status code (not_found→404, not_goal→400, board_busy→409, not_implemented→501).
    executor_override wins over the goal's stored executor and is persisted back.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import set_goal_executor

    conn = get_db()
    row = conn.execute(
        "SELECT id, board, scope, text, type, executor FROM comms_messages "
        "WHERE id=? AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    if row is None:
        return {"ok": False, "reason": "not_found", "error": f"goal {goal_id!r} not found"}
    if (row["type"] or "") != "goal":
        return {
            "ok": False,
            "reason": "not_goal",
            "error": f"message {goal_id!r} is type={row['type']!r}, not 'goal'",
        }

    board = row["board"] or "feature"
    scope = row["scope"] or ""
    goal_text = row["text"] or ""
    if executor_override and executor_override.strip():
        executor = executor_override.strip().lower()
        if executor != (row["executor"] or ""):
            set_goal_executor(conn, goal_id, executor)
    else:
        executor = (row["executor"] or "single").strip().lower()

    if executor == "single":
        return _run_single(
            goal_id, board, scope, goal_text,
            project_root=project_root, adapter=adapter, model=model, progress=progress,
            broadcast_fn=broadcast_fn, on_start=on_start, on_done=on_done,
            spawn_fn=spawn_fn, block=block,
        )
    if executor == "loop":
        return _run_loop(
            goal_id, board, scope,
            project_root=project_root, adapter=adapter, model=model,
            broadcast_fn=broadcast_fn, event_broadcast_fn=event_broadcast_fn,
            on_start=on_start, on_done=on_done, spawn_fn=spawn_fn, block=block,
        )
    if executor == "team":
        return _run_team(
            goal_id, board, scope,
            flow=(flow_override or _TEAM_FLOW),
            project_root=project_root, adapter=adapter, model=model,
            broadcast_fn=broadcast_fn, on_start=on_start, on_done=on_done,
            start_fn=start_fn,
        )
    return {
        "ok": False,
        "reason": "unknown_executor",
        "error": f"unknown executor {executor!r} (expected single|loop|team)",
    }


def _run_single(
    goal_id: str,
    board: str,
    scope: str,
    goal_text: str,
    *,
    project_root: str,
    adapter: str,
    model: str,
    progress: str,
    broadcast_fn,
    on_start,
    on_done,
    spawn_fn,
    block: bool,
) -> dict:
    """ONE agent drains the whole goal via start_board_run + drain-dag skill."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    instructions = (
        f"Drain the task-DAG for goal_id={goal_id!r} on the '{board}' board, "
        f"scope '{scope}'. Pass goal_id={goal_id!r} as the goal_id query param when "
        f"polling ready tasks so you run only THIS goal's tasks."
        + (f"\n\nGoal: {goal_text}" if goal_text else "")
    )
    result = start_board_run(
        board, scope, "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill="development/drain-dag",
        progress=progress,
        broadcast_fn=broadcast_fn,
        on_start=on_start,
        on_done=on_done,
        spawn_fn=spawn_fn,
        block=block,
    )
    if isinstance(result, dict) and result.get("ok"):
        result["executor"] = "single"
        result["goal_id"] = goal_id
    return result


def _run_loop(
    goal_id: str,
    board: str,
    scope: str,
    *,
    project_root: str,
    adapter: str,
    model: str,
    broadcast_fn,
    event_broadcast_fn,
    on_start,
    on_done,
    spawn_fn,
    block: bool,
) -> dict:
    """Supervisor owns the frontier via scheduler_loop (SerialIsolation), scoped to goal."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop
    from pathly_orchestrator.supervisor.state import RunnerState

    run_id = str(uuid.uuid4())
    if not board_lock.acquire(board, scope, run_id):
        return {
            "ok": False,
            "reason": "board_busy",
            "error": "board is busy",
            "holder": board_lock.holder(board, scope),
        }

    slug = scope  # fallback
    if project_root and goal_id:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.supervisor.slug import ensure_goal_slug
            import os
            slug = ensure_goal_slug(get_db(project_root or None), goal_id)
            _goal_dir = os.path.join(project_root, "pathly", "goals", slug)
            os.makedirs(_goal_dir, exist_ok=True)
        except Exception:
            pass

    state = RunnerState(
        topic=slug,
        flow="goal-loop",
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        timeout=600,
        run_id=run_id,
        current_adapter=adapter or "claude",
    )
    # telemetry-three-tier: the loop owns its telemetry (no registry RunnerState →
    # api_lifecycle won't write it). Tag every task with the board's scope_tier and
    # thread each task's span under one goal trace (goal=trace, task=span).
    from pathly_orchestrator.runner.telemetry import (
        new_span_id,
        new_trace_id,
        scope_tier_for,
        write_goal_root_span,
    )

    state.executor_owned_telemetry = True
    state.scope_tier = scope_tier_for(board)
    state.goal_trace_id = new_trace_id()
    state.goal_span_id = new_span_id()
    write_goal_root_span(
        project_root=project_root,
        feature=scope,
        goal_id=goal_id,
        trace_id=state.goal_trace_id,
        span_id=state.goal_span_id,
        scope_tier=state.scope_tier,
        executor="loop",
    )
    isolation = SerialIsolation()

    def _abort_check() -> bool:
        return board_lock.holder(board, scope) != run_id

    def _work() -> dict:
        try:
            _safe_call(on_start, run_id)
            kwargs: dict = dict(
                isolation=isolation,
                broadcast_fn=broadcast_fn,
                event_broadcast_fn=event_broadcast_fn,
                goal_id=goal_id,
                abort_check=_abort_check,
            )
            if spawn_fn is not None:
                kwargs["spawn_fn"] = spawn_fn
            raw = scheduler_loop(state, board, scope, **kwargs)
            res: dict = dict(raw) if isinstance(raw, dict) else {"result": raw}
            res["executor"] = "loop"
            res["goal_id"] = goal_id
            res["run_id"] = run_id
            _safe_call(on_done, run_id, res)
            return res
        finally:
            board_lock.release(board, scope, run_id)

    if block:
        return {"ok": True, "run_id": run_id, "executor": "loop", "result": _work()}

    def _runner() -> None:
        try:
            _work()
        except Exception as exc:
            _safe_call(on_done, run_id, {"result": f"error: {exc}", "error": str(exc)})

    threading.Thread(
        target=_runner, daemon=True, name=f"goal-loop-{run_id[:8]}"
    ).start()
    return {"ok": True, "run_id": run_id, "executor": "loop", "status": "started"}


def _run_team(
    goal_id: str,
    board: str,
    scope: str,
    *,
    flow: str = _TEAM_FLOW,
    project_root: str,
    adapter: str,
    model: str,
    broadcast_fn,
    on_start,
    on_done,
    start_fn,
) -> dict:
    """Run an FSM flow (default team-build) on the goal's scope via start_run."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.registry import get_state

    if board_lock.holder(board, scope) is not None:
        return {"ok": False, "reason": "board_busy", "error": "board is busy (a run holds the lock)"}
    existing = get_state(scope)
    if existing is not None and existing.status in ("running", "paused", "awaiting_decision"):
        return {
            "ok": False,
            "reason": "board_busy",
            "error": f"a pipeline run is already active for {scope!r} (status={existing.status})",
        }

    # Slug: stable on-disk topic under pathly/goals/<slug>
    slug = scope  # fallback
    if project_root and goal_id:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.supervisor.slug import ensure_goal_slug
            import os
            slug = ensure_goal_slug(get_db(project_root or None), goal_id)
            _goal_dir = os.path.join(project_root, "pathly", "goals", slug)
            os.makedirs(_goal_dir, exist_ok=True)
        except Exception:
            pass

    if start_fn is None:
        try:
            from pathly_orchestrator.fsm_ops import _load_flow
            _load_flow(flow, project_root or None)
        except Exception:
            return {
                "ok": False,
                "reason": "unknown_flow",
                "error": f"flow {flow!r} not found (run any seeded flow: team-build, debug, quick-fix, …)",
            }

    _start = start_fn
    if _start is None:
        from pathly_orchestrator.supervisor.api import start_run as _start
        # Only re-seed when driving the REAL FSM — a test start_fn owns its own state.
        _reset_fsm_state_for_flow(flow, slug, project_root)

    try:
        state = _start(
            topic=slug,
            flow=flow,
            project_root=project_root or "",
            model=model or _DEFAULT_MODEL,
            broadcast_fn=broadcast_fn,
            # Goal executors are headless one-shots per stage — never the interactive REPL
            # path (which start_run defaults to). interactive=True would spawn a bare REPL
            # and hang waiting on prompt injection. Mirror _decompose_consultation.
            interactive=False,
            # Carry the goal context and fire the lifecycle on_done on terminal status so
            # the goal-run indicator clears even when the FSM flow ends in error.
            goal_id=goal_id,
            on_done=on_done,
        )
    except ValueError as exc:
        return {"ok": False, "reason": "board_busy", "error": str(exc)}

    run_id = getattr(state, "run_id", "") or ""
    _safe_call(on_start, run_id)
    return {
        "ok": True,
        "run_id": run_id,
        "executor": "team",
        "flow": flow,
        "goal_id": goal_id,
        "status": "started",
    }
