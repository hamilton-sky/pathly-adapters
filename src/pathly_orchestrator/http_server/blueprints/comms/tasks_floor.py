"""POST /comms/tasks/floor-allow — a human allows floor categories for one task (build-proof).

The floor guard (``proof/floor.py``) fails a build that skips a test, silences a check or
edits its own task. When one task really must do one of those, a human names the allowed
categories here. Task text on the board is written by agents, so an allow line in the text
would let the planner grant the builder an excuse: this route is the only writer of
``floor_allow``, and it refuses any caller with a live run token, the same rule
``/complete_stage`` applies to ``force_past_gate``. The limit is the same too: a caller with no
token (or an unknown or revoked one) is treated as a human, because the server cannot tell
Studio from a local process until the UI token exists.

``refreeze: true`` also copies the task's live text into ``claimed_text`` (frozen at the
task's first claim), which is how a human corrects a broken check without allowing
``task-edit``.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ._helpers import read_json_body

bp = Blueprint("comms_tasks_floor", __name__)


@bp.route("/comms/tasks/floor-allow", methods=["POST"])
def comms_tasks_floor_allow():
    """Set a task's floor allow list, and with ``refreeze`` its frozen text. Humans only."""
    try:
        from pathly_orchestrator.http_server.run_identity import caller_identity

        if caller_identity(request).kind == "run":
            return (
                jsonify({"error": "floor-allow is refused for an agent run"}),
                403,
            )

        from pathly_orchestrator.proof.floor import CATEGORIES, parse_allow

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
        message_id = data.get("message_id")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )
        raw_allow = data.get("allow")
        if not isinstance(raw_allow, list):
            return (
                jsonify(
                    {
                        "error": "Field 'allow' must be a list of floor categories; "
                        "valid categories: " + ", ".join(CATEGORIES)
                    }
                ),
                400,
            )
        refreeze = data.get("refreeze", False)
        if not isinstance(refreeze, bool):
            return jsonify({"error": "Field 'refreeze' must be true or false"}), 400
        try:
            allow = parse_allow(raw_allow)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import get_task, set_floor_allow

        conn = get_db()
        row = get_task(conn, message_id.strip())
        if row is None:
            return jsonify({"error": f"No message {message_id!r}"}), 404
        if row["type"] != "task":
            return (
                jsonify(
                    {"error": f"Message {message_id!r} is a {row['type']}, not a task"}
                ),
                400,
            )
        set_floor_allow(conn, row["id"], allow, refreeze=refreeze)
        return jsonify({"ok": True, "allow": sorted(allow)}), 200
    except Exception as exc:
        logging.exception("comms_tasks_floor_allow error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
