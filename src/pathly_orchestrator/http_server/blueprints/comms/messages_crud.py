"""Message board writers — ack, answer, edit, delete, supersede, trash, restore.

``GET /comms`` and ``POST /comms/search`` are in ``messages_read.py``; ``POST /comms/post`` is in
``messages_write.py``. ``messages.py`` loads the three modules against the one blueprint.
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from ...sse import _broadcast_comms
from ._messages_bp import bp
from ._helpers import (
    BINDING_REFUSED,
    edit_stamp,
    read_json_body,
    refuse_agent_on_human_gate,
)
from ._supersede_on_post import refuse_agent_supersede


@bp.route("/comms/acknowledge", methods=["POST"])
def comms_acknowledge():
    """Mark a message as acknowledged by an agent."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import acknowledge_message as _ack

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        agent = data.get("agent", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )
        if not isinstance(agent, str) or not agent.strip():
            return jsonify({"error": "Field 'agent' must be a non-empty string"}), 400

        conn = _get_db()
        refused = refuse_agent_on_human_gate(conn, request, message_id)
        if refused:
            return refused
        _ack(conn, message_id=message_id, agent=agent)
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_acknowledge error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/answer", methods=["POST"])
def comms_answer():
    """Answer a pending question message."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import answer_question as _answer
        from pathly_orchestrator.http_server.chief_cite import answer_text as _text_of

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        question_id = data.get("question_id", "")
        answer_text = _text_of(data)
        if not isinstance(question_id, str) or not question_id.strip():
            return (
                jsonify({"error": "Field 'question_id' must be a non-empty string"}),
                400,
            )
        if not isinstance(answer_text, str) or not answer_text.strip():
            return jsonify({"error": "Field 'answer' must be a non-empty string"}), 400

        option_id = data.get("option_id")
        conn = _get_db()
        refused = refuse_agent_on_human_gate(conn, request, question_id)
        if refused:
            return refused
        answer_id = _answer(
            conn, question_id=question_id, answer_text=answer_text, option_id=option_id
        )

        # Instant cross-client sync: nudge every board subscribed to this question's
        # scope to reload, so the 'answered' state + chosen option appear at once
        # instead of waiting out the board's 5s fallback poll. Best-effort — a
        # broadcast failure must never fail an answer that already persisted.
        try:
            row = conn.execute(
                "SELECT board, scope FROM comms_messages WHERE id=?", (question_id,)
            ).fetchone()
            if row is not None:
                _broadcast_comms(
                    row["scope"],
                    {
                        "type": "COMMS_UPDATE",
                        "message_id": question_id,
                        "board": row["board"],
                        "scope": row["scope"],
                        "msg_type": "question",
                    },
                )
        except Exception:
            logging.debug("comms_answer broadcast failed", exc_info=True)

        return jsonify({"ok": True, "answer_id": answer_id}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        logging.exception("comms_answer error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/edit", methods=["POST"])
def comms_edit():
    """Edit a message's text in place."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            update_message_text as _update_text,
        )

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing or invalid JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )
        text = data.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Field 'text' must be a non-empty string"}), 400

        conn = _get_db()
        result = _update_text(conn, message_id, text.strip(), **edit_stamp(request))
        if result == "binding":
            return jsonify(error="binding directives are superseded, not edited"), 409
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_edit error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/delete", methods=["POST"])
def comms_delete():
    """Retract (soft-delete) a message."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            soft_delete_message as _soft_delete,
        )

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )

        force = bool(data.get("force", False))
        conn = _get_db()
        refused = refuse_agent_on_human_gate(conn, request, message_id)
        if refused:
            return refused
        result = _soft_delete(conn, message_id, force=force)
        if result == "binding":
            return jsonify(error=BINDING_REFUSED), 403
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404
        if result == "locked":
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Message already read by an agent — cannot retract",
                    }
                ),
                409,
            )
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_delete error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/supersede", methods=["POST"])
def comms_supersede():
    """Mark a decision as superseded by a newer one."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import supersede_message as _supersede

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        old_id = data.get("old_id", "")
        new_id = data.get("new_id", "")
        if not isinstance(old_id, str) or not old_id.strip():
            return jsonify({"error": "Field 'old_id' must be a non-empty string"}), 400
        if not isinstance(new_id, str) or not new_id.strip():
            return jsonify({"error": "Field 'new_id' must be a non-empty string"}), 400

        conn = _get_db()
        refused = refuse_agent_supersede(conn, old_id)
        if refused:
            return refused
        result = _supersede(conn, old_id=old_id, new_id=new_id)
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404
        if result == "already_superseded":
            return jsonify({"ok": False, "error": "Message already superseded"}), 409
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_supersede error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/trash", methods=["GET"])
def comms_trash():
    """List trashed messages for a scope."""
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
    """Restore trashed messages."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import restore_messages as _restore

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_ids = data.get("message_ids")
        if not isinstance(message_ids, list) or not message_ids:
            return (
                jsonify({"error": "Field 'message_ids' must be a non-empty list"}),
                400,
            )
        if not all(isinstance(i, str) for i in message_ids):
            return (
                jsonify({"error": "Field 'message_ids' must be a list of strings"}),
                400,
            )

        conn = _get_db()
        _restore(conn, message_ids=message_ids)
        return jsonify({"ok": True, "restored": len(message_ids)}), 200
    except Exception as exc:
        logging.exception("comms_restore error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
