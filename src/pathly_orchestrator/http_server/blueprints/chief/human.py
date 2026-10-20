"""POST /chief/human-messages — record a prompt that reached a chief's claude tab (chief-agent).

Written to by one caller in practice: the chief's UserPromptSubmit hook
(``pathly_hooks.chief_prompt``), which holds the session's hook secret (a 0600 file in the
session folder; the session row keeps only its sha256) and the claude session id. The chief
itself holds a run token, never the secret, and the chief gate refuses this route to a chief
token (it is not in ``chief_routes.ROUTE_ACTIONS``). So "only the hook can write" means no
chief token can. The secret file is readable by every other process of the same user and the
claude ``--session-id`` is in the chief's argv, so a same-user process that reads both (a
headless builder, say) can post a ``human`` row. The caller must also name the chief's own
claude session id (``chief_sessions.cli_session_id``, which ``open_chief`` passed to claude as
``--session-id``), so a hook that picked up the settings file in another claude session records
nothing; ``/clear`` in the tab gives claude a new id, after which every prompt is a 403.

The session id binds the process, not the typist, and the server cannot tell a typed prompt from
another one. The hook sends ``relayed: true`` for the prompts it recognises by a wrapper
(``<task-notification>`` for a finished background task, ``<cross-session-message>`` for another
session's message); the server stores kind ``relayed``, which ticket 10 never accepts as a
citation. That is a deny-list of wrappers measured on claude 2.1.304: a prompt without one is
stored as ``human`` whether or not anyone typed it (a scheduled task from the project's
``.claude/scheduled_tasks.json`` arrives bare). ``src/pathly_orchestrator/CLAUDE.md`` ("Human
messages") lists the sources found and the two claude switches that close most of them.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("chief_human", __name__)

MAX_TEXT_BYTES = 64 * 1024


def _secret_matches(secret: object, stored_hash: object) -> bool:
    """Whether sha256(``secret``) is ``stored_hash`` (constant-time compare)."""
    if not isinstance(secret, str) or not secret:
        return False
    if not isinstance(stored_hash, str) or not stored_hash:
        return False
    try:
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(digest.encode("ascii"), stored_hash.encode("utf-8"))


def _text_refusal(text: object) -> str | None:
    """Why ``text`` cannot be stored, or None."""
    if not isinstance(text, str) or not text.strip():
        return "Field 'text' must be a non-empty string"
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError:
        return "Field 'text' must be valid Unicode"
    if size > MAX_TEXT_BYTES:
        return f"Field 'text' must be at most {MAX_TEXT_BYTES} bytes"
    return None


@bp.route("/chief/human-messages", methods=["POST"])
def chief_human_message():
    """Store a prompt: 201 ``{id, kind}``.

    400 for a body that is not an object or a bad ``text`` (not a string, blank, invalid
    Unicode or over 64 KiB), 404 when the session is unknown or closed, 403 when the secret
    does not match the session's or ``session_id`` is not its claude session. The first
    message of a session is stored as ``style_prompt``; ``relayed`` makes a later one
    ``relayed``, else it is ``human``.
    """
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "A JSON object body is required"}), 400
        refusal = _text_refusal(body.get("text"))
        if refusal is not None:
            return jsonify({"error": refusal}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries import chief as sessions

        conn = get_db()
        run_id = body.get("run_id")
        session = (
            sessions.get_session(conn, run_id) if isinstance(run_id, str) else None
        )
        if session is None or session.get("closed_at") is not None:
            return jsonify({"error": "no open chief session"}), 404
        if not _secret_matches(
            body.get("hook_secret"), session.get("hook_secret_hash")
        ):
            return jsonify({"error": "bad hook secret"}), 403
        sent, own = body.get("session_id"), session.get("cli_session_id")
        if not (
            isinstance(sent, str) and sent and isinstance(own, str) and sent == own
        ):
            return jsonify({"error": "not this chief's claude session"}), 403

        stored = sessions.add_human_message(
            conn,
            run_id,
            session.get("project_root"),
            body["text"],
            relayed=bool(body.get("relayed")),
        )
        return jsonify({"id": stored["id"], "kind": stored["kind"]}), 201
    except Exception as exc:
        logging.exception("chief_human_message error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
