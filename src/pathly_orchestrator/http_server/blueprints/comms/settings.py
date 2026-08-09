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
                    {
                        "error": "Field 'scope' must contain at least one of: feature, project, global"
                    }
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


@bp.route("/comms/default-selection", methods=["GET"])
def comms_get_default_selection():
    """Return the app-default AI summary target (AiSelection {type,id}) or null.

    unified-ai-routing Conv 3: the client uses this to seed the ArtifactsView
    AiTargetSelector. null ⇒ the renderer falls back to its built-in default."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_default_summary_selection,
        )

        return jsonify({"selection": get_default_summary_selection(_get_db())}), 200
    except Exception as exc:
        logging.exception("comms_get_default_selection error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/default-selection", methods=["POST"])
def comms_set_default_selection():
    """Persist the app-default AI summary target. Body: {selection: {type,id}}."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            set_default_summary_selection,
        )

        data = request.get_json(silent=True) or {}
        selection = data.get("selection")
        if not isinstance(selection, dict):
            return jsonify({"error": "Field 'selection' must be an object"}), 400
        try:
            set_default_summary_selection(_get_db(), selection)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "selection": selection}), 200
    except Exception as exc:
        logging.exception("comms_set_default_selection error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/default-style", methods=["GET"])
def comms_get_default_style():
    """Return the app-default summary DEPTH style ('gist'|'topic-map'|'detailed') or null.

    The client seeds the ArtifactsView depth picker from this; null ⇒ the renderer
    falls back to its built-in default (topic-map)."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_default_summary_style,
        )

        return jsonify({"style": get_default_summary_style(_get_db())}), 200
    except Exception as exc:
        logging.exception("comms_get_default_style error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/default-style", methods=["POST"])
def comms_set_default_style():
    """Persist the app-default summary DEPTH style. Body: {style: 'gist'|'topic-map'|'detailed'}."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            set_default_summary_style,
        )

        data = request.get_json(silent=True) or {}
        style = data.get("style")
        if not isinstance(style, str):
            return jsonify({"error": "Field 'style' must be a string"}), 400
        try:
            set_default_summary_style(_get_db(), style)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "style": style}), 200
    except Exception as exc:
        logging.exception("comms_set_default_style error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/default-progress", methods=["GET"])
def comms_get_default_progress():
    """Return the app-default board-updates verbosity ('quiet'|'normal'|'verbose') or null.

    The single source of truth for how chatty a headless agent is on the board. The client
    seeds the Settings control from this; null ⇒ the renderer falls back to 'normal'."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            get_default_progress,
        )

        return jsonify({"progress": get_default_progress(_get_db())}), 200
    except Exception as exc:
        logging.exception("comms_get_default_progress error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/default-progress", methods=["POST"])
def comms_set_default_progress():
    """Persist the app-default board-updates verbosity. Body: {progress: 'quiet'|'normal'|'verbose'}."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            set_default_progress,
        )

        data = request.get_json(silent=True) or {}
        progress = data.get("progress")
        if not isinstance(progress, str):
            return jsonify({"error": "Field 'progress' must be a string"}), 400
        try:
            set_default_progress(_get_db(), progress)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "progress": progress}), 200
    except Exception as exc:
        logging.exception("comms_set_default_progress error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


# ── spawn-policy P1 — per-agent model + logging config API ─────────────
# Mirrors the /comms/default-progress pair. The one editable surface behind the Settings UI;
# both this and the Python resolver read the SAME DB rows (db/queries/app_settings), so nothing
# re-fragments. The always-on cost/monitor spine is NOT exposed here — by design it can't be
# toggled off (see get_logging_config / the spawn-policy SPEC §0 invariant).


@bp.route("/comms/model-policy", methods=["GET"])
def comms_get_model_policy():
    """Return {default: {adapter,model}|null, roles: {<role>: {adapter,model}}} for the UI."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import get_model_policy

        return jsonify(get_model_policy(_get_db())), 200
    except Exception as exc:
        logging.exception("comms_get_model_policy error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/model-policy", methods=["POST"])
def comms_set_model_policy():
    """Set the global default (role null/'default') or a per-role override, or clear one.

    Body: {role?: str|null, adapter: str, model?: str}  — set; `model` '' ⇒ engine default.
          {role: str, clear: true}                       — remove that override.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import (
            clear_agent_model,
            set_agent_model,
        )

        data = request.get_json(silent=True) or {}
        role = data.get("role")
        if data.get("clear") is True:
            clear_agent_model(_get_db(), role)
            return jsonify({"ok": True, "cleared": role or "default"}), 200
        adapter = data.get("adapter")
        model = data.get("model", "")
        if not isinstance(adapter, str) or not adapter.strip():
            return jsonify({"error": "Field 'adapter' must be a non-empty string"}), 400
        try:
            set_agent_model(_get_db(), role, adapter, model if isinstance(model, str) else "")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "role": role or "default", "adapter": adapter, "model": model}), 200
    except Exception as exc:
        logging.exception("comms_set_model_policy error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/logging-config", methods=["GET"])
def comms_get_logging_config():
    """Return {board: bool, verbosity: 'quiet'|'normal'|'verbose'} — the AGENT-narration sinks.

    The cost/monitor spine is intentionally absent (always on)."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import get_logging_config

        return jsonify(get_logging_config(_get_db())), 200
    except Exception as exc:
        logging.exception("comms_get_logging_config error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/logging-config", methods=["POST"])
def comms_set_logging_config():
    """Turn agent BOARD narration on/off. Body: {board: bool}. Never touches the monitor spine."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.app_settings import set_logging_board_enabled

        data = request.get_json(silent=True) or {}
        board = data.get("board")
        if not isinstance(board, bool):
            return jsonify({"error": "Field 'board' must be a boolean"}), 400
        set_logging_board_enabled(_get_db(), board)
        return jsonify({"ok": True, "board": board}), 200
    except Exception as exc:
        logging.exception("comms_set_logging_config error")
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
        try:
            from pathly_orchestrator.runner.embeddings import embed as _embed_fn
        except Exception:
            _embed_fn = None
        pairs = _dedupe(
            conn, board, scope, max_distance=float(max_distance), embed_fn=_embed_fn
        )

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
                _board_post(
                    "reflector started synthesizing this board…", phase="running"
                )

            def _on_done(_run_id: str, res) -> None:
                summary = ""
                if isinstance(res, dict):
                    summary = str(res.get("result") or res.get("summary") or "done")
                _board_post(
                    f"reflector finished synthesis — {summary[:280]}", phase="done"
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

        return (
            jsonify({"ok": True, "superseded_count": len(pairs), "pairs": pairs}),
            200,
        )
    except Exception as exc:
        logging.exception("comms_consolidate error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
