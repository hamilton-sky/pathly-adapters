"""Server-initiated summary-request emit (unified-ai-routing, Conv 4).

The server runs NO inference and NO CLI subprocess for artifact summaries. When a
``type:'artifact'`` message is posted and a summary is wanted, the server resolves
the AI target server-side and emits a ``summary_request`` event over the comms SSE.
The Studio renderer (subscribed to ``/events/comms``) reads it, runs ``aiRouter``
against the resolved target, and POSTs the result back to
``/comms/artifacts/<id>/summary``.

Layer rule: this module lives in the http_server layer (it owns the SSE emit) and
takes the already-resolved ``broadcast_fn`` so it never imports the SSE globals into
a lower layer. Lazy DB imports keep startup fast and avoid circular imports.

Selection precedence (§ server-resolve):
    per-artifact saved (get_artifact_summary_selection)
      → app default (get_default_summary_selection)
      → neither ⇒ emit NOTHING (filename-only best-effort, deferred client-side).

Suppression: ``summary_backend == 'minilm'`` ⇒ emit NOTHING. That backend is the
Conv-3 client-drop signal; the renderer already summarizes that artifact inline, so
emitting here would double the work.
"""

from __future__ import annotations

import json
import logging


def _is_md(artifact_path: str, artifact_type: str | None) -> bool:
    """Mirror the .md-only rule the client and server summarizers both apply."""
    if artifact_type == "md":
        return True
    return artifact_path.lower().endswith((".md", ".markdown", ".txt"))


def resolve_summary_selection(conn, artifact_id: str) -> dict | None:
    """Resolve the AI target for a server-initiated summary, or None.

    per-artifact saved selection → app default → None. A malformed per-artifact
    value degrades to the app default (then None), so a bad row never crashes the
    post path.
    """
    from pathly_orchestrator.db.queries.app_settings import (
        get_default_summary_selection,
    )
    from pathly_orchestrator.db.queries.comms_summary import (
        get_artifact_summary_selection,
    )

    raw = get_artifact_summary_selection(conn, artifact_id)
    if raw:
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if (
            isinstance(parsed, dict)
            and parsed.get("type") in ("model", "engine")
            and isinstance(parsed.get("id"), str)
            and parsed["id"].strip()
        ):
            return {"type": parsed["type"], "id": parsed["id"]}

    return get_default_summary_selection(conn)


def emit_summary_request(
    conn,
    *,
    artifact_id: str,
    artifact_path: str,
    artifact_type: str | None,
    scope: str,
    summary_backend: str | None,
    broadcast_fn,
) -> None:
    """Emit a ``summary_request`` comms-SSE event so the client summarizes.

    No-op (emits nothing) when:
    - ``summary_backend == 'minilm'`` (Conv-3 client-drop path summarizes inline),
    - the artifact is not a .md/.txt (matches the .md-only summarizer rule),
    - no selection resolves (filename-only best-effort).

    Never raises — a summary-request failure must not fail the artifact post.
    """
    try:
        if summary_backend == "minilm":
            return
        if not _is_md(artifact_path, artifact_type):
            return

        row = conn.execute(
            "SELECT message_id FROM comms_artifacts WHERE id=?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            return

        selection = resolve_summary_selection(conn, artifact_id)
        if not selection:
            return
        # An explicit "Off" sentinel resolves to a target the client would skip;
        # don't bother emitting for it.
        if selection.get("type") == "model" and selection.get("id") == "__off__":
            return

        broadcast_fn(
            {
                "type": "COMMS_UPDATE",
                "event": "summary_request",
                "artifact_id": artifact_id,
                "message_id": row["message_id"],
                "artifact_path": artifact_path,
                "scope": scope,
                "selection": selection,
            }
        )
    except Exception:
        logging.debug("emit_summary_request failed", exc_info=True)
