"""POST /comms/post — the main message-write handler.

Kept in its own file because comms_post is ~300 lines: it validates required
fields, enforces write permissions, resolves context_refs, posts the message,
triggers artifact indexing, emits the summary request, and fires the SSE update.
"""

from __future__ import annotations

import json
import logging
import os

from flask import jsonify, request

from ...sse import _broadcast_comms
from ._helpers import (
    _EMBED_TYPES,
    check_write_permission,
    extract_artifact_path,
    guess_artifact_type,
    norm_project_root,
)
from ._messages_bp import bp


@bp.route("/comms/post", methods=["POST"])
def comms_post():
    """Post a message to a board."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_write_permissions as _get_write_perms,
        )
        from pathly_orchestrator.db.queries.comms import post_message as _post_message
        from pathly_orchestrator.runner.embeddings import (
            embed_artifact_async as _embed_artifact_async,
            embed_async as _embed_async,
        )

        # Windows agents post via curl whose JSON body may be cp1252-encoded (a stray em-dash →
        # byte 0x97), which strict UTF-8 parsing rejects with a 500 — silently dropping a task or
        # artifact. Decode leniently: UTF-8 first, then cp1252, so the post always lands.
        raw = request.get_data()
        data = None
        if raw:
            for _enc in ("utf-8", "cp1252"):
                try:
                    data = json.loads(raw.decode(_enc))
                    break
                except (UnicodeDecodeError, ValueError):
                    continue
        if not data:
            return jsonify({"error": "Missing or invalid JSON body"}), 400

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
                        "builder",
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
        # summary_backend is now ONLY the client-drop suppression signal consumed by
        # emit_summary_request: 'minilm' ⇒ suppress the summary_request (the Conv-3
        # client-drop path already summarized inline). Any other string|null is
        # accepted and means "emit" — the server runs no inference, so legacy values
        # (ollama/haiku) no longer error. Coerced to None for non-string inputs.
        summary_backend = data.get("summary_backend")
        if not isinstance(summary_backend, str):
            summary_backend = None
        # embed_summary (§3a): accepted as a no-op for request-contract compatibility.
        _ = bool(data.get("embed_summary"))
        # §3: an agent that just wrote the artifact may supply `summary` alongside
        # `text`. When present we store it, embed description+summary, and SKIP the
        # client summary_request — the author knows it best.
        artifact_summary = data.get("summary")
        if not isinstance(artifact_summary, str) or not artifact_summary.strip():
            artifact_summary = None
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
                    safe_artifact_path as _safe_artifact_path,
                )

                _project_root = project_root or os.getcwd()
                resolved_refs = []
                for ref in context_refs:
                    art_name = ref.get("artifact", "")
                    anc = ref.get("anchor")
                    if not art_name or anc is None:
                        resolved_refs.append(ref)
                        continue
                    try:
                        art_path = _safe_artifact_path(scope, art_name, _project_root)
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
                                        f"context_refs validate-at-write: "
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
                    summary=artifact_summary or text,
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
                        broadcast_fn=lambda _p: _broadcast_comms(scope, _p),
                    )
                except Exception:
                    logging.debug("index_artifact_async (post) failed", exc_info=True)

                from ._summary_request import emit_summary_request as _emit_summary_req

                _emit_summary_req(
                    conn,
                    artifact_id=art_id,
                    artifact_path=artifact_path,
                    artifact_type=artifact_type
                    if isinstance(artifact_type, str)
                    else None,
                    scope=scope,
                    summary_backend="minilm" if artifact_summary else summary_backend,
                    broadcast_fn=lambda _p: _broadcast_comms(scope, _p),
                )
            except Exception:
                logging.debug("comms_artifacts insert (post) failed", exc_info=True)

        if msg_type in _EMBED_TYPES:
            if msg_type == "artifact" and artifact_summary:
                _embed_artifact_async(
                    message_id, f"{text}\n\n{artifact_summary}".strip(), artifact_summary
                )
            else:
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

        # T3a: server-side context_refs enforcement for DAG tasks. A task posted with no
        # refs (and no explicit no_refs justification) will fall back to unverified
        # auto-derived context — surface that as a NON-BLOCKING warning so the gap is
        # visible to the poster instead of silently degrading context quality (ISSUE-4).
        resp = {"ok": True, "message_id": message_id}
        if msg_type == "task":
            _has_refs = isinstance(context_refs, list) and len(context_refs) > 0
            if not _has_refs and not data.get("no_refs"):
                resp["ref_warning"] = (
                    "task has no context_refs; agents will fall back to unverified "
                    "auto-derived context — add context_refs or pass no_refs=<reason>"
                )
        return jsonify(resp), 200
    except Exception as exc:
        logging.exception("comms_post error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
