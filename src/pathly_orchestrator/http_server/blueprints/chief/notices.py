"""GET /chief/notices and POST /chief/notices/read (chief-autopilot 08).

The runs a chief session started are recorded (``http_server/chief_run_record.py``) so the person
can be told when one ends: Studio's Chief button will show the unread count (ticket 13), and
nothing enters the chief's tab. The notices are the project's recorded runs that reached a terminal
status (``parked`` included) and are unread, each with what ``GET /runs/<id>`` says of its kind,
status, outcome and cost (``chief_session_runs.run_notice``, which reads only the run, not its
stages, logs or board posts) and the count of open questions and escalations to the person on the
run's board. Rows outlive the session, so the next chief of the project sees them.

``GET /chief/notices`` is a read, which the chief gate lets a chief call for its own project.
``POST /chief/notices/read`` is the person's: it is not in ``chief_routes.ROUTE_ACTIONS``, so the
gate refuses a chief token, and this view refuses any other live run token (an agent). A tokenless
loopback caller can still call it, as every human-only route allows today.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("chief_notices", __name__)


def _notice(conn, row: dict) -> dict | None:
    """One notice: the run as ``GET /runs/<id>`` reads it, plus the open questions on its board."""
    from pathly_orchestrator.db.queries.chief_session_runs import (
        open_questions_on_board,
        run_notice,
    )

    run = run_notice(conn, row["run_id"])
    if run is None:
        return None
    return {
        "run_id": row["run_id"],
        "session_run_id": row["session_run_id"],
        "started_at": row["started_at"],
        "kind": run["kind"],
        "status": run["status"],
        "outcome": run["outcome"],
        "error": run["error"],
        "cost_usd": run["cost_usd"],
        "finished_at": run["finished_at"],
        "open_questions": open_questions_on_board(conn, run["board"] or ""),
    }


@bp.route("/chief/notices", methods=["GET"])
def chief_notices():
    """``{notices: [{run_id, session_run_id, started_at, kind, status, outcome, error, cost_usd,
    finished_at, open_questions}]}``, oldest first. 400 without a ``project_root`` query
    parameter."""
    try:
        project_root = request.args.get("project_root", "")
        if not project_root:
            return jsonify({"error": "Query parameter 'project_root' is required"}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.chief_session_runs import (
            ended_unread_runs,
        )
        from pathly_orchestrator.supervisor.chief_session import (
            normalise_project_root,
        )

        conn = get_db()
        rows = ended_unread_runs(conn, normalise_project_root(project_root))
        found = [_notice(conn, row) for row in rows]
        return jsonify({"notices": [n for n in found if n is not None]}), 200
    except Exception as exc:
        logging.exception("chief_notices error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/chief/notices/read", methods=["POST"])
def chief_notices_read():
    """Mark the project's notices of ``run_ids`` read: 200 ``{marked: <n>}``.

    400 for a missing or non-string ``project_root`` or a ``run_ids`` that is not a list of
    strings; 403 for a live run token.
    """
    try:
        from pathly_orchestrator.http_server.run_identity import caller_identity

        if caller_identity(request).kind == "run":
            return jsonify({"error": "marking notices read is the person's"}), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "A JSON object body is required"}), 400
        project_root = body.get("project_root")
        if not isinstance(project_root, str) or not project_root:
            return jsonify({"error": "Field 'project_root' must be a string"}), 400
        run_ids = body.get("run_ids")
        if not isinstance(run_ids, list) or not all(
            isinstance(r, str) for r in run_ids
        ):
            return (
                jsonify({"error": "Field 'run_ids' must be a list of strings"}),
                400,
            )

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.chief_session_runs import mark_runs_read
        from pathly_orchestrator.supervisor.chief_session import (
            normalise_project_root,
        )

        marked = mark_runs_read(get_db(), normalise_project_root(project_root), run_ids)
        return jsonify({"marked": marked}), 200
    except Exception as exc:
        logging.exception("chief_notices_read error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
