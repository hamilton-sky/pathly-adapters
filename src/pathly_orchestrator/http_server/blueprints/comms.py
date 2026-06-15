"""Communication board endpoints (/comms/*)."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ..sse import _broadcast_comms, _broadcast_runner

bp = Blueprint("comms", __name__)

_EMBED_TYPES: frozenset[str] = frozenset({
    "decision", "discovery", "constraint", "warning", "escalation", "artifact"
})

_PROJECT_WRITERS: frozenset[str] = frozenset({
    "tester", "reviewer", "explorer", "architect",
    "planner", "designer", "director", "human",
})
_GLOBAL_WRITERS: frozenset[str] = frozenset({"director", "human"})


def _check_write_permission(
    from_agent: str, board: str, perm_table: dict | None = None
) -> bool:
    """Return True when from_agent is allowed to write to the given board tier.

    perm_table, when provided, is the resolved override table from get_write_permissions()
    (keys: 'feature'|'project'|'global', values: list[str] or ['*']).  Falls back to the
    module-level frozensets when perm_table is absent or missing the tier key.
    """
    if board == "feature":
        return True
    if perm_table is not None:
        roles = perm_table.get(board)
        if roles is not None:
            return "*" in roles or from_agent in roles
    if board == "project":
        return from_agent in _PROJECT_WRITERS
    if board == "global":
        return from_agent in _GLOBAL_WRITERS
    return False


@bp.route("/comms/post", methods=["POST"])
def comms_post():
    """Post a message to a board.

    Required body fields: feature, from, type, text.
    Optional: scope (default 'feature'), to, options, reply_to, stage, conv.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import get_write_permissions as _get_write_perms
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

        project_root = str(data.get("project_root", "") or "").strip()
        norm_root = _norm_project_root(project_root) if project_root else ""
        conn = _get_db()
        perm_table = _get_write_perms(conn, norm_root)

        if not _check_write_permission(from_agent, board, perm_table=perm_table):
            allowed = sorted(perm_table.get(board) or (
                _GLOBAL_WRITERS if board == "global" else _PROJECT_WRITERS
            ))
            return jsonify({
                "error": f"Role '{from_agent}' cannot write to '{board}' scope",
                "allowed_roles": allowed,
            }), 403

        to_agent = data.get("to", "*") or "*"
        options = data.get("options")
        reply_to = data.get("reply_to")
        stage = data.get("stage")
        conv = data.get("conv")
        depends_on = data.get("depends_on")

        if options is not None and not isinstance(options, list):
            return jsonify({"error": "Field 'options' must be a list or null"}), 400
        if conv is not None and not isinstance(conv, int):
            return jsonify({"error": "Field 'conv' must be an integer or null"}), 400
        if depends_on is not None and (
            not isinstance(depends_on, list)
            or not all(isinstance(d, str) for d in depends_on)
        ):
            return jsonify({"error": "Field 'depends_on' must be a list of strings or null"}), 400
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
        )

        if msg_type in _EMBED_TYPES:
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
    Optional: scope (default 'feature'), k (default 5),
              mode ('hybrid'|'semantic'|'keyword', default 'hybrid').
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import search_by_embedding as _search
        from pathly_orchestrator.db.queries.comms import search_by_hybrid as _search_hybrid
        from pathly_orchestrator.db.queries.comms import search_by_keyword as _search_keyword
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
                results = _search(conn, embedding=embedding, boards=[board], scopes=[scope], k=k)
            else:
                from pathly_orchestrator.db.queries.comms import get_messages as _get_messages
                results = _get_messages(conn, board=board, scope=scope, limit=k)
        else:  # hybrid — fall back to recency when both BM25 and vec are absent (SPEC §26.7)
            results = _search_hybrid(conn, query, embedding, [board], [scope], k)
            if not results:
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


@bp.route("/comms/tasks", methods=["GET"])
def comms_tasks_get():
    """Fetch task messages for a feature.

    Query params: feature (required), ready=true (only unblocked tasks)
    or status=pending (all pending tasks regardless of readiness).
    Default when neither flag is set: all pending tasks.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import get_messages as _get_messages
        from pathly_orchestrator.db.queries.comms import get_ready_tasks as _get_ready_tasks

        feature = request.args.get("feature", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400

        board = (request.args.get("board") or "feature").strip() or "feature"
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = (request.args.get("scope") or feature).strip() or feature

        conn = _get_db()
        ready_flag = request.args.get("ready", "").strip().lower()
        if ready_flag == "true":
            tasks = _get_ready_tasks(conn, boards=[board], scopes=[scope])
        else:
            tasks = _get_messages(conn, board=board, scope=scope, type="task", status="pending")
        return jsonify(tasks), 200
    except Exception as exc:
        logging.exception("comms_tasks_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/tasks/complete", methods=["POST"])
def comms_tasks_complete():
    """Mark a task as done and broadcast newly-unblocked tasks.

    Required body fields: message_id.
    Optional: feature (used for the broadcast scope).
    Idempotent: completing an already-done task returns 200 with no change.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import complete_task as _complete_task

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400

        conn = _get_db()
        newly_ready = _complete_task(conn, message_id=message_id)

        scope = data.get("feature") or data.get("scope") or ""
        for nrid in newly_ready:
            _broadcast_comms(scope, {
                "type": "COMMS_UPDATE",
                "message_id": nrid,
                "event": "task_unblocked",
                "feature": scope,
            })

        return jsonify({"ok": True, "newly_ready": newly_ready}), 200
    except Exception as exc:
        logging.exception("comms_tasks_complete error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/tasks/claim", methods=["POST"])
def comms_tasks_claim():
    """Atomically claim a pending task (pending → in_progress).

    Required body fields: message_id, run_id.
    Returns 200 {"claimed": bool} — True if this caller won the claim,
    False if the task was already claimed, done, or failed.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import claim_task as _claim_task

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        run_id = data.get("run_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400
        if not isinstance(run_id, str) or not run_id.strip():
            return jsonify({"error": "Field 'run_id' must be a non-empty string"}), 400

        conn = _get_db()
        claimed = _claim_task(conn, message_id=message_id, run_id=run_id)
        return jsonify({"claimed": claimed}), 200
    except Exception as exc:
        logging.exception("comms_tasks_claim error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/tasks/fail", methods=["POST"])
def comms_tasks_fail():
    """Mark a task failed and cascade-block transitive dependents.

    Required body fields: message_id.
    Optional: reason (short error text).
    Returns 200 {"ok": true, "blocked": [...ids]}.
    Broadcasts COMMS_UPDATE task_failed for the failed task and task_blocked
    for each cascade-blocked dependent, scoped to the message's scope.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import fail_task as _fail_task

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400

        reason = data.get("reason") or ""

        conn = _get_db()

        row = conn.execute(
            "SELECT scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        scope = row["scope"] if row is not None else ""

        blocked = _fail_task(conn, message_id=message_id, reason=reason)

        _broadcast_comms(scope, {
            "type": "COMMS_UPDATE",
            "event": "task_failed",
            "message_id": message_id,
        })
        for bid in blocked:
            _broadcast_comms(scope, {
                "type": "COMMS_UPDATE",
                "event": "task_blocked",
                "message_id": bid,
            })

        return jsonify({"ok": True, "blocked": blocked}), 200
    except Exception as exc:
        logging.exception("comms_tasks_fail error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/attach", methods=["POST"])
def comms_attach():
    """Attach a file or URL artifact to an existing message.

    Required body fields: message_id, and at least one of artifact_path / artifact_url.
    Optional: artifact_type ('md'|'code'|'pdf'|'image'|'json'|'url'|'snippet').
    Returns 200 {ok, message_id} | 400 bad input | 404 message not found.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            attach_artifact_to_message as _attach,
        )

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return jsonify({"error": "Field 'message_id' must be a non-empty string"}), 400

        artifact_path = data.get("artifact_path")
        artifact_url = data.get("artifact_url")
        artifact_type = data.get("artifact_type")

        has_path = isinstance(artifact_path, str) and artifact_path.strip()
        has_url = isinstance(artifact_url, str) and artifact_url.strip()
        if not has_path and not has_url:
            return jsonify({
                "error": "Provide at least one of 'artifact_path' or 'artifact_url'"
            }), 400
        if artifact_type is not None and not isinstance(artifact_type, str):
            return jsonify({"error": "Field 'artifact_type' must be a string or null"}), 400

        conn = _get_db()
        row = conn.execute(
            "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        if row is None:
            return jsonify({"ok": False, "error": "Message not found"}), 404

        result = _attach(
            conn,
            message_id=message_id,
            artifact_path=artifact_path if has_path else None,
            artifact_type=artifact_type,
            artifact_url=artifact_url if has_url else None,
        )
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404

        _broadcast_comms(row["scope"], {
            "type": "COMMS_UPDATE",
            "message_id": message_id,
            "event": "artifact_attached",
            "board": row["board"],
            "scope": row["scope"],
            "artifact_type": artifact_type,
        })

        return jsonify({"ok": True, "message_id": message_id}), 200
    except Exception as exc:
        logging.exception("comms_attach error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


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


@bp.route("/comms/supersede", methods=["POST"])
def comms_supersede():
    """Mark a decision as superseded by a newer one.

    Required body fields: old_id, new_id.
    Returns 200 {ok:true} | 404 not found | 409 already superseded.
    """
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


@bp.route("/comms/permissions", methods=["GET"])
def comms_permissions():
    """Return the resolved write-permission table for a project.

    Query param: project_root (optional, defaults to empty string for global default).
    Returns a dict mapping board tier to allowed roles and any project overrides.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import get_write_permissions as _get_perms

        project_root = request.args.get("project_root", "").strip()
        norm_root = _norm_project_root(project_root) if project_root else ""

        conn = _get_db()
        perms = _get_perms(conn, norm_root)
        return jsonify(perms), 200
    except Exception as exc:
        logging.exception("comms_permissions error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/agent-context", methods=["POST"])
def comms_agent_context():
    """Return board context in BOARD-INFO mode (no flow state, no embeddings).

    Required body fields: board, scope.
    Returns 200 {mode, has_flow, board, scope, board_context, decisions, escalations,
    message_count} or 400 when scope is missing.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            get_active_escalations as _get_escalations,
            get_messages as _get_messages,
            get_pending_decisions as _get_decisions,
        )
        from pathly_orchestrator.supervisor.board_run import _format_board_info

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        board = data.get("board")
        scope = data.get("scope")

        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        if not isinstance(board, str) or not board.strip():
            board = "feature"

        conn = _get_db()
        decisions = _get_decisions(conn, boards=[board], scopes=[scope])
        escalations = _get_escalations(conn, boards=[board], scopes=[scope])
        recent = _get_messages(conn, board=board, scope=scope, limit=20)

        board_context = _format_board_info(decisions, escalations, recent)

        return jsonify({
            "mode": "board-info",
            "has_flow": False,
            "board": board,
            "scope": scope,
            "board_context": board_context,
            "decisions": decisions,
            "escalations": escalations,
            "message_count": len(recent),
        }), 200
    except Exception as exc:
        logging.exception("comms_agent_context error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/run", methods=["POST"])
def comms_run():
    """Spawn a single-agent board run (US4).

    Required body fields: board, scope, mode ("single-agent"|"evaluator").
    Optional: instructions, project_root.
    Returns 200 with start_board_run result, or 409 when the board is busy.
    """
    try:
        from pathly_orchestrator.supervisor.board_run import start_board_run

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        board = data.get("board", "feature")
        scope = data.get("scope")
        mode = data.get("mode", "single-agent")
        instructions = data.get("instructions", "") or ""
        project_root = data.get("project_root", "") or ""
        agent = data.get("agent", "") or ""
        skill = data.get("skill", "") or ""
        system_prompt = data.get("system_prompt", "") or ""
        interactive = bool(data.get("interactive", False))

        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"

        # Lifecycle posts so the human is never blind: a "started" message when the
        # run begins and a "done" summary when it ends, both streamed live to the
        # board via _broadcast_comms. Defined here (http layer) and injected into
        # board_run so the supervisor never imports http_server.
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message

        def _board_post(text: str) -> None:
            try:
                conn = _get_db()
                mid = _post_message(conn, board=board, scope=scope,
                                    from_agent="system", type="status", text=text)
                _broadcast_comms(scope, {
                    "type": "COMMS_UPDATE", "event": "board_run",
                    "message_id": mid, "board": board, "scope": scope,
                })
            except Exception:
                logging.debug("board_run lifecycle post failed", exc_info=True)

        label = (agent if isinstance(agent, str) and agent else mode)

        def _on_start(_run_id: str) -> None:
            _board_post(f"🤖 {label} started on this board…")

        def _on_done(_run_id: str, res) -> None:
            summary = ""
            if isinstance(res, dict):
                summary = str(res.get("result") or res.get("summary") or "done")
            _board_post(f"✅ {label} finished — {summary[:300]}")

        result = start_board_run(
            board,
            scope,
            mode,
            instructions,
            project_root=project_root,
            agent=agent if isinstance(agent, str) else "",
            skill=skill if isinstance(skill, str) else "",
            system_prompt=system_prompt if isinstance(system_prompt, str) else "",
            interactive=interactive,
            broadcast_fn=_broadcast_runner,   # so TERMINAL_SPAWN reaches Studio
            on_start=_on_start,
            on_done=_on_done,
        )

        if not result.get("ok"):
            return jsonify({"ok": False, "error": result.get("error", "board_busy")}), 409

        return jsonify(result), 200
    except Exception as exc:
        logging.exception("comms_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/run/stop", methods=["POST"])
def comms_run_stop():
    """Stop the agent currently running on a board.

    Required body: {board, scope}. Kills the agent's PTY (TERMINAL_KILL), unblocks
    the waiting run so its lock is freed, releases the board lock, and posts a
    'stopped' status. Idempotent: stopped=false when nothing is running.
    """
    try:
        from pathly_orchestrator.supervisor import board_lock, get_run
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message

        data = request.get_json() or {}
        board = data.get("board", "feature")
        scope = data.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"

        run_id = board_lock.holder(board, scope)
        if not run_id:
            return jsonify({"ok": True, "stopped": False, "reason": "not_running"}), 200

        # 1. Kill the visible PTY tab in Studio.
        tab_id = f"runner-{run_id[-10:]}"
        try:
            _broadcast_runner(scope, {"type": "TERMINAL_KILL", "tab_id": tab_id, "run_id": run_id})
        except Exception:
            pass
        # 2. Unblock the waiting run (its finally then releases the lock).
        try:
            run = get_run(run_id)
            if run is not None:
                run.mark_pty_result({"exit_code": 0, "result": {"result": "stopped by user"}})
        except Exception:
            pass
        # 3. Belt-and-suspenders — free the board lock immediately.
        board_lock.release(board, scope, run_id)

        # 4. Tell the board it was stopped (streamed live).
        try:
            conn = _get_db()
            mid = _post_message(conn, board=board, scope=scope, from_agent="system",
                                type="status", text="⏹ run stopped by user")
            _broadcast_comms(scope, {"type": "COMMS_UPDATE", "event": "board_run",
                                     "message_id": mid, "board": board, "scope": scope})
        except Exception:
            pass

        return jsonify({"ok": True, "stopped": True, "run_id": run_id}), 200
    except Exception as exc:
        logging.exception("comms_run_stop error")
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

        # force=True lets the human remove any board message (incl. agent posts and
        # already-read messages). Still a soft delete — recoverable from trash.
        force = bool(data.get("force", False))

        conn = _get_db()
        result = _soft_delete(conn, message_id, force=force)
        if result == "not_found":
            return jsonify({"ok": False, "error": "Message not found"}), 404
        if result == "locked":
            return jsonify({"ok": False, "error": "Message already read by an agent — cannot retract"}), 409
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("comms_delete error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
