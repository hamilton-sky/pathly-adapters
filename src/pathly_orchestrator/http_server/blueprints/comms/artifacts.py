"""Artifact attachment and retrieval endpoints (/comms/attach, /comms/artifacts)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms
from ._helpers import extract_artifact_path, guess_artifact_type

bp = Blueprint("comms_artifacts", __name__)


@bp.route("/comms/attach", methods=["POST"])
def comms_attach():
    """Attach a file or URL artifact to an existing message."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            attach_artifact_to_message as _attach,
            insert_artifact as _insert_artifact,
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

        artifact_path = data.get("artifact_path")
        artifact_url = data.get("artifact_url")
        artifact_type = data.get("artifact_type")

        has_path = isinstance(artifact_path, str) and artifact_path.strip()
        has_url = isinstance(artifact_url, str) and artifact_url.strip()
        if not has_path and not has_url:
            return (
                jsonify(
                    {"error": "Provide at least one of 'artifact_path' or 'artifact_url'"}
                ),
                400,
            )
        if artifact_type is not None and not isinstance(artifact_type, str):
            return (
                jsonify({"error": "Field 'artifact_type' must be a string or null"}),
                400,
            )

        conn = _get_db()
        row = conn.execute(
            "SELECT board, scope, from_agent, text FROM comms_messages WHERE id=? AND deleted_at IS NULL",
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

        if has_path:
            try:
                art_id = _insert_artifact(
                    conn,
                    message_id=message_id,
                    path=artifact_path,
                    type=artifact_type if isinstance(artifact_type, str) else None,
                    summary=row["text"],
                    created_by=row["from_agent"],
                )
                try:
                    from pathly_orchestrator.runner.hydrate import (
                        index_artifact_async as _index_async,
                    )
                    _ascope = row.get("scope", "")
                    _index_async(
                        art_id,
                        artifact_path,
                        scope=_ascope,
                        broadcast_fn=lambda _p: _broadcast_comms(_ascope, _p),
                    )
                except Exception:
                    logging.debug("index_artifact_async (attach) failed", exc_info=True)
            except Exception:
                logging.debug("comms_artifacts insert (attach) failed", exc_info=True)

        _broadcast_comms(
            row["scope"],
            {
                "type": "COMMS_UPDATE",
                "message_id": message_id,
                "event": "artifact_attached",
                "board": row["board"],
                "scope": row["scope"],
                "artifact_type": artifact_type,
            },
        )

        return jsonify({"ok": True, "message_id": message_id}), 200
    except Exception as exc:
        logging.exception("comms_attach error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/artifacts", methods=["GET"])
def comms_artifacts():
    """List artifacts for a message or board catalog."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db

        message_id = (request.args.get("message_id") or "").strip()
        board = (request.args.get("board") or "").strip()
        scope = (request.args.get("scope") or "").strip()

        conn = _get_db()

        if message_id:
            from pathly_orchestrator.db.queries.comms import (
                list_artifacts_for_message as _list_artifacts,
            )
            return (
                jsonify({"ok": True, "artifacts": _list_artifacts(conn, message_id)}),
                200,
            )

        if board and scope:
            from pathly_orchestrator.db.queries.comms import (
                list_artifacts_catalog as _list_catalog,
            )
            goal_id = (request.args.get("goal_id") or "").strip() or None
            order = (request.args.get("order") or "").strip() or None
            limit_raw = request.args.get("limit")
            offset_raw = request.args.get("offset")
            limit = int(limit_raw) if limit_raw and limit_raw.isdigit() else None
            offset = int(offset_raw) if offset_raw and offset_raw.isdigit() else None
            rows = _list_catalog(
                conn,
                scope,
                exposed_boards=[board],
                goal_id=goal_id,
                order=order,
                limit=limit,
                offset=offset,
            )
            return jsonify({"ok": True, "artifacts": rows}), 200

        return jsonify({"error": "Query param 'message_id' or 'board'+'scope' is required"}), 400
    except Exception as exc:
        logging.exception("comms_artifacts error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


# API summary engines run in-process (async, silent). CLI engines (claude/codex/…)
# need the terminal-spawn path and are not driven through this route yet.
_API_SUMMARY_ENGINES = {"ollama", "haiku"}


@bp.route("/comms/artifacts/<artifact_id>/summarize", methods=["POST"])
def comms_artifact_summarize(artifact_id: str):
    """Trigger an on-demand summary of an artifact with a chosen engine (manual
    per-card Summarize). Async + best-effort: returns 202 immediately; the
    `summarizing` / `summary_ready` / `summary_failed` COMMS_UPDATE signals carry
    the outcome. `engine` is optional — omit to use the global default backend."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.runner.hydrate import _schedule_resummarize_async

        data = request.get_json(silent=True) or {}
        engine = (data.get("engine") or "").strip().lower() or None
        if engine == "minilm":
            return jsonify({"ok": False, "error": "engine 'minilm' is off — produces no summary"}), 400
        if engine is not None and engine not in _API_SUMMARY_ENGINES:
            return (
                jsonify({
                    "ok": False,
                    "error": f"engine {engine!r} is not an in-process API engine "
                             f"(supported: {sorted(_API_SUMMARY_ENGINES)}; CLI engines use the terminal path)",
                }),
                400,
            )

        conn = _get_db()
        row = conn.execute(
            "SELECT a.id, m.scope FROM comms_artifacts a "
            "JOIN comms_messages m ON m.id = a.message_id "
            "WHERE a.id=? AND m.deleted_at IS NULL",
            (artifact_id,),
        ).fetchone()
        if row is None:
            return jsonify({"ok": False, "error": "artifact not found"}), 404
        scope = row["scope"] or ""

        # embed_summary=True so a successful summary also feeds the 💡 channel (§3a),
        # matching the upload path. The async worker emits the lifecycle signals.
        _schedule_resummarize_async(
            artifact_id,
            backend=engine,  # None ⇒ global default
            broadcast_fn=lambda _p: _broadcast_comms(scope, _p),
            embed_summary=True,
        )
        return (
            jsonify({"ok": True, "artifact_id": artifact_id, "engine": engine or "default", "status": "summarizing"}),
            202,
        )
    except Exception as exc:
        logging.exception("comms_artifact_summarize error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/artifacts/<artifact_id>/section", methods=["GET"])
@bp.route("/comms/artifacts/section", methods=["GET"])
def comms_artifact_section(artifact_id: str | None = None):
    """Hydrate a section of a .md artifact."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.runner.hydrate import hydrate_section as _hydrate
        import os as _os

        anchor = (request.args.get("anchor") or "").strip() or None
        scope = (
            request.args.get("scope") or request.args.get("feature") or ""
        ).strip()
        artifact = (request.args.get("artifact") or "").strip()
        project_root = (
            request.args.get("project_root") or ""
        ).strip() or _os.getcwd()

        conn = _get_db()
        result = _hydrate(
            conn,
            artifact_id=artifact_id,
            scope=scope,
            artifact=artifact,
            anchor=anchor,
            project_root=project_root,
        )
        return jsonify(result["body"]), result["status"]
    except Exception as exc:
        logging.exception("comms_artifact_section error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
