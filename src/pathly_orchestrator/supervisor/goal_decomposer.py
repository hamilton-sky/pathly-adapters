"""Goal decomposition strategies: planner (fast) and consultation (heavy FSM)."""

from __future__ import annotations

from typing import Callable, Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"
_CONSULTATION_FLOW = "consultation"


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
    """Decompose an EXISTING goal into a task DAG.

    mode='planner' — one agent run, fast, DAG-only.
    mode='consultation' — heavy PO→architect→researcher→designer→planner flow.
    Refuses if the goal already has tasks.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    row = conn.execute(
        "SELECT id, board, scope, text, type FROM comms_messages WHERE id=? AND deleted_at IS NULL",
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

    existing_tasks = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE goal_id=? AND type='task' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    if existing_tasks and existing_tasks["n"]:
        return {
            "ok": False,
            "reason": "already_decomposed",
            "error": f"goal {goal_id!r} already has {existing_tasks['n']} task(s)",
        }

    mode = (mode or "planner").strip().lower()
    if mode == "planner":
        return _decompose_planner(
            goal_id, board, scope, goal_text,
            project_root=project_root, adapter=adapter, model=model,
            progress=progress, broadcast_fn=broadcast_fn,
            on_start=on_start, on_done=on_done, spawn_fn=spawn_fn, block=block,
        )
    if mode == "consultation":
        return _decompose_consultation(
            goal_id, board, scope,
            project_root=project_root, model=model,
            broadcast_fn=broadcast_fn, on_start=on_start, on_done=on_done,
            start_fn=start_fn,
        )
    return {
        "ok": False,
        "reason": "unknown_mode",
        "error": f"unknown decompose mode {mode!r} (expected planner|consultation)",
    }


def _decompose_planner(
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
    """Light decomposer: one planner run posts 3-7 tasks under the existing goal."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    post_url = "http://127.0.0.1:8765/comms/post"
    instructions = (
        f"Analyze the goal below and break it into 3-7 concrete, actionable tasks.\n\n"
        f"**Goal:** {goal_text}\n\n"
        "For each task make an HTTP POST request:\n\n"
        f"  POST {post_url}\n"
        "  Content-Type: application/json\n\n"
        "  {\n"
        f'    "board": "{board}",\n'
        f'    "scope": "{scope}",\n'
        '    "from": "planner",\n'
        '    "type": "task",\n'
        f'    "goal_id": "{goal_id}",\n'
        '    "text": "<one-line task title>",\n'
        '    "stage": "implement",\n'
        '    "status": "pending"\n'
        "  }\n\n"
        "Rules:\n"
        "- POST all tasks before doing anything else — that is your entire job\n"
        "- Do NOT create plan files, run the planning workflow, or read any skill files\n"
        "- Do NOT post a new goal (goal_id already exists)\n"
        "- Each task title must be actionable and specific (e.g. 'Set up DB schema')\n"
        f"- Stamp every task with goal_id={goal_id!r}"
    )
    result = start_board_run(
        board, scope, "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill="",
        agent="planner",
        progress=progress,
        broadcast_fn=broadcast_fn,
        on_start=on_start,
        on_done=on_done,
        spawn_fn=spawn_fn,
        block=block,
    )
    if isinstance(result, dict) and result.get("ok"):
        result["mode"] = "planner"
        result["goal_id"] = goal_id
    return result


def _decompose_consultation(
    goal_id: str,
    board: str,
    scope: str,
    *,
    project_root: str,
    model: str,
    broadcast_fn,
    on_start,
    on_done,
    start_fn,
) -> dict:
    """Heavy decomposer: run the consultation FSM flow (PO→architect→…→planner)."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.goal_executor import _safe_call
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

    _start = start_fn
    if _start is None:
        from pathly_orchestrator.supervisor.api import start_run as _start

    try:
        state = _start(
            topic=scope,
            flow=_CONSULTATION_FLOW,
            project_root=project_root or "",
            model=model or _DEFAULT_MODEL,
            broadcast_fn=broadcast_fn,
            interactive=False,
        )
    except ValueError as exc:
        return {"ok": False, "reason": "board_busy", "error": str(exc)}

    run_id = getattr(state, "run_id", "") or ""
    _safe_call(on_start, run_id)
    return {
        "ok": True,
        "run_id": run_id,
        "mode": "consultation",
        "goal_id": goal_id,
        "status": "started",
    }
