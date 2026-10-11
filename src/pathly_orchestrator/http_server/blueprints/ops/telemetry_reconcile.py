"""GET /telemetry/reconcile — Pathly's recorded spend vs ccusage's machine-wide daily total.

See ``runner/cost_reconcile.py`` for the invariant (Pathly <= ccusage per local day per tool).
"""

from __future__ import annotations

from flask import jsonify, request

from ._telemetry_bp import _get_db, bp, logger


@bp.route("/telemetry/reconcile", methods=["GET"])
def reconcile_endpoint():
    """Query: ``days`` (1-31, default 7), ``project_root`` (optional), ``tolerance``
    (0-1, default 0.10). Always 200 — ``status`` says ok / overstated / unavailable."""
    from pathly_orchestrator.runner.cost_reconcile import (
        DEFAULT_TOLERANCE,
        reconcile_costs,
    )

    days = max(1, min(request.args.get("days", 7, type=int) or 7, 31))
    tolerance = request.args.get("tolerance", DEFAULT_TOLERANCE, type=float)
    tolerance = min(max(tolerance, 0.0), 1.0)
    project_root = (request.args.get("project_root") or "").strip().replace(
        "\\", "/"
    ) or None
    try:
        return jsonify(reconcile_costs(_get_db(), days, project_root, tolerance)), 200
    except Exception as exc:
        logger.exception("reconcile_endpoint error")
        return jsonify({"status": "unavailable", "reason": str(exc), "days": []}), 200
