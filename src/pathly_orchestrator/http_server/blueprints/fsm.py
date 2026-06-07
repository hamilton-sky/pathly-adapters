"""FSM next_action and complete_stage endpoints."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ..sse import _push_menu_to_sse

bp = Blueprint("fsm", __name__)


@bp.route("/next_action", methods=["POST"])
def next_action_endpoint():
    """Call next_action FSM function.

    Expects JSON POST with fields:
      - flow (str): Flow name (e.g. 'team')
      - topic (str): Feature/topic name
      - project_root (str): Absolute path to project root
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        # Validate required fields
        required = {"flow", "topic", "project_root"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        for field in ("flow", "topic", "project_root"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )

        # Import lazily through the package namespace so tests can patch
        # pathly_orchestrator.http_server.next_action and have it take effect.
        import pathly_orchestrator.http_server as _hs
        result = _hs.next_action(data)
        if isinstance(result.get("menu"), dict):
            _push_menu_to_sse(result["menu"])
        return jsonify(result), 200
    except Exception as e:
        logging.exception("next_action error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/complete_stage", methods=["POST"])
def complete_stage_endpoint():
    """Call complete_stage FSM function.

    Expects JSON POST with fields:
      - flow (str): Flow name (e.g. 'team')
      - topic (str): Feature/topic name
      - project_root (str): Absolute path to project root
      - decision (str, optional): Decision key for decide-blocks
      - resolved_files (list[str], optional): Feedback files to delete
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        # Validate required fields
        required = {"flow", "topic", "project_root"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        for field in ("flow", "topic", "project_root"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )

        import pathly_orchestrator.http_server as _hs
        result = _hs.complete_stage(data)
        if isinstance(result.get("menu"), dict):
            _push_menu_to_sse(result["menu"])
        return jsonify(result), 200
    except Exception as e:
        logging.exception("complete_stage error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
