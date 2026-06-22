"""Board settings, permissions, memory consolidation, and agent context endpoints."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner
from ._helpers import norm_project_root

bp = Blueprint("comms_settings", __name__)


@bp.route("/comms/scope", methods=["GET"])
def comms_scope_get():
    """Return the board_scope for a feature."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_board_scope as _get_scope,
        )

        feature = request.args.get("feature", "").strip()
        project_root = request.args.get("project_root", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400
        if not project_root:
            return jsonify({"error": "Query parameter 'project_root' is required"}), 400

        conn = _get_db()
        scope = _get_scope(
            conn, project_root=norm_project_root(project_root), feature=feature
        )
        return jsonify(scope), 200
    except Exception as exc:
        logging.exception("comms_scope_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/scope", methods=["POST"])
def comms_scope_set():
    """Persist the board_scope for a feature."""
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
            return (
                jsonify({"error": "Field 'project_root' must be a non-empty string"}),
                400,
            )
        if not isinstance(scope, dict):
            return jsonify({"error": "Field 'scope' must be an object"}), 400

        allowed = {"feature", "project", "global"}
        updates = {k: bool(v) for k, v in scope.items() if k in allowed}
        if not updates:
            return (
                jsonify(
                    {"error": "Field 'scope' must contain at least one of: feature, project, global"}
                ),
                400,
            )

        conn = _get_db()
        norm_root = norm_project_root(project_root)
        merged = _get_scope(conn, project_root=norm_root, feature=feature)
        merged.update(updates)
        _set_scope(conn, project_root=norm_root, feature=feature, scope_dict=merged)
        return jsonify(merged), 200
    except Exception as exc:
        logging.exception("comms_scope_set error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/permissions", methods=["GET"])
def comms_permissions():
    """Return the resolved write-permission table for a project."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_write_permissions as _get_perms,
        )

        project_root = request.args.get("project_root", "").strip()
        norm_root = norm_project_root(project_root) if project_root else ""

        conn = _get_db()
        perms = _get_perms(conn, norm_root)
        return jsonify(perms), 200
    except Exception as exc:
        logging.exception("comms_permissions error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/summary-backend", methods=["GET"])
def comms_get_summary_backend():
    """Return the global offline-summarizer backend."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import get_summary_backend

        return jsonify({"backend": get_summary_backend(_get_db())}), 200
    except Exception as exc:
        logging.exception("comms_get_summary_backend error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/summary-backend", methods=["POST"])
def comms_set_summary_backend():
    """Set the global offline-summarizer backend."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import set_summary_backend

        data = request.get_json() or {}
        backend = data.get("backend", "")
        if not isinstance(backend, str) or not backend.strip():
            return jsonify({"error": "Field 'backend' is required"}), 400
        try:
            set_summary_backend(_get_db(), backend)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "backend": backend}), 200
    except Exception as exc:
        logging.exception("comms_set_summary_backend error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/agent-context", methods=["POST"])
def comms_agent_context():
    """Return board context in BOARD-INFO mode."""
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

        return (
            jsonify(
                {
                    "mode": "board-info",
                    "has_flow": False,
                    "board": board,
                    "scope": scope,
                    "board_context": board_context,
                    "decisions": decisions,
                    "escalations": escalations,
                    "message_count": len(recent),
                }
            ),
            200,
        )
    except Exception as exc:
        logging.exception("comms_agent_context error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/consolidate", methods=["POST"])
def comms_consolidate():
    """Memory consolidation — deterministic dedup and optional LLM synthesis."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            dedupe_board as _dedupe,
            post_message as _post_message,
        )

        data = request.get_json() or {}
        scope = data.get("scope")
        board = data.get("board", "feature")
        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"
        max_distance = data.get("max_distance", 0.08)
        if not isinstance(max_distance, (int, float)):
            return jsonify({"error": "Field 'max_distance' must be a number"}), 400
        mode = (data.get("mode", "") or "dedup").strip().lower()
        if mode not in ("dedup", "full", "reflect"):
            mode = "dedup"

        conn = _get_db()
        pairs = _dedupe(conn, board, scope, max_distance=float(max_distance))

        if pairs:
            try:
                mid = _post_message(
                    conn,
                    board=board,
                    scope=scope,
                    from_agent="system",
                    type="status",
                    text=f"🧹 Consolidated board — superseded {len(pairs)} near-duplicate note(s).",
                )
                _broadcast_comms(
                    scope,
                    {
                        "type": "COMMS_UPDATE",
                        "event": "consolidated",
                        "message_id": mid,
                        "board": board,
                        "scope": scope,
                        "superseded_count": len(pairs),
                    },
                )
            except Exception:
                pass

        if mode in ("full", "reflect"):
            from pathly_orchestrator.supervisor.board_run import start_board_run

            project_root = data.get("project_root", "") or ""

            def _board_post(text: str, phase: str | None = None) -> None:
                try:
                    _c = _get_db()
                    _mid = _post_message(
                        _c,
                        board=board,
                        scope=scope,
                        from_agent="system",
                        type="status",
                        text=text,
                    )
                    payload = {
                        "type": "COMMS_UPDATE",
                        "event": "board_run",
                        "message_id": _mid,
                        "board": board,
                        "scope": scope,
                    }
                    if phase:
                        payload["phase"] = phase
                    _broadcast_comms(scope, payload)
                except Exception:
                    logging.debug("consolidate lifecycle post failed", exc_info=True)

            def _on_start(_run_id: str) -> None:
                _board_post("🤖 reflector started synthesizing this board…", phase="running")

            def _on_done(_run_id: str, res) -> None:
                summary = ""
                if isinstance(res, dict):
                    summary = str(res.get("result") or res.get("summary") or "done")
                _board_post(
                    f"✅ reflector finished synthesis — {summary[:280]}", phase="done"
                )

            result = start_board_run(
                board,
                scope,
                "single-agent",
                skill="planning/consolidate",
                agent="planner",
                project_root=project_root,
                broadcast_fn=_broadcast_runner,
                on_start=_on_start,
                on_done=_on_done,
            )

            if not result.get("ok"):
                return (
                    jsonify({"ok": False, "error": result.get("error", "board_busy")}),
                    409,
                )

            return (
                jsonify(
                    {
                        "ok": True,
                        "superseded_count": len(pairs),
                        "pairs": pairs,
                        "run_id": result.get("run_id"),
                        "status": result.get("status", "started"),
                    }
                ),
                200,
            )

        return jsonify({"ok": True, "superseded_count": len(pairs), "pairs": pairs}), 200
    except Exception as exc:
        logging.exception("comms_consolidate error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
