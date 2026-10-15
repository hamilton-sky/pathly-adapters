"""HQ context endpoint (hq-copilot ticket 03) — GET /hq/context.

Returns the assembled board packet the HQ copilot answers from, for the
Studio context manifest (ticket 06) and as a debugging surface. Read-only.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("hq_context", __name__)


def _board_known(conn, board_id: str) -> bool:
    """A board is known when the scope has any messages or any runs.

    Unknown board -> 404, never an empty 200 (ticket 03). An empty-but-known
    board still returns its (empty) packet with a 200.
    """
    msg = conn.execute(
        "SELECT 1 FROM comms_messages WHERE scope=? AND deleted_at IS NULL LIMIT 1",
        (board_id,),
    ).fetchone()
    if msg is not None:
        return True
    run = conn.execute(
        "SELECT 1 FROM run_history WHERE feature=? LIMIT 1",
        (board_id,),
    ).fetchone()
    return run is not None


@bp.route("/hq/context", methods=["GET"])
def hq_context():
    """Return the HQ context packet for ``board`` (a scope id).

    Query params: ``board`` (required), ``project_root`` (optional — scopes
    the live-runs section; without it that section is reported cut),
    ``model`` (optional — the HQ model id to check; defaults to the
    ``hq.default_model`` setting).
    200 ``{packet, tokens_est, sections: [{name, included, cut_reason}],
    budget, model, eligible_model, unavailable}``; 400 when ``board`` is
    missing; 404 for an unknown board; 503 when the packet cannot be
    assembled. (``POST /hq/prompt`` is what Studio sends the model; this is
    the inspection/debugging view of the same packet.)
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.hq_settings import (
            get_hq_budget_tokens,
            get_hq_default_model,
        )
        from pathly_orchestrator.hq_context import (
            HQContextUnavailable,
            assemble_packet,
        )

        from ._helpers import manifest

        board_id = (request.args.get("board") or "").strip()
        if not board_id:
            return jsonify({"error": "Query parameter 'board' is required"}), 400
        project_root = (request.args.get("project_root") or "").strip() or None
        # ?sections=questions,goals — same choice as POST /hq/prompt's list.
        raw_sections = request.args.get("sections")
        sections = (
            [s.strip() for s in raw_sections.split(",") if s.strip()]
            if raw_sections is not None
            else None
        )

        conn = get_db()
        if not _board_known(conn, board_id):
            return jsonify({"error": f"unknown board '{board_id}'"}), 404

        budget = get_hq_budget_tokens(conn)
        model_id = (request.args.get("model") or "").strip() or get_hq_default_model(
            conn
        )
        try:
            pkt = assemble_packet(board_id, budget, project_root, sections)
        except HQContextUnavailable as exc:
            return jsonify({"error": str(exc), "type": "HQContextUnavailable"}), 503

        return (
            jsonify({"packet": pkt.text, **manifest(pkt, model_id, budget, board_id)}),
            200,
        )
    except Exception as exc:
        logging.exception("hq context error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
