"""Goal executor dispatcher — Phase 1 (serial).

`start_goal_run` reads a goal message's `executor` and routes its task-DAG to one
of `single` | `loop` | `team`. **Ship serial** — `k>1` is P3. The DAG already
lives on the board (Phase 0b); this module is the missing driver.

See: pathly/plans/comms-board/phases/PHASE-1-dispatcher.md

  single → ONE agent drains the whole goal (reuses board_run + the drain-dag skill)
  loop   → supervisor owns the frontier (wires the existing scheduler_loop, serial)
  team   → trimmed team FSM flow — GATED on the two-flow split (501 for now)

spawn_fn is dependency-injected so tests can drive both paths without real PTYs.
"""
from __future__ import annotations

import threading
import uuid
from typing import Callable, Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"


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
    project_root: str = "",
    adapter: str = "claude",
    model: str = "",
    progress: str = "normal",
    broadcast_fn: Optional[Callable] = None,        # runner stream (worker TERMINAL_SPAWN)
    event_broadcast_fn: Optional[Callable] = None,  # comms stream (task-state events)
    on_start: Optional[Callable] = None,
    on_done: Optional[Callable] = None,
    spawn_fn: Optional[Callable] = None,
    block: bool = False,
) -> dict:
    """Read the goal's executor and dispatch its DAG. Returns a dict with `ok` and,
    on failure, a `reason` the HTTP layer maps to a status code
    (not_found→404, not_goal→400, board_busy→409, not_implemented→501)."""
    from pathly_orchestrator.db.connection import get_db

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
        return {
            "ok": False, "reason": "not_implemented",
            "error": "executor 'team' is not available until the two-flow split "
                     "(trimmed team flow) lands — Phase-1 follow-on",
        }
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
