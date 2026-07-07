"""Goals read-model endpoint (GET /comms/goals).

The symmetric READ partner to the /comms/goals/{run,stop,decompose} write side
(which live in goals.py — kept separate here because goals.py is at the 400-line
limit). One call returns each goal on the board plus its task-DAG rollup, so
callers no longer fetch goals and tasks separately and join them client-side.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("comms_goals_read", __name__)


@bp.route("/comms/goals", methods=["GET"])
def comms_goals_list():
    """List goals on ``(board, scope)``, each enriched with its task rollup.

    Query params (mirrors GET /comms/tasks): ``feature`` (required), ``board``
    (feature|project|global, default feature), ``scope`` (default = feature).
    Returns ``[{id, slug, text, executor, from_agent, ts,
    tasks:{total, done, in_progress, pending, blocked, failed, ready}}]``.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            get_goals_with_rollup as _rollup,
        )

        feature = request.args.get("feature", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400

        board = (request.args.get("board") or "feature").strip() or "feature"
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = (request.args.get("scope") or feature).strip() or feature

        return jsonify(_rollup(_get_db(), board, scope)), 200
    except Exception as exc:
        logging.exception("comms_goals_list error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
