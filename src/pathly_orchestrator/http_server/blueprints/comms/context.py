"""Agent-context preview endpoint (board-context-pull Solution C).

``POST /comms/agent-context/preview`` renders the exact ``## Communication Board``
block that WOULD be injected into an agent's prompt for a task — read-only, no DB
writes — plus a per-channel count breakdown. Lets a human sanity-check governance
and catalog scoping before dispatching a goal.

It is a thin wrapper over ``board_context_for`` (the real injection path) so the
previewed block can never drift from what an agent actually receives. This sits in
its own file rather than ``settings.py`` to respect the one-domain-per-file rule.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("comms_context_preview", __name__)


@bp.route("/comms/agent-context/preview", methods=["POST"])
def comms_agent_context_preview():
    """Render the board-context block for a task without running it."""
    try:
        from pathly_orchestrator.runner.comms_context import board_context_for

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        scope = data.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400

        board = data.get("board")
        if not isinstance(board, str) or not board.strip():
            board = "feature"
        if board not in ("feature", "project", "global"):
            board = "feature"

        project_root = data.get("project_root") or ""
        task_description = data.get("task_description") or ""
        task_id = data.get("task_id") or None

        counts: dict[str, int] = {}
        block = board_context_for(
            board=board,
            scope=scope,
            project_root=project_root,
            task_description=task_description,
            task_id=task_id,
            counts=counts,
        )

        return (
            jsonify(
                {
                    "ok": True,
                    "board": board,
                    "scope": scope,
                    "block": block,
                    "channels": {
                        "governance": counts.get("governance", 0),
                        "referenced": counts.get("referenced", 0),
                        "semantic": counts.get("semantic", 0),
                        "catalog": counts.get("catalog", 0),
                    },
                }
            ),
            200,
        )
    except Exception as exc:
        logging.exception("comms_agent_context_preview error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
