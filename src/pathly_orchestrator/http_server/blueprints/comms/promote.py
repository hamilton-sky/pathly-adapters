"""Cross-tier message promotion endpoint (POST /comms/promote).

Copies one ``decision``/``constraint`` from a lower board tier onto a higher one
(feature→project, feature→global, project→global), leaving the source row in
place as the audit record and linking the two through the ``promoted_to`` /
``promoted_from`` / ``original_scope`` columns.

This lives in its own file rather than in ``messages_write.py`` for the
one-domain-per-file rule: promotion is not a post, it is a copy with its own
type gate, direction gate and permission set (``_PROMOTE_WRITERS``).

The DB work is ``db/queries/comms_promote.py``; this layer owns the two things
``db/`` may not reach for — the permission gate and the embedding of the new row.
Embedding is not optional: an unembedded promotion is invisible to the semantic
retrieval that reads the higher boards, which is the only reason to promote at all.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from ...sse import _broadcast_comms
from ._helpers import (
    _EMBED_TYPES,
    _PROMOTE_WRITERS,
    check_promote_permission,
    norm_project_root,
    read_json_body,
)

bp = Blueprint("comms_promote", __name__)

_BOARDS = ("feature", "project", "global")


def _resolve_target_scope(data: dict, to_board: str) -> str:
    """Scope key for the target board, following the board's own conventions.

    The global board is always keyed by the literal ``"global"``, and the project
    board by the NORMALIZED project_root (never the literal ``"project"``) —
    the same keys ``runner/comms_context.py`` reads context from. Getting this
    wrong does not error, it just parks the promoted row on a board nobody reads.
    """
    explicit = data.get("to_scope")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if to_board == "global":
        return "global"
    project_root = str(data.get("project_root", "") or "").strip()
    return norm_project_root(project_root) if project_root else ""


@bp.route("/comms/promote", methods=["POST"])
def comms_promote():
    """Promote a decision/constraint to a higher board tier."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms_promote import (
            PROMOTABLE_TYPES as _PROMOTABLE,
            promote_message as _promote_message,
        )
        from pathly_orchestrator.runner.embeddings import embed_async as _embed_async

        # silent=True → a malformed body yields a clean 400 instead of a werkzeug
        # BadRequest bubbling into the generic 500 that echoes exception text.
        data = read_json_body()
        if not isinstance(data, dict):
            return jsonify({"error": "Missing or malformed JSON body"}), 400

        message_id = data.get("message_id")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )
        message_id = message_id.strip()

        from_agent = data.get("from")
        if not isinstance(from_agent, str) or not from_agent.strip():
            return jsonify({"error": "Field 'from' must be a non-empty string"}), 400
        from_agent = from_agent.strip()

        to_board = data.get("to_board")
        if not isinstance(to_board, str) or to_board.strip() not in _BOARDS:
            return (
                jsonify(
                    {"error": "Field 'to_board' must be one of: " + ", ".join(_BOARDS)}
                ),
                400,
            )
        to_board = to_board.strip()

        if not check_promote_permission(from_agent):
            return (
                jsonify(
                    {
                        "error": f"Role '{from_agent}' cannot promote messages",
                        "allowed_roles": sorted(_PROMOTE_WRITERS),
                    }
                ),
                403,
            )

        to_scope = _resolve_target_scope(data, to_board)
        if not to_scope:
            return (
                jsonify(
                    {
                        "error": "Field 'to_scope' is required for this target board "
                        "(or pass 'project_root' for to_board='project')"
                    }
                ),
                400,
            )

        conn = _get_db()
        result = _promote_message(
            conn,
            message_id=message_id,
            to_board=to_board,
            to_scope=to_scope,
            promoted_by=from_agent,
        )

        status = result.get("status")
        if status == "not_found":
            return (
                jsonify({"ok": False, "error": f"Message '{message_id}' not found"}),
                404,
            )
        if status == "not_promotable":
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": (
                            f"Type '{result.get('type')}' is not promotable — "
                            "only a distilled conclusion crosses tiers"
                        ),
                        "promotable_types": sorted(_PROMOTABLE),
                    }
                ),
                400,
            )
        if status == "not_upward":
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": (
                            f"Promotion must be strictly upward: "
                            f"'{result.get('from_board')}' → '{result.get('to_board')}' is not"
                        ),
                        "from_board": result.get("from_board"),
                        "to_board": result.get("to_board"),
                    }
                ),
                400,
            )

        already = bool(result.get("already_promoted"))
        new_id = result["message_id"]

        # Mirrors POST /comms/post: a promoted row that is never embedded cannot be
        # reached by the semantic arm of board search or by context injection on the
        # target tier — it would sit on the global board unreadable by every agent
        # the promotion was meant to inform. Skipped on an idempotent hit: that row's
        # vector was already stored by the original promotion.
        if not already:
            if result.get("type") in _EMBED_TYPES:
                _embed_async(new_id, result.get("text") or "")

            _broadcast_comms(
                to_scope,
                {
                    "type": "COMMS_UPDATE",
                    "event": "promoted",
                    "message_id": new_id,
                    "source_id": message_id,
                    "board": to_board,
                    "scope": to_scope,
                    "msg_type": result.get("type"),
                },
            )

        return (
            jsonify(
                {
                    "ok": True,
                    "message_id": new_id,
                    "source_id": message_id,
                    "board": result.get("board"),
                    "scope": result.get("scope"),
                    "type": result.get("type"),
                    "already_promoted": already,
                }
            ),
            200,
        )
    except Exception as exc:
        logging.exception("comms_promote error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
