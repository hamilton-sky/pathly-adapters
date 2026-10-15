"""HQ operator action catalog — GET /hq/actions, PUT /hq/actions/available.

The catalog (``hq_actions.CATALOG``) is fixed in code; what Settings changes is
which of its actions HQ may use at all (``hq.actions.available``). Studio's
Settings panel edits it and the composer's Actions tab lists only the available
ones. local-operator ticket 01's two-level decision.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("hq_actions", __name__)


@bp.route("/hq/actions", methods=["GET"])
def hq_actions_catalog():
    """200 ``{max_enabled, domains, presets, actions: [{name, domain, label,
    risk, description, runs_on, available, default_available, schema_tokens}]}``."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.hq_actions import catalog_payload

        from ._helpers import available_actions

        return jsonify(catalog_payload(available_actions(get_db()))), 200
    except Exception as exc:
        logging.exception("hq actions catalog error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/hq/actions/available", methods=["PUT"])
def hq_actions_set_available():
    """Body ``{actions: [name, …]}`` — the catalog actions HQ may use.

    Names outside the catalog are rejected (400), not silently dropped: a
    request for a never-offered action is a caller bug worth seeing. Returns
    the catalog payload as ``GET /hq/actions`` would.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.hq_settings import set_hq_available_actions
        from pathly_orchestrator.hq_actions import (
            BY_NAME,
            catalog_payload,
            normalize_names,
        )

        body = request.get_json(silent=True) or {}
        names = body.get("actions")
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            return jsonify({"error": "'actions' must be a list of action names"}), 400
        unknown = sorted({n for n in names if n not in BY_NAME})
        if unknown:
            return jsonify({"error": f"not HQ actions: {', '.join(unknown)}"}), 400
        conn = get_db()
        kept = normalize_names(names)
        set_hq_available_actions(conn, kept)
        return jsonify(catalog_payload(kept)), 200
    except Exception as exc:
        logging.exception("hq actions availability error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
