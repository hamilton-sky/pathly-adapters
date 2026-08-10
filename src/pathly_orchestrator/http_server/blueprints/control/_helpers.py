"""Shared run-resolution + run-creation helpers for the control blueprint
(unified-control-plane).

Both ``POST /runs/<run_id>/stop`` and ``POST /runs/<run_id>/<action>`` resolve a run_id the
same way: an ACTIVE registry ``RunnerState`` (FSM flow/team/consultation) keyed by topic, or a
board-lock holder (board single/evaluator, goal single/loop). ``create_run`` (used by ``POST
/runs``) is the inverse — a thin RunSpec in, a dispatch to the matching EXISTING facade out.
Extracted here so ``runs_control.py`` stays a thin route layer, under the 400-line file cap.

Lazy imports INSIDE each function per the layer rule (http_server may import supervisor/db,
but only inside route/helper functions, never at module top-level).
"""

from __future__ import annotations

from typing import Optional

ACTIVE_STATUSES = ("running", "paused", "awaiting_decision")


def find_registry_run(run_id: str, statuses=ACTIVE_STATUSES) -> Optional[tuple]:
    """Reverse-lookup: the ``(topic, RunnerState)`` whose ``run_id`` matches, or ``None``.

    ``statuses``: restrict the match to these statuses (default: only ACTIVE runs, mirroring
    the stop resolver). Pass ``None`` to match a run_id regardless of status — ``retry`` needs
    a FINISHED run, the inverse of every other action.
    """
    from pathly_orchestrator.supervisor.registry import _lock, _registry

    with _lock:
        for topic, state in _registry.items():
            if getattr(state, "run_id", "") != run_id:
                continue
            if statuses is not None and state.status not in statuses:
                continue
            return topic, state
    return None


def resolve_and_abort(run_id: str) -> tuple[dict, int]:
    """Stop/abort ``run_id`` wherever it lives. Idempotent.

    The shared body of both ``POST /runs/<run_id>/stop`` and the ``abort`` case of
    ``POST /runs/<run_id>/<action>`` — kept byte-for-byte equivalent so the two routes are
    interchangeable for a caller that only knows the run_id.
    """
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.api import abort_run

    found = find_registry_run(run_id, statuses=ACTIVE_STATUSES)
    if found is not None:
        topic, _state = found
        abort_run(topic, announced=True)
        return {"ok": True, "stopped": True, "run_id": run_id, "via": "runner_abort"}, 200

    board_found = board_lock.find_by_holder(run_id)
    if board_found is not None:
        board, scope = board_found
        _release_board_run(run_id, board, scope)
        return {"ok": True, "stopped": True, "run_id": run_id, "via": "board_stop"}, 200

    return {"ok": True, "stopped": False, "run_id": run_id, "reason": "not_active"}, 200


def _release_board_run(run_id: str, board: str, scope: str) -> None:
    """Mirror /comms/run/stop's kill: TERMINAL_KILL SSE + mark the PTY result + release the
    lock (releasing also trips a loop's abort_check, so its scheduler winds down) + post a
    board status message. Each side effect is independently best-effort — mirrors the original
    inline stop_run_route logic this was extracted from verbatim.
    """
    from ...sse import _broadcast_comms, _broadcast_runner
    from pathly_orchestrator.supervisor import board_lock, get_run

    tab_id = f"runner-{run_id[-10:]}"
    try:
        _broadcast_runner(
            scope, {"type": "TERMINAL_KILL", "tab_id": tab_id, "run_id": run_id}
        )
    except Exception:
        pass
    try:
        run = get_run(run_id)
        if run is not None:
            run.mark_pty_result({"exit_code": 0, "result": {"result": "stopped by user"}})
    except Exception:
        pass
    board_lock.release(board, scope, run_id)
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message

        mid = _post_message(
            _get_db(),
            board=board,
            scope=scope,
            from_agent="system",
            type="status",
            text="⏹ run stopped by user",
        )
        _broadcast_comms(
            scope,
            {
                "type": "COMMS_UPDATE",
                "event": "board_run",
                "message_id": mid,
                "board": board,
                "scope": scope,
            },
        )
    except Exception:
        pass


def handle_retry(run_id: str, topic: str, state, body: dict) -> tuple[dict, int]:
    """Retry a finished/errored run addressed by run_id.

    Mirrors ``POST /runner/retry``'s exact validation + ``start_run`` call — the only
    difference is the topic comes from resolving run_id (via the caller's registry lookup)
    instead of a ``topic`` body field.
    """
    if state.status in ACTIVE_STATUSES:
        return {"ok": False, "run_id": run_id, "reason": "already_active"}, 200

    from pathly_orchestrator.supervisor import _lock, _registry
    from pathly_orchestrator.supervisor.api import start_run

    with _lock:
        _registry.pop(topic, None)

    required = {"flow", "project_root", "max_iterations", "max_cost_usd"}
    missing = required - set(body.keys())
    if missing:
        return {"error": f"Missing fields: {', '.join(sorted(missing))}"}, 400

    max_iterations = body.get("max_iterations")
    if not isinstance(max_iterations, int) or max_iterations <= 0:
        return {"error": "Field 'max_iterations' must be a positive integer"}, 400

    max_cost_usd = body.get("max_cost_usd")
    if not isinstance(max_cost_usd, (int, float)) or max_cost_usd <= 0:
        return {"error": "Field 'max_cost_usd' must be a positive number"}, 400

    model = body.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"
    timeout = body.get("timeout", 600)
    if not isinstance(timeout, int) or timeout <= 0:
        timeout = 600
    autonomy = body.get("autonomy", {})
    if not isinstance(autonomy, dict):
        autonomy = {}

    from ...sse import _broadcast_runner

    try:
        new_state = start_run(
            topic=topic,
            flow=body["flow"],
            project_root=body["project_root"],
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=float(max_cost_usd),
            autonomy=autonomy,
            broadcast_fn=_broadcast_runner,
        )
    except ValueError as exc:
        return {"error": str(exc)}, 409

    return {"ok": True, "run_id": new_state.run_id, "topic": topic, "action": "retry"}, 200


# ── POST /runs (create) — thin RunSpec -> the matching existing facade ─────────────────

_RUN_KINDS = frozenset({"flow", "single", "evaluator", "goal"})
_BOARD_RUN_MODE = {"single": "single-agent", "evaluator": "evaluator"}
# Mirrors /comms/run's per-adapter default (comms/runs.py) so a launcher-started board run
# picks a model that actually matches its adapter, instead of start_board_run's own fixed
# claude-only default.
_BOARD_RUN_DEFAULT_MODEL = {"claude": "claude-sonnet-4-6", "codex": "gpt-5.4"}
_GOAL_RUN_STATUS = {
    "not_found": 404,
    "not_goal": 400,
    "board_busy": 409,
    "project_busy": 409,
    "unknown_executor": 400,
    "unknown_flow": 400,
}


def create_run(body: dict) -> tuple[dict, int]:
    """Validate a thin RunSpec and dispatch to the matching EXISTING facade.

    RunSpec: ``{kind, board, scope, flow?, goal_id?, adapter?, model?}`` (+ ``project_root``,
    needed by every facade below). ``kind`` selects the destination — ``flow`` ->
    ``supervisor.api.start_run``, ``single``/``evaluator`` -> ``supervisor.board_run.
    start_board_run``, ``goal`` -> ``supervisor.goal_executor.start_goal_run``. Route only —
    each facade keeps owning its own locking/telemetry/spawn logic.
    """
    kind = body.get("kind", "")
    if not isinstance(kind, str) or kind not in _RUN_KINDS:
        return {"error": f"Field 'kind' must be one of {sorted(_RUN_KINDS)}"}, 400

    project_root = body.get("project_root", "")
    if not isinstance(project_root, str):
        project_root = ""

    if kind == "flow":
        return _create_flow_run(body, project_root)
    if kind == "goal":
        return _create_goal_run(body, project_root)
    return _create_board_run(body, kind, project_root)


def _create_flow_run(body: dict, project_root: str) -> tuple[dict, int]:
    scope = body.get("scope", "")
    flow = body.get("flow", "")
    for field_name, val in (
        ("scope", scope),
        ("flow", flow),
        ("project_root", project_root),
    ):
        if not isinstance(val, str) or not val.strip():
            return {"error": f"Field '{field_name}' must be a non-empty string"}, 400

    model = body.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"

    from ...sse import _broadcast_runner
    from pathly_orchestrator.supervisor.api import start_run

    try:
        state = start_run(
            topic=scope,
            flow=flow,
            project_root=project_root,
            model=model,
            broadcast_fn=_broadcast_runner,
        )
    except ValueError as exc:
        return {"error": str(exc)}, 409

    return {"ok": True, "run_id": state.run_id, "kind": "flow"}, 200


def _create_board_run(body: dict, kind: str, project_root: str) -> tuple[dict, int]:
    scope = body.get("scope", "")
    if not isinstance(scope, str) or not scope.strip():
        return {"error": "Field 'scope' must be a non-empty string"}, 400

    board = body.get("board", "feature")
    if not isinstance(board, str) or board not in ("feature", "project", "global"):
        board = "feature"

    adapter = (body.get("adapter", "") or "claude").strip().lower()
    if adapter not in _BOARD_RUN_DEFAULT_MODEL:
        adapter = "claude"
    model = body.get("model", "") or _BOARD_RUN_DEFAULT_MODEL[adapter]

    from ...sse import _broadcast_runner
    from pathly_orchestrator.supervisor.board_run import start_board_run

    result = start_board_run(
        board,
        scope,
        _BOARD_RUN_MODE[kind],
        project_root=project_root,
        adapter=adapter,
        model=model,
        broadcast_fn=_broadcast_runner,
    )
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "board_busy")}, 409

    return {"ok": True, "run_id": result["run_id"], "kind": kind}, 200


def _create_goal_run(body: dict, project_root: str) -> tuple[dict, int]:
    goal_id = body.get("goal_id", "")
    if not isinstance(goal_id, str) or not goal_id.strip():
        return {"error": "Field 'goal_id' must be a non-empty string"}, 400

    adapter = body.get("adapter", "") or "claude"
    model = body.get("model", "") or ""

    from ...sse import _broadcast_runner
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    result = start_goal_run(
        goal_id,
        project_root=project_root,
        adapter=adapter,
        model=model,
        broadcast_fn=_broadcast_runner,
    )
    if not result.get("ok"):
        status = _GOAL_RUN_STATUS.get(result.get("reason") or "", 400)
        return result, status

    return {"ok": True, "run_id": result["run_id"], "kind": "goal"}, 200
