"""CRUD message board endpoints — GET /comms, search, ack, answer, edit, delete, trash, restore."""

from __future__ import annotations

import logging

from flask import jsonify, request

from ...sse import _broadcast_comms
from ._messages_bp import bp


@bp.route("/comms", methods=["GET"])
def comms_get():
    """Fetch messages for a feature board."""
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
            # Board feed: never let run churn evict the (bounded) goals/tasks out of the
            # newest-`limit` window — the Goals & Tasks view needs them all, and the Messages
            # thread filters them out anyway. Only applies when not filtering by an explicit type.
            include_structural=(msg_type is None),
        )
        return jsonify(messages), 200
    except Exception as exc:
        logging.exception("comms_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


# Bounds for /comms/search hardening: a search box never needs a multi-KB query
# (which would hog the process-wide embedding-model lock) or hundreds of results.
_MAX_QUERY_LEN = 512
_MAX_K = 50


@bp.route("/comms/search", methods=["POST"])
def comms_search():
    """Hybrid (BM25 + semantic) search across boards.

    Semantic hits are floored at SEMANTIC_DISTANCE_CEILING; keyword hits bypass the
    floor. A query matching nothing returns [] — results are never padded with
    recent messages (that padding made every query "match" the newest rows).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import search_by_embedding as _search
        from pathly_orchestrator.db.queries.comms import (
            search_by_hybrid as _search_hybrid,
        )
        from pathly_orchestrator.db.queries.comms import (
            search_by_keyword as _search_keyword,
        )
        from pathly_orchestrator.db.queries.comms_embeddings import (
            SEMANTIC_DISTANCE_CEILING as _CEILING,
        )
        from pathly_orchestrator.runner.embeddings import embed as _embed

        # silent=True → a malformed/empty body yields None (a clean 400), not a
        # werkzeug BadRequest bubbling into the generic 500 that echoes exception text.
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Missing or malformed JSON body"}), 400

        query = data.get("query", "")
        feature = data.get("feature", "")
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Field 'query' must be a non-empty string"}), 400
        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400
        # Cap length before embedding: a multi-KB query is never a real search and
        # would hold the process-wide model lock, stalling every other embed.
        query = query[:_MAX_QUERY_LEN]

        board = data.get("board", "feature")
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = data.get("scope") or feature
        # bool is an int subclass — reject it so k=true can't silently become LIMIT 1.
        k = data.get("k", 5)
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            k = 5
        k = min(k, _MAX_K)

        mode = data.get("mode", "hybrid")
        if mode not in ("hybrid", "semantic", "keyword"):
            mode = "hybrid"

        # Only the semantic/hybrid arms need a query vector — keyword mode skips the
        # model forward-pass entirely.
        embedding = _embed(query) if mode != "keyword" else None
        conn = _get_db()

        if mode == "keyword":
            results = _search_keyword(conn, query, [board], [scope], k)
        elif mode == "semantic":
            if embedding is not None:
                results = _search(
                    conn,
                    embedding=embedding,
                    boards=[board],
                    scopes=[scope],
                    k=k,
                    max_distance=_CEILING,
                )
            else:
                # No embedding model → degrade to keyword matching, which is still
                # honest; recency rows are not matches.
                results = _search_keyword(conn, query, [board], [scope], k)
        else:
            results = _search_hybrid(
                conn, query, embedding, [board], [scope], k, max_distance=_CEILING
            )

        return jsonify(results), 200
    except Exception as exc:
        logging.exception("comms_search error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/acknowledge", methods=["POST"])
def comms_acknowledge():
    """Mark a message as acknowledged by an agent."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import acknowledge_message as _ack

        data = request.get_json()
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

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        question_id = data.get("question_id", "")
        answer_text = data.get("answer", "")
        if not isinstance(question_id, str) or not question_id.strip():
            return (
                jsonify({"error": "Field 'question_id' must be a non-empty string"}),
                400,
            )
        if not isinstance(answer_text, str) or not answer_text.strip():
            return jsonify({"error": "Field 'answer' must be a non-empty string"}), 400

        option_id = data.get("option_id")
        conn = _get_db()
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

        # Windows clients may POST cp1252-encoded JSON (a stray em-dash → byte 0x97), which strict
        # UTF-8 parsing rejects with a 500 — dropping the edit. Decode leniently: UTF-8 first, then
        # cp1252 (mirrors comms_post) so an edit carrying a smart-quote/em-dash lands cleanly.
        import json as _json

        raw = request.get_data()
        data = None
        if raw:
            for _enc in ("utf-8", "cp1252"):
                try:
                    data = _json.loads(raw.decode(_enc))
                    break
                except (UnicodeDecodeError, ValueError):
                    continue
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
        result = _update_text(conn, message_id, text.strip())
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

        data = request.get_json()
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
        result = _soft_delete(conn, message_id, force=force)
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

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        old_id = data.get("old_id", "")
        new_id = data.get("new_id", "")
        if not isinstance(old_id, str) or not old_id.strip():
            return jsonify({"error": "Field 'old_id' must be a non-empty string"}), 400
        if not isinstance(new_id, str) or not new_id.strip():
            return jsonify({"error": "Field 'new_id' must be a non-empty string"}), 400

        conn = _get_db()
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

        data = request.get_json()
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
