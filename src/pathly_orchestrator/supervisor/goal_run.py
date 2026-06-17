"""Goal executor dispatcher — Phase 1 (serial).

`start_goal_run` reads a goal message's `executor` and routes its task-DAG to one
of `single` | `loop` | `team`. **Ship serial** — `k>1` is P3. The DAG already
lives on the board (Phase 0b); this module is the missing driver.

See: pathly/plans/comms-board/phases/PHASE-1-dispatcher.md

  single → ONE agent drains the whole goal (reuses board_run + the drain-dag skill)
  loop   → supervisor owns the frontier (wires the existing scheduler_loop, serial)
  team   → trimmed team FSM flow (team-build) via start_run

spawn_fn is dependency-injected so tests can drive both paths without real PTYs.
"""
from __future__ import annotations

import threading
import uuid
from typing import Callable, Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"
_TEAM_FLOW = "team-build"  # the trimmed team flow (build→review→test→retro)


def _safe_call(fn: Optional[Callable], *args) -> None:
    """Invoke a lifecycle callback best-effort; a bad callback never breaks a run."""
    if fn is None:
        return
    try:
        fn(*args)
    except Exception:
        pass


def start_goal_run(
    goal_id: str,
    *,
    executor_override: str | None = None,
    flow_override: str | None = None,   # executor='team': which FSM flow to run (default team-build)
    project_root: str = "",
    adapter: str = "claude",
    model: str = "",
    progress: str = "normal",
    broadcast_fn: Optional[Callable] = None,        # runner stream (worker TERMINAL_SPAWN)
    event_broadcast_fn: Optional[Callable] = None,  # comms stream (task-state events)
    on_start: Optional[Callable] = None,
    on_done: Optional[Callable] = None,
    spawn_fn: Optional[Callable] = None,
    start_fn: Optional[Callable] = None,
    block: bool = False,
) -> dict:
    """Read the goal's executor and dispatch its DAG. Returns a dict with `ok` and,
    on failure, a `reason` the HTTP layer maps to a status code
    (not_found→404, not_goal→400, board_busy→409, not_implemented→501).

    executor_override (the UI selector) wins over the goal's stored executor and is
    persisted back onto the goal so the board reflects the pick after a reload."""
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
            "ok": False, "reason": "not_goal",
            "error": f"message {goal_id!r} is type={row['type']!r}, not 'goal'",
        }

    board = row["board"] or "feature"
    scope = row["scope"] or ""
    goal_text = row["text"] or ""
    if executor_override and executor_override.strip():
        executor = executor_override.strip().lower()
        if executor != (row["executor"] or ""):
            set_goal_executor(conn, goal_id, executor)  # persist the UI pick
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
        "ok": False, "reason": "unknown_executor",
        "error": f"unknown executor {executor!r} (expected single|loop|team)",
    }


def _run_single(
    goal_id: str, board: str, scope: str, goal_text: str, *,
    project_root: str, adapter: str, model: str, progress: str,
    broadcast_fn, on_start, on_done, spawn_fn, block: bool,
) -> dict:
    """ONE agent drains the whole goal. Reuses start_board_run (lock + skill compose
    + async spawn); the drain-dag skill is the agent's self-loop contract."""
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
        on_start=on_start, on_done=on_done,
        spawn_fn=spawn_fn,
        block=block,
    )
    if isinstance(result, dict) and result.get("ok"):
        result["executor"] = "single"
        result["goal_id"] = goal_id
    return result


def _run_loop(
    goal_id: str, board: str, scope: str, *,
    project_root: str, adapter: str, model: str,
    broadcast_fn, event_broadcast_fn, on_start, on_done, spawn_fn, block: bool,
) -> dict:
    """Supervisor owns the frontier: wire the existing scheduler_loop with
    SerialIsolation (one worker), scoped to this goal. Holds the board lock for the
    run; abort = the lock being released/stolen (e.g. a future stop route)."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop
    from pathly_orchestrator.supervisor.state import RunnerState

    run_id = str(uuid.uuid4())
    if not board_lock.acquire(board, scope, run_id):
        return {
            "ok": False, "reason": "board_busy", "error": "board is busy",
            "holder": board_lock.holder(board, scope),
        }

    state = RunnerState(
        topic=scope, flow="goal-loop", project_root=project_root,
        model=model or _DEFAULT_MODEL, timeout=600, run_id=run_id,
        current_adapter=adapter or "claude",
    )
    isolation = SerialIsolation()

    def _abort_check() -> bool:
        # The lock is held by this run for its lifetime; a stop releases/steals it.
        return board_lock.holder(board, scope) != run_id

    def _work() -> dict:
        try:
            _safe_call(on_start, run_id)
            kwargs: dict = dict(
                isolation=isolation, broadcast_fn=broadcast_fn,
                event_broadcast_fn=event_broadcast_fn, goal_id=goal_id,
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
        except Exception as exc:  # noqa: BLE001 — async failure must still reach the board
            _safe_call(on_done, run_id, {"result": f"error: {exc}", "error": str(exc)})

    threading.Thread(target=_runner, daemon=True, name=f"goal-loop-{run_id[:8]}").start()
    return {"ok": True, "run_id": run_id, "executor": "loop", "status": "started"}


def _run_team(
    goal_id: str, board: str, scope: str, *,
    flow: str = _TEAM_FLOW,
    project_root: str, adapter: str, model: str,
    broadcast_fn, on_start, on_done, start_fn,
) -> dict:
    """team executor: run an FSM flow (default the trimmed team-build build→review→test→retro)
    on the goal's scope, reusing the supervisor pipeline (start_run → visible PTY
    stages). Serial: refuses if any run (board-lock or pipeline) is already active for
    the scope. start_run is async, so on_done (the board 'finished' post) is left to
    the pipeline's own RUN_COMPLETE SSE — we only fire on_start here.

    NOTE: the team executor consumes the goal's plan artifacts (the consultation flow
    or a full planner run produced them). A DAG-only goal with no plan files is better
    run with single/loop. The 'team-build' flow is seeded into the DB by _refresh_flows
    on server start — a server that predates it must restart to pick it up.
    """
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.registry import get_state

    # A single/loop run holds the board lock; an FSM pipeline run lives in the registry.
    if board_lock.holder(board, scope) is not None:
        return {"ok": False, "reason": "board_busy", "error": "board is busy (a run holds the lock)"}
    existing = get_state(scope)
    if existing is not None and existing.status in ("running", "paused", "awaiting_decision"):
        return {
            "ok": False, "reason": "board_busy",
            "error": f"a pipeline run is already active for {scope!r} (status={existing.status})",
        }

    # Validate the flow exists so a typo/unknown flow fails fast (400) instead of
    # crashing the supervisor loop. Skipped when start_fn is injected (tests).
    if start_fn is None:
        try:
            from pathly_orchestrator.fsm_ops import _load_flow
            _load_flow(flow, project_root or None)
        except Exception:
            return {"ok": False, "reason": "unknown_flow",
                    "error": f"flow {flow!r} not found (run any seeded flow: team-build, debug, quick-fix, …)"}

    _start = start_fn
    if _start is None:
        from pathly_orchestrator.supervisor.api import start_run as _start

    try:
        state = _start(
            topic=scope,
            flow=flow,
            project_root=project_root or "",
            model=model or _DEFAULT_MODEL,
            broadcast_fn=broadcast_fn,
        )
    except ValueError as exc:  # start_run guards against a duplicate active topic
        return {"ok": False, "reason": "board_busy", "error": str(exc)}

    run_id = getattr(state, "run_id", "") or ""
    _safe_call(on_start, run_id)
    return {"ok": True, "run_id": run_id, "executor": "team", "flow": flow,
            "goal_id": goal_id, "status": "started"}


# ── Decompose bridge: turn a chosen goal into a task DAG ──────────────────────
_CONSULTATION_FLOW = "consultation"
_PLAN_SKILL = "planning/plan"


def start_goal_decompose(
    goal_id: str,
    *,
    mode: str = "planner",
    project_root: str = "",
    adapter: str = "claude",
    model: str = "",
    progress: str = "normal",
    broadcast_fn: Optional[Callable] = None,
    on_start: Optional[Callable] = None,
    on_done: Optional[Callable] = None,
    spawn_fn: Optional[Callable] = None,
    start_fn: Optional[Callable] = None,
    block: bool = False,
) -> dict:
    """Decompose an EXISTING goal into a task DAG — the bridge from an analyzed/chosen
    goal to runnable tasks. `mode='planner'` runs the planner (fast, DAG-only);
    `mode='consultation'` runs the heavy PO→architect→researcher→designer→planner flow.
    Either way the planner's plan.md Step 6 seeds the `type=task` messages under this
    goal's id. Refuses if the goal already has tasks (already decomposed)."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    row = conn.execute(
        "SELECT id, board, scope, text, type FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    if row is None:
        return {"ok": False, "reason": "not_found", "error": f"goal {goal_id!r} not found"}
    if (row["type"] or "") != "goal":
        return {"ok": False, "reason": "not_goal",
                "error": f"message {goal_id!r} is type={row['type']!r}, not 'goal'"}

    board = row["board"] or "feature"
    scope = row["scope"] or ""
    goal_text = row["text"] or ""

    existing_tasks = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE goal_id=? AND type='task' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    if existing_tasks and existing_tasks["n"]:
        return {"ok": False, "reason": "already_decomposed",
                "error": f"goal {goal_id!r} already has {existing_tasks['n']} task(s)"}

    mode = (mode or "planner").strip().lower()
    if mode == "planner":
        return _decompose_planner(
            goal_id, board, scope, goal_text,
            project_root=project_root, adapter=adapter, model=model, progress=progress,
            broadcast_fn=broadcast_fn, on_start=on_start, on_done=on_done,
            spawn_fn=spawn_fn, block=block,
        )
    if mode == "consultation":
        return _decompose_consultation(
            goal_id, board, scope,
            project_root=project_root, model=model, broadcast_fn=broadcast_fn,
            on_start=on_start, on_done=on_done, start_fn=start_fn,
        )
    return {"ok": False, "reason": "unknown_mode",
            "error": f"unknown decompose mode {mode!r} (expected planner|consultation)"}


def _decompose_planner(
    goal_id: str, board: str, scope: str, goal_text: str, *,
    project_root: str, adapter: str, model: str, progress: str,
    broadcast_fn, on_start, on_done, spawn_fn, block: bool,
) -> dict:
    """Light decomposer: one planner run on the goal's scope. The directive tells the
    planner the goal ALREADY exists, so it posts tasks under this goal_id (plan.md
    Step 6) without creating a second goal."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    instructions = (
        f"Decompose the EXISTING goal into a task DAG. goal_id={goal_id!r}, scope={scope!r}.\n"
        f"Goal: {goal_text}\n\n"
        "Produce the plan files, then execute plan.md Step 6 to post one type=task per "
        f"phase — but the goal already exists, so do NOT post a new type=goal; stamp every "
        f"task with goal_id={goal_id!r}. The posted tasks are this goal's DAG."
    )
    result = start_board_run(
        board, scope, "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill=_PLAN_SKILL,
        agent="planner",
        progress=progress,
        broadcast_fn=broadcast_fn,
        on_start=on_start, on_done=on_done,
        spawn_fn=spawn_fn,
        block=block,
    )
    if isinstance(result, dict) and result.get("ok"):
        result["mode"] = "planner"
        result["goal_id"] = goal_id
    return result


def _decompose_consultation(
    goal_id: str, board: str, scope: str, *,
    project_root: str, model: str, broadcast_fn, on_start, on_done, start_fn,
) -> dict:
    """Heavy decomposer: run the consultation FSM flow (PO→architect→researcher→
    designer→planner) on the goal's scope. The planner stage seeds the DAG."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.registry import get_state

    if board_lock.holder(board, scope) is not None:
        return {"ok": False, "reason": "board_busy", "error": "board is busy (a run holds the lock)"}
    existing = get_state(scope)
    if existing is not None and existing.status in ("running", "paused", "awaiting_decision"):
        return {"ok": False, "reason": "board_busy",
                "error": f"a pipeline run is already active for {scope!r} (status={existing.status})"}

    _start = start_fn
    if _start is None:
        from pathly_orchestrator.supervisor.api import start_run as _start

    try:
        state = _start(
            topic=scope, flow=_CONSULTATION_FLOW,
            project_root=project_root or "", model=model or _DEFAULT_MODEL,
            broadcast_fn=broadcast_fn,
        )
    except ValueError as exc:
        return {"ok": False, "reason": "board_busy", "error": str(exc)}

    run_id = getattr(state, "run_id", "") or ""
    _safe_call(on_start, run_id)
    return {"ok": True, "run_id": run_id, "mode": "consultation", "goal_id": goal_id, "status": "started"}
