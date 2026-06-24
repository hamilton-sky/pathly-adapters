"""Core message board endpoints (/comms/post, GET /comms, search, ack, answer, edit, delete…)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms
from ._helpers import (
    _EMBED_TYPES,
    check_write_permission,
    extract_artifact_path,
    guess_artifact_type,
    norm_project_root,
)

bp = Blueprint("comms_messages", __name__)


@bp.route("/comms/post", methods=["POST"])
def comms_post():
    """Post a message to a board."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_write_permissions as _get_write_perms,
        )
        from pathly_orchestrator.db.queries.comms import post_message as _post_message
        from pathly_orchestrator.runner.embeddings import embed_async as _embed_async

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"feature", "from", "type", "text"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

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

        board = data.get("board", "feature")
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"
        scope = data.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            scope = "global" if board == "global" else feature

        project_root = str(data.get("project_root", "") or "").strip()
        norm_root = norm_project_root(project_root) if project_root else ""
        conn = _get_db()
        perm_table = _get_write_perms(conn, norm_root)

        if not check_write_permission(from_agent, board, perm_table=perm_table):
            allowed = sorted(
                perm_table.get(board)
                or (
                    {"director", "human"}
                    if board == "global"
                    else {
                        "tester",
                        "reviewer",
                        "explorer",
                        "architect",
                        "planner",
                        "designer",
                        "director",
                        "human",
                    }
                )
            )
            return (
                jsonify(
                    {
                        "error": f"Role '{from_agent}' cannot write to '{board}' scope",
                        "allowed_roles": allowed,
                    }
                ),
                403,
            )

        to_agent = data.get("to", "*") or "*"
        options = data.get("options")
        reply_to = data.get("reply_to")
        stage = data.get("stage")
        conv = data.get("conv")
        depends_on = data.get("depends_on")
        goal_id = data.get("goal_id")
        executor = data.get("executor")
        artifact_path = data.get("artifact_path") or None
        artifact_type = data.get("artifact_type") or None
        if msg_type == "artifact" and not (
            isinstance(artifact_path, str) and artifact_path.strip()
        ):
            recovered = extract_artifact_path(text)
            if recovered:
                artifact_path = recovered
                if not artifact_type:
                    artifact_type = guess_artifact_type(recovered)

        if options is not None and not isinstance(options, list):
            return jsonify({"error": "Field 'options' must be a list or null"}), 400
        if conv is not None and not isinstance(conv, int):
            return jsonify({"error": "Field 'conv' must be an integer or null"}), 400
        if depends_on is not None and (
            not isinstance(depends_on, list)
            or not all(isinstance(d, str) for d in depends_on)
        ):
            return (
                jsonify(
                    {"error": "Field 'depends_on' must be a list of strings or null"}
                ),
                400,
            )
        if goal_id is not None and not isinstance(goal_id, str):
            return jsonify({"error": "Field 'goal_id' must be a string or null"}), 400
        if executor is not None and not isinstance(executor, str):
            return jsonify({"error": "Field 'executor' must be a string or null"}), 400
        summary_backend = data.get("summary_backend")
        if summary_backend is not None and summary_backend not in (
            "minilm",
            "ollama",
            "haiku",
        ):
            return (
                jsonify(
                    {
                        "error": "Field 'summary_backend' must be one of minilm|ollama|haiku or null"
                    }
                ),
                400,
            )
        # embed_summary (§3a): when an UPLOADED .md is summarized, feed the generated
        # summary into the message's search vector + display text so it surfaces in the
        # 💡 semantic channel / retrieve_board_context. Set by the upload UI; agent
        # posts leave it false (their summary stays catalog-only).
        embed_summary = bool(data.get("embed_summary"))
        context_refs = data.get("context_refs")
        if context_refs is not None and (
            not isinstance(context_refs, list)
            or not all(
                isinstance(r, dict)
                and isinstance(r.get("artifact"), str)
                and (r.get("anchor") is None or isinstance(r.get("anchor"), str))
                for r in context_refs
            )
        ):
            return (
                jsonify(
                    {
                        "error": "Field 'context_refs' must be a list of {artifact:str, anchor?:str} objects or null"
                    }
                ),
                400,
            )

        if context_refs:
            try:
                from pathly_orchestrator.db.queries.comms import (
                    find_or_create_artifact_by_path as _find_artifact,
                    get_section as _get_section,
                )
                from pathly_orchestrator.runner.hydrate import (
                    ensure_indexed as _ensure_indexed,
                    safe_plan_path as _safe_plan_path,
                )
                import os as _os

                _project_root = project_root or _os.getcwd()
                resolved_refs = []
                for ref in context_refs:
                    art_name = ref.get("artifact", "")
                    anc = ref.get("anchor")
                    if not art_name or anc is None:
                        resolved_refs.append(ref)
                        continue
                    try:
                        art_path = _safe_plan_path(scope, art_name, _project_root)
                        if art_path is None:
                            resolved_refs.append(ref)
                            continue
                        _ensure_indexed(conn, scope, art_path, _project_root)
                        art_row = _find_artifact(conn, scope, art_path)
                        if art_row is None:
                            resolved_refs.append(ref)
                            continue
                        sec = _get_section(conn, art_row["id"], anc)
                        if sec is None:
                            resolved_refs.append({"artifact": art_name, "anchor": None})
                            logging.warning(
                                "context_refs validate-at-write: anchor %r not found in %s "
                                "(scope=%s) — rewriting to whole-file",
                                anc,
                                art_name,
                                scope,
                            )
                            try:
                                _post_message(
                                    conn,
                                    board=board,
                                    scope=scope,
                                    from_agent="system",
                                    type="nudge",
                                    text=(
                                        f"⚠ context_refs validate-at-write: "
                                        f"{art_name} §{anc} unresolved → hydrating whole file. "
                                        f"Check heading conventions (§3.1)."
                                    ),
                                )
                            except Exception:
                                pass
                        else:
                            resolved_refs.append(ref)
                    except Exception:
                        resolved_refs.append(ref)
                context_refs = resolved_refs
            except Exception:
                pass

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
            depends_on=depends_on,
            artifact_path=artifact_path if isinstance(artifact_path, str) else None,
            artifact_type=artifact_type if isinstance(artifact_type, str) else None,
            goal_id=goal_id,
            executor=executor,
            context_refs=context_refs,
        )

        if (
            msg_type == "artifact"
            and isinstance(artifact_path, str)
            and artifact_path.strip()
        ):
            try:
                from pathly_orchestrator.db.queries.comms import (
                    insert_artifact as _insert_artifact,
                )

                art_id = _insert_artifact(
                    conn,
                    message_id=message_id,
                    path=artifact_path,
                    type=artifact_type if isinstance(artifact_type, str) else None,
                    summary=text,
                    created_by=from_agent,
                )
                try:
                    from pathly_orchestrator.runner.hydrate import (
                        index_artifact_async as _index_async,
                    )

                    _index_async(
                        art_id,
                        artifact_path,
                        scope=scope,
                        backend=summary_backend,
                        broadcast_fn=lambda _p: _broadcast_comms(scope, _p),
                        embed_summary=embed_summary,
                    )
                except Exception:
                    logging.debug("index_artifact_async (post) failed", exc_info=True)
            except Exception:
                logging.debug("comms_artifacts insert (post) failed", exc_info=True)

        if msg_type in _EMBED_TYPES:
            _embed_async(message_id, text)

        _broadcast_comms(
            scope,
            {
                "type": "COMMS_UPDATE",
                "message_id": message_id,
                "feature": feature,
                "board": board,
                "scope": scope,
                "msg_type": msg_type,
            },
        )

        return jsonify({"ok": True, "message_id": message_id}), 200
    except Exception as exc:
        logging.exception("comms_post error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


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
        )
        return jsonify(messages), 200
    except Exception as exc:
        logging.exception("comms_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/search", methods=["POST"])
def comms_search():
    """Semantic search across boards."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import search_by_embedding as _search
        from pathly_orchestrator.db.queries.comms import (
            search_by_hybrid as _search_hybrid,
        )
        from pathly_orchestrator.db.queries.comms import (
            search_by_keyword as _search_keyword,
        )
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

        mode = data.get("mode", "hybrid")
        if mode not in ("hybrid", "semantic", "keyword"):
            mode = "hybrid"

        embedding = _embed(query)
        conn = _get_db()

        if mode == "keyword":
            results = _search_keyword(conn, query, [board], [scope], k)
        elif mode == "semantic":
            if embedding is not None:
                results = _search(
                    conn, embedding=embedding, boards=[board], scopes=[scope], k=k
                )
            else:
                from pathly_orchestrator.db.queries.comms import (
                    get_messages as _get_messages,
                )

                results = _get_messages(conn, board=board, scope=scope, limit=k)
        else:
            results = _search_hybrid(conn, query, embedding, [board], [scope], k)
            if not results:
                from pathly_orchestrator.db.queries.comms import (
                    get_messages as _get_messages,
                )

                results = _get_messages(conn, board=board, scope=scope, limit=k)

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

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

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
