"""Unified run read API (unified-control-plane P0) — GET /runs, GET /runs/<run_id>.

A NEW blueprint domain at the server ROOT (no ``/runner`` prefix → a new namespace, so it
cannot collide with the existing runner routes). Read-only over the P0 read-model
(``db/queries/run_history_read``) with the supervisor live-status overlay
(``supervisor/dispatch``). Lazy imports INSIDE each handler per the layer rule (http_server
may import db/supervisor, but only inside route functions).
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("control_runs_read", __name__)


@bp.route("/runs", methods=["GET"])
def list_runs_route():
    """List top-level runs for ``project_root`` (ARCHITECTURE §4.1), overlaid with live
    status + per-kind capabilities. Empty list when no ``project_root`` is given; ``limit``
    is capped at 200 (a bad/absent value falls back to 50)."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.run_history_read import list_runs
        from pathly_orchestrator.supervisor.dispatch import overlay_live_status

        project_root = (request.args.get("project_root") or "").strip()
        try:
            limit = min(int(request.args.get("limit", 50)), 200)
        except (TypeError, ValueError):
            limit = 50
        runs = list_runs(get_db(), project_root, limit) if project_root else []
        return jsonify(overlay_live_status(runs)), 200
    except Exception as exc:
        logging.exception("control list_runs error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runs/<run_id>", methods=["GET"])
def get_run_route(run_id: str):
    """Full RunDetail for ``run_id`` (ARCHITECTURE §4.2): 200 with the detail, or 404
    ``{'error': 'unknown run_id'}`` when no ``run_history`` row matches."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.run_history_read import get_run_detail

        detail = get_run_detail(get_db(), run_id)
        if not detail.get("run"):
            return jsonify({"error": "unknown run_id"}), 404
        return jsonify(detail), 200
    except Exception as exc:
        logging.exception("control get_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
