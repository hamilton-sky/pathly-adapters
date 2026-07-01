"""Goal decomposition strategies: planner (fast) and consultation (heavy FSM)."""

from __future__ import annotations

from typing import Callable, Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"
_CONSULTATION_FLOW = "consultation"


def _goal_storage_dir(project_root: str, board: str, scope: str, slug: str) -> str:
    """Where a goal-decompose writes its plan + artifacts (storage-restructure Phase 2).

    Feature-tier goals nest under their feature: ``pathly/features/<feature>/goals/<slug>``
    (the feature = the goal's parent board scope). Project/global-tier goals stay at the
    legacy ``pathly/goals/<slug>`` until their scope homes are stood up (a follow-up).

    Only the board-run decompose paths (planner/plan) use this — they pass the result to
    ``start_board_run`` explicitly AND post their artifacts with absolute paths, so goal
    EXECUTION (which reads context via the board, not by re-resolving a goal dir) stays
    consistent wherever this points. The consultation path routes through the FSM resolver
    (``_resolve_storage_path``) and is NOT nested here — that needs feature-threading through
    the resolver + the fsm_compose root derivation, a documented follow-up.
    """
    import os

    if board == "feature" and scope:
        return os.path.join(project_root, "pathly", "features", scope, "goals", slug)
    return os.path.join(project_root, "pathly", "goals", slug)


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
    if mode == "plan":
        return _decompose_plan(
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
        "error": f"unknown decompose mode {mode!r} (expected planner|plan|consultation)",
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

    instructions = (
        f"Decompose this goal into 3-7 concrete, independently-runnable tasks.\n\n"
        f"Goal: {goal_text}\n\n"
        f"The goal already exists with goal_id={goal_id!r} — post task children only, "
        f"do NOT post a new goal. Follow the task-posting mechanics in the fragment below."
    )
    # Resolve goal slug for where_line so the planner knows the on-disk dir.
    _slug = scope  # fallback
    _storage_path_str = ""
    if project_root and goal_id:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.supervisor.slug import ensure_goal_slug
            import os
            _slug = ensure_goal_slug(get_db(project_root or None), goal_id)
            _goal_dir = _goal_storage_dir(project_root, board, scope, _slug)
            os.makedirs(_goal_dir, exist_ok=True)
            _storage_path_str = _goal_dir
        except Exception:
            pass

    _caps = None
    if goal_id and (adapter or "claude"):
        try:
            from pathly_orchestrator.skills.compose import build_adapter_caps
            _caps = build_adapter_caps(adapter or "claude", goal_id=goal_id, kind="dag")
        except Exception:
            pass

    result = start_board_run(
        board, scope, "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill="planning/dag-sketch",
        agent="planner",
        progress=progress,
        broadcast_fn=broadcast_fn,
        on_start=on_start,
        on_done=on_done,
        spawn_fn=spawn_fn,
        block=block,
        storage_path=_storage_path_str,
        caps=_caps,
    )
    if isinstance(result, dict) and result.get("ok"):
        result["mode"] = "planner"
        result["goal_id"] = goal_id
    return result


def _decompose_plan(
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
    """Full single-planner decompose: ONE agent runs the `planning/plan` skill → plan artifacts
    + a context_refs/depends_on-wired task DAG, without the full consultation team. The goal
    already exists, so the planner uses goal_id rather than posting a new one."""
    from pathly_orchestrator.supervisor.board_run import start_board_run

    instructions = (
        f"Decompose the goal below into a plan and a task DAG. The goal ALREADY EXISTS on the "
        f"'{board}' board (scope '{scope}') with goal_id={goal_id!r} — at the 'Post Tasks to "
        f"Comms Board' step use goal_id={goal_id!r} as $GOAL_ID and do NOT post a new goal; only "
        f"add its task children (each with context_refs + depends_on as the skill specifies)."
        + (f"\n\nGoal: {goal_text}" if goal_text else "")
    )
    # Resolve goal slug for where_line so the planner knows the on-disk dir.
    _slug = scope  # fallback
    _storage_path_str = ""
    if project_root and goal_id:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.supervisor.slug import ensure_goal_slug
            import os
            _slug = ensure_goal_slug(get_db(project_root or None), goal_id)
            _goal_dir = _goal_storage_dir(project_root, board, scope, _slug)
            os.makedirs(_goal_dir, exist_ok=True)
            _storage_path_str = _goal_dir
        except Exception:
            pass

    _caps = None
    if goal_id and (adapter or "claude"):
        try:
            from pathly_orchestrator.skills.compose import build_adapter_caps
            _caps = build_adapter_caps(adapter or "claude", goal_id=goal_id, kind="dag")
        except Exception:
            pass

    result = start_board_run(
        board, scope, "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill="planning/plan",
        agent="planner",
        progress=progress,
        broadcast_fn=broadcast_fn,
        on_start=on_start,
        on_done=on_done,
        spawn_fn=spawn_fn,
        block=block,
        storage_path=_storage_path_str,
        caps=_caps,
    )
    if isinstance(result, dict) and result.get("ok"):
        result["mode"] = "plan"
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

    # Route on-disk storage to pathly/goals/<slug> so the project path never
    # becomes a FSM topic (which collapses to itself via Path joining).
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.supervisor.slug import ensure_goal_slug
        import os
        slug = ensure_goal_slug(get_db(project_root or None), goal_id)
        _goal_dir = os.path.join(project_root, "pathly", "goals", slug)
        os.makedirs(_goal_dir, exist_ok=True)
    except Exception:
        slug = scope  # fallback: old behavior

    _start = start_fn
    if _start is None:
        from pathly_orchestrator.supervisor.api import start_run as _start
        # Re-seed a stale DONE/foreign FSM state so a re-decompose actually spawns the PO
        # stage instead of short-circuiting to {done:True}. Only when driving the real FSM.
        from pathly_orchestrator.supervisor.goal_executor import (
            _reset_fsm_state_for_flow,
        )

        _reset_fsm_state_for_flow(_CONSULTATION_FLOW, slug, project_root)

    try:
        state = _start(
            topic=slug,
            flow=_CONSULTATION_FLOW,
            project_root=project_root or "",
            model=model or _DEFAULT_MODEL,
            broadcast_fn=broadcast_fn,
            interactive=False,
            # Seed THIS goal's DAG at the terminal planner stage (not a new goal), and
            # fire the lifecycle on_done on terminal status so the board's "Decomposing…"
            # indicator clears even when the consultation flow ends in error.
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
        "mode": "consultation",
        "goal_id": goal_id,
        "status": "started",
    }
