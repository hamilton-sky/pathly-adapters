"""Feature decompose endpoint (/comms/features/decompose)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner

bp = Blueprint("comms_features", __name__)

_VALID_RIGORS = {"light", "full", "consultation"}
_DEFAULT_MODEL = "claude-sonnet-4-6"


@bp.route("/comms/features/decompose", methods=["POST"])
def comms_features_decompose():
    """Decompose a feature into a task DAG or full plan.

    Body: {feature, project_root, rigor, adapter?, model?}
    rigor: "light" → planning/feature-decompose skill
           "full"  → planning/plan skill
           "consultation" → feature-consultation FSM flow
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        feature = (data.get("feature") or "").strip()
        if not feature:
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400

        rigor = (data.get("rigor") or "light").strip().lower()
        if rigor not in _VALID_RIGORS:
            return (
                jsonify({
                    "error": (
                        f"Field 'rigor' must be one of: {', '.join(sorted(_VALID_RIGORS))}"
                    ),
                    "reason": "invalid_rigor",
                }),
                400,
            )

        project_root = (data.get("project_root") or "").strip()
        adapter = (data.get("adapter") or "claude").strip()
        model = (data.get("model") or "").strip()

        board = "feature"
        scope = feature

        if rigor in ("light", "full"):
            return _dispatch_board_run(
                feature=feature,
                board=board,
                scope=scope,
                rigor=rigor,
                project_root=project_root,
                adapter=adapter,
                model=model,
            )
        return _dispatch_consultation(
            feature=feature,
            board=board,
            scope=scope,
            project_root=project_root,
            model=model,
        )

    except Exception as exc:
        logging.exception("comms_features_decompose error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


def _dispatch_board_run(
    *,
    feature: str,
    board: str,
    scope: str,
    rigor: str,
    project_root: str,
    adapter: str,
    model: str,
) -> tuple:
    """Dispatch a light or full single-agent board run for the feature."""
    from pathly_orchestrator.db.connection import get_db as _get_db
    from pathly_orchestrator.db.queries.comms import post_message as _post_message
    from pathly_orchestrator.supervisor.board_run import start_board_run

    skill = "planning/feature-decompose" if rigor == "light" else "planning/plan"
    instructions = (
        f"Decompose the feature '{feature}' into a plan and task DAG. "
        f"Write all artifacts to the feature directory."
    )

    _storage_path_str = ""
    if project_root:
        try:
            import os
            _storage_path_str = os.path.join(
                project_root, "pathly", "features", feature
            )
            os.makedirs(_storage_path_str, exist_ok=True)
        except Exception:
            pass

    _caps = None
    try:
        from pathly_orchestrator.skills.compose import build_adapter_caps
        _caps = build_adapter_caps(adapter or "claude", kind="dag")
    except Exception:
        pass

    def _board_post(text: str, phase: str | None = None) -> None:
        try:
            c = _get_db()
            mid = _post_message(
                c,
                board=board,
                scope=scope,
                from_agent="system",
                type="status",
                text=text,
            )
            payload: dict = {
                "type": "COMMS_UPDATE",
                "event": "feature_decompose",
                "feature": feature,
                "message_id": mid,
                "board": board,
                "scope": scope,
            }
            if phase:
                payload["phase"] = phase
            _broadcast_comms(scope, payload)
        except Exception:
            logging.debug("feature_decompose lifecycle post failed", exc_info=True)

    def _on_start(_run_id: str) -> None:
        _board_post(f"decomposing feature via {rigor}…", phase="running")

    def _on_done(_run_id: str, res) -> None:
        if isinstance(res, dict) and res.get("error"):
            if res.get("announced"):
                return
            err = str(res.get("error"))
            low = err.lower()
            if (
                res.get("status") == "aborted"
                or "stop" in low
                or "abort" in low
                or "kill" in low
            ):
                _board_post("feature decomposition stopped", phase="stopped")
                return
            _board_post(f"feature decomposition failed — {err[:300]}", phase="error")
            return
        _board_post("feature decomposition finished", phase="done")

    result = start_board_run(
        board, scope, "single-agent",
        instructions=instructions,
        project_root=project_root,
        model=model or _DEFAULT_MODEL,
        adapter=adapter or "claude",
        skill=skill,
        agent="planner",
        broadcast_fn=_broadcast_runner,
        on_start=_on_start,
        on_done=_on_done,
        storage_path=_storage_path_str,
        caps=_caps,
    )

    if result.get("ok"):
        result["rigor"] = rigor
        result["feature"] = feature
        return jsonify(result), 200

    reason = result.get("reason") or result.get("error") or ""
    status_code = {"board_busy": 409}.get(reason, 400)
    result["rigor"] = rigor
    result["feature"] = feature
    return jsonify(result), status_code


def _dispatch_consultation(
    *,
    feature: str,
    board: str,
    scope: str,
    project_root: str,
    model: str,
) -> tuple:
    """Dispatch a feature-consultation FSM flow for the feature."""
    from pathly_orchestrator.db.connection import get_db as _get_db
    from pathly_orchestrator.db.queries.comms import post_message as _post_message
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.goal_executor import _safe_call
    from pathly_orchestrator.supervisor.registry import get_state

    if board_lock.holder(board, scope) is not None:
        return (
            jsonify({
                "ok": False,
                "reason": "board_busy",
                "error": "board is busy (a run holds the lock)",
            }),
            409,
        )
    existing = get_state(scope)
    if existing is not None and existing.status in ("running", "paused", "awaiting_decision"):
        return (
            jsonify({
                "ok": False,
                "reason": "board_busy",
                "error": (
                    f"a pipeline run is already active for {scope!r} "
                    f"(status={existing.status})"
                ),
            }),
            409,
        )

    topic = feature  # feature slug = FSM topic → stored at pathly/features/<feature>/
    if project_root:
        try:
            import os
            os.makedirs(
                os.path.join(project_root, "pathly", "features", feature),
                exist_ok=True,
            )
        except Exception:
            pass

    from pathly_orchestrator.supervisor.api import start_run
    from pathly_orchestrator.supervisor.goal_executor import _reset_fsm_state_for_flow

    _reset_fsm_state_for_flow("feature-consultation", topic, project_root)

    def _board_post(text: str, phase: str | None = None) -> None:
        try:
            c = _get_db()
            mid = _post_message(
                c,
                board=board,
                scope=scope,
                from_agent="system",
                type="status",
                text=text,
            )
            payload: dict = {
                "type": "COMMS_UPDATE",
                "event": "feature_decompose",
                "feature": feature,
                "message_id": mid,
                "board": board,
                "scope": scope,
            }
            if phase:
                payload["phase"] = phase
            _broadcast_comms(scope, payload)
        except Exception:
            logging.debug("feature_consultation lifecycle post failed", exc_info=True)

    def _on_done(_run_id: str, res) -> None:
        if isinstance(res, dict) and res.get("error"):
            if res.get("announced"):
                return
            err = str(res.get("error"))
            low = err.lower()
            if (
                res.get("status") == "aborted"
                or "stop" in low
                or "abort" in low
                or "kill" in low
            ):
                _board_post("feature consultation stopped", phase="stopped")
                return
            _board_post(f"feature consultation failed — {err[:300]}", phase="error")
            return
        _board_post("feature consultation finished", phase="done")

    try:
        state = start_run(
            topic=topic,
            flow="feature-consultation",
            project_root=project_root or "",
            model=model or _DEFAULT_MODEL,
            broadcast_fn=_broadcast_runner,
            interactive=False,
            on_done=_on_done,
        )
    except ValueError as exc:
        return (
            jsonify({"ok": False, "reason": "board_busy", "error": str(exc)}),
            409,
        )

    run_id = getattr(state, "run_id", "") or ""
    _safe_call(_board_post, "feature consultation started…", "running")
    return (
        jsonify({
            "ok": True,
            "run_id": run_id,
            "rigor": "consultation",
            "feature": feature,
            "status": "started",
        }),
        200,
    )
