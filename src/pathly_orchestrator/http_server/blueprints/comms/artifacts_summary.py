"""Client-side artifact summary + per-artifact AI-target writeback routes.

unified-ai-routing (Conv 3): summarization moved from the server to the CLIENT
(renderer aiRouter). These two routes are how the client posts its computed result
back. Split from artifacts.py to keep that file under the 400-line SOLID cap and to
isolate the writeback domain from attach/list/summarize/section.

Auth: the X-Pathly-Secret middleware guards every /comms/* route — no per-route
change needed. Lazy imports inside handlers per the layer-dependency rule.
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypeGuard

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms

bp = Blueprint("comms_artifacts_summary", __name__)


def _artifact_scope(conn, artifact_id: str) -> str | None:
    """Return the owning message's scope for artifact_id, or None if not found.

    Shared by the summary + selection writeback routes so each can broadcast a
    COMMS_UPDATE on the right board and 404 cleanly when the artifact is gone."""
    row = conn.execute(
        "SELECT m.scope FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE a.id=? AND m.deleted_at IS NULL",
        (artifact_id,),
    ).fetchone()
    return (row["scope"] or "") if row is not None else None


def _validate_selection(sel) -> TypeGuard[dict[str, Any]]:
    """True when sel is a well-formed AiSelection {'type':'model'|'engine','id':str}."""
    return (
        isinstance(sel, dict)
        and sel.get("type") in ("model", "engine")
        and isinstance(sel.get("id"), str)
        and bool(sel["id"].strip())
    )


@bp.route("/comms/artifacts/<artifact_id>/summary", methods=["POST"])
def comms_artifact_set_summary(artifact_id: str):
    """Client writeback of a CLIENT-computed summary.

    Body: {summary: str, selection?: AiSelection}. The renderer runs aiRouter
    locally (Ollama / GGUF / Brightsky / CLI engine) and POSTs the resulting text
    here — the server never runs inference for this path. When `selection` is
    given it is persisted alongside as the artifact's saved target. Broadcasts a
    COMMS_UPDATE summary_ready so open boards refresh, matching the other artifact
    mutations."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms_summary import (
            set_artifact_summary as _set_summary,
        )

        data = request.get_json(silent=True) or {}
        summary = data.get("summary")
        if not isinstance(summary, str):
            return (
                jsonify({"ok": False, "error": "Field 'summary' must be a string"}),
                400,
            )

        selection = data.get("selection")
        selection_json = None
        if selection is not None:
            if not _validate_selection(selection):
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "Field 'selection' must be {type:'model'|'engine', id:str}",
                        }
                    ),
                    400,
                )
            selection_json = json.dumps(
                {"type": selection["type"], "id": selection["id"]}
            )

        conn = _get_db()
        scope = _artifact_scope(conn, artifact_id)
        if scope is None:
            return jsonify({"ok": False, "error": "artifact not found"}), 404

        _set_summary(conn, artifact_id, summary, selection_json=selection_json)

        _broadcast_comms(
            scope,
            {
                "type": "COMMS_UPDATE",
                "event": "summary_ready",
                "artifact_id": artifact_id,
                "scope": scope,
            },
        )
        return jsonify({"ok": True, "artifact_id": artifact_id}), 200
    except Exception as exc:
        logging.exception("comms_artifact_set_summary error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/artifacts/<artifact_id>/selection", methods=["POST"])
def comms_artifact_set_selection(artifact_id: str):
    """Persist the per-artifact AI target.

    Body: {selection: AiSelection}. Lets the user pin a target on one artifact so
    Re-summarize reuses it."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms_summary import (
            set_artifact_summary_selection as _set_selection,
        )

        data = request.get_json(silent=True) or {}
        selection = data.get("selection")
        if not _validate_selection(selection):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Field 'selection' must be {type:'model'|'engine', id:str}",
                    }
                ),
                400,
            )

        conn = _get_db()
        scope = _artifact_scope(conn, artifact_id)
        if scope is None:
            return jsonify({"ok": False, "error": "artifact not found"}), 404

        _set_selection(
            conn,
            artifact_id,
            json.dumps({"type": selection["type"], "id": selection["id"]}),
        )

        _broadcast_comms(
            scope,
            {
                "type": "COMMS_UPDATE",
                "event": "artifact_selection",
                "artifact_id": artifact_id,
                "scope": scope,
            },
        )
        return jsonify({"ok": True, "artifact_id": artifact_id}), 200
    except Exception as exc:
        logging.exception("comms_artifact_set_selection error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
