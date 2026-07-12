"""Board disk-mirror hydration endpoint (/comms/hydrate)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("comms_hydrate", __name__)


@bp.route("/comms/hydrate", methods=["POST"])
def comms_hydrate():
    """Import a project's on-disk BOARD.json mirrors back into the DB for any board
    that is currently empty — the fresh-clone story (P2). Body: {project_root}.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        project_root = data.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            return (
                jsonify({"error": "Field 'project_root' must be a non-empty string"}),
                400,
            )

        from pathly_orchestrator.board_mirror import hydrate_project
        from pathly_orchestrator.db.connection import get_db

        result = hydrate_project(get_db(), project_root)
        return jsonify(result), 200
    except Exception as exc:
        logging.exception("comms_hydrate error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
