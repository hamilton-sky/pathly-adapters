"""Communication board endpoints (/comms/*)."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ..sse import _broadcast_comms

bp = Blueprint("comms", __name__)


@bp.route("/comms/post", methods=["POST"])
def comms_post():
    """Post a message to a board.

    Required body fields: feature, from, type, text.
    Optional: scope (default 'feature'), to, options, reply_to, stage, conv.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message
        from pathly_orchestrator.runner.embeddings import embed_async as _embed_async

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"feature", "from", "type", "text"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        feature = data.get("feature", "")
        from_agent = data.get("from", "")
        msg_type = data.get("type", "")
        text = data.get("text", "")

        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400
        if not isinstance(from_agent, str) or not from_agent.strip():
            return jsonify({"error": "Field 'from' must be a non-empty string"}), 400
        if not isinstance(msg_type, str) or not msg_type.strip():
            return jsonify({"error": "Field 'type' must be a non-empty string"}), 400
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Field 'text' must be a non-empty string"}), 400

        # SPEC convention: board = tier (feature|project|global); scope = identifier.
        board = data.get("board", "feature")
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"
        scope = data.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            scope = "global" if board == "global" else feature

        to_agent = data.get("to", "*") or "*"
        options = data.get("options")
        reply_to = data.get("reply_to")
        stage = data.get("stage")
        conv = data.get("conv")

        if options is not None and not isinstance(options, list):
            return jsonify({"error": "Field 'options' must be a list or null"}), 400
        if conv is not None and not isinstance(conv, int):
            return jsonify({"error": "Field 'conv' must be an integer or null"}), 400

        conn = _get_db()
        message_id = _post_message(
            conn,
            board=board,
            scope=scope,
            from_agent=from_agent,
            to_agent=to_agent,
            type=msg_type,
            text=text,
            options=options,
            reply_to=reply_to,
            stage=stage,
            conv=conv,
        )

        _embed_async(message_id, text)

        _broadcast_comms(scope, {
            "type": "COMMS_UPDATE",
            "message_id": message_id,
            "feature": feature,
            "board": board,
            "scope": scope,
            "msg_type": msg_type,
        })

        return jsonify({"ok": True, "message_id": message_id}), 200
    except Exception as exc:
        logging.exception("comms_post error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms", methods=["GET"])
def comms_get():
    """Fetch messages for a feature board.

    Query params: feature (required), scope (default 'feature'),
    type (optional), status (optional), limit (default 50).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import get_messages as _get_messages

        feature = request.args.get("feature", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400

        board = (request.args.get("board") or "feature").strip() or "feature"
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = (request.args.get("scope") or feature).strip() or feature
        msg_type = request.args.get("type") or None
        status = request.args.get("status") or None
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50

        conn = _get_db()
        messages = _get_messages(
            conn,
            board=board,
            scope=scope,
            type=msg_type,
            status=status,
            limit=limit,
        )
        return jsonify(messages), 200
    except Exception as exc:
        logging.exception("comms_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/search", methods=["POST"])
def comms_search():
    """Semantic search across boards.

    Required body fields: query, feature.
    Optional: scope (default 'feature'), k (default 5).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import search_by_embedding as _search
        from pathly_orchestrator.runner.embeddings import embed as _embed

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        query = data.get("query", "")
        feature = data.get("feature", "")
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Field 'query' must be a non-empty string"}), 400
        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400

        board = data.get("board", "feature")
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = data.get("scope") or feature
        k = data.get("k", 5)
        if not isinstance(k, int) or k <= 0:
            k = 5

        embedding = _embed(query)
        conn = _get_db()
        if embedding is not None:
            results = _search(conn, embedding=embedding, boards=[board], scopes=[scope], k=k)
        else:
            from pathly_orchestrator.db.queries.comms import get_messages as _get_messages
            results = _get_messages(conn, board=board, scope=scope, limit=k)

        return jsonify(results), 200
    except Exception as exc:
        logging.exception("comms_search error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/acknowledge", methods=["POST"])
def comms_acknowledge():
    """Mark a message as acknowledged by an agent.

    Required body fields: message_id, agent.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import acknowledge_message as _ack

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        agent = data.get("agent", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400
        if not isinstance(agent, str) or not agent.strip():
            return jsonify({"error": "Field 'agent' must be a non-empty string"}), 400

        conn = _get_db()
        _ack(conn, message_id=message_id, agent=agent)
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_acknowledge error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/answer", methods=["POST"])
def comms_answer():
    """Answer a pending question message.

    Required body fields: question_id, answer.
    Optional: option_id.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import answer_question as _answer

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        question_id = data.get("question_id", "")
        answer_text = data.get("answer", "")
        if not isinstance(question_id, str) or not question_id.strip():
            return jsonify({"error": "Field 'question_id' must be a non-empty string"}), 400
        if not isinstance(answer_text, str) or not answer_text.strip():
            return jsonify({"error": "Field 'answer' must be a non-empty string"}), 400

        option_id = data.get("option_id")

        conn = _get_db()
        answer_id = _answer(conn, question_id=question_id, answer_text=answer_text, option_id=option_id)
        return jsonify({"ok": True, "answer_id": answer_id}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        logging.exception("comms_answer error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/attach", methods=["POST"])
def comms_attach():
    """Attach a file or URL artifact to a message. (Not implemented in this phase.)"""
    return jsonify({"error": "Artifact attachments are not implemented in this phase"}), 501


@bp.route("/comms/trash", methods=["GET"])
def comms_trash():
    """List trashed messages for a scope.

    Query param: scope (required).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import get_trash as _get_trash

        scope = request.args.get("scope", "").strip()
        if not scope:
            return jsonify({"error": "Query parameter 'scope' is required"}), 400

        conn = _get_db()
        messages = _get_trash(conn, scope=scope)
        return jsonify(messages), 200
    except Exception as exc:
        logging.exception("comms_trash error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/restore", methods=["POST"])
def comms_restore():
    """Restore trashed messages.

    Required body field: message_ids (list of strings).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import restore_messages as _restore

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_ids = data.get("message_ids")
        if not isinstance(message_ids, list) or not message_ids:
            return jsonify({"error": "Field 'message_ids' must be a non-empty list"}), 400
        if not all(isinstance(i, str) for i in message_ids):
            return jsonify({"error": "Field 'message_ids' must be a list of strings"}), 400

        conn = _get_db()
        _restore(conn, message_ids=message_ids)
        return jsonify({"ok": True, "restored": len(message_ids)}), 200
    except Exception as exc:
        logging.exception("comms_restore error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


# board_scope: project_root is normalized to forward-slash form to match the
# key used at injection time (runner/comms_context.retrieve_board_context),
# otherwise a UI-set scope would be stored under a different key than the FSM
# reads and the toggle would silently have no effect.
def _norm_project_root(project_root: str) -> str:
    return project_root.replace("\\", "/").rstrip("/")


@bp.route("/comms/scope", methods=["GET"])
def comms_scope_get():
    """Return the board_scope for a feature.

    Query params: feature (required), project_root (required).
    Returns {"feature": bool, "project": bool, "global": bool},
    defaulting to all-enabled when never set.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import get_board_scope as _get_scope

        feature = request.args.get("feature", "").strip()
        project_root = request.args.get("project_root", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400
        if not project_root:
            return jsonify({"error": "Query parameter 'project_root' is required"}), 400

        conn = _get_db()
        scope = _get_scope(conn, project_root=_norm_project_root(project_root), feature=feature)
        return jsonify(scope), 200
    except Exception as exc:
        logging.exception("comms_scope_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/scope", methods=["POST"])
def comms_scope_set():
    """Persist the board_scope for a feature.

    Required body fields: feature, project_root, scope (object containing any
    of 'feature'/'project'/'global' → bool). A partial scope only flips the
    named keys. Returns the merged, persisted scope.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_board_scope as _get_scope,
            set_board_scope as _set_scope,
        )

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        feature = data.get("feature", "")
        project_root = data.get("project_root", "")
        scope = data.get("scope")
        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400
        if not isinstance(project_root, str) or not project_root.strip():
            return jsonify({"error": "Field 'project_root' must be a non-empty string"}), 400
        if not isinstance(scope, dict):
            return jsonify({"error": "Field 'scope' must be an object"}), 400

        allowed = {"feature", "project", "global"}
        updates = {k: bool(v) for k, v in scope.items() if k in allowed}
        if not updates:
            return jsonify({
                "error": "Field 'scope' must contain at least one of: feature, project, global"
            }), 400

        conn = _get_db()
        norm_root = _norm_project_root(project_root)
        # Merge onto the existing (or default) scope so a partial update leaves
        # the other tiers untouched.
        merged = _get_scope(conn, project_root=norm_root, feature=feature)
        merged.update(updates)
        _set_scope(conn, project_root=norm_root, feature=feature, scope_dict=merged)
        return jsonify(merged), 200
    except Exception as exc:
        logging.exception("comms_scope_set error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/delete", methods=["POST"])
def comms_delete():
    """Retract (soft-delete) a message — only while no agent has read it.

    Required body field: message_id.
    Returns 200 {ok:true} on delete, 409 if an agent has already read it
    (locked), 404 if the message does not exist.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import soft_delete_message as _soft_delete

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400

        conn = _get_db()
        result = _soft_delete(conn, message_id)
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404
        if result == "locked":
            return jsonify({"ok": False, "error": "Message already read by an agent — cannot retract"}), 409
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_delete error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
