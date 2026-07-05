"""Task DAG endpoints (/comms/tasks/*)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms
from ._helpers import post_task_status

bp = Blueprint("comms_tasks", __name__)


@bp.route("/comms/tasks", methods=["GET"])
def comms_tasks_get():
    """Fetch task messages for a feature."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            get_ready_tasks as _get_ready_tasks,
        )
        from pathly_orchestrator.db.queries.comms import get_tasks as _get_tasks

        feature = request.args.get("feature", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400

        board = (request.args.get("board") or "feature").strip() or "feature"
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = (request.args.get("scope") or feature).strip() or feature
        goal_id = request.args.get("goal_id") or None

        conn = _get_db()
        ready_flag = request.args.get("ready", "").strip().lower()
        if ready_flag == "true":
            tasks = _get_ready_tasks(
                conn, boards=[board], scopes=[scope], goal_id=goal_id
            )
        else:
            # Return the goal's tasks with their real DAG task_status. The previous
            # filter on the generic message `status` column was meaningless (it stays
            # 'pending' for a task's whole life) AND it ignored goal_id, so a goal's
            # list could include other goals' tasks. task_status=None keeps completed
            # tasks in the list (the Goals view needs them for duration) but now each
            # carries its true status, so the UI can tell done from pending.
            tasks = _get_tasks(conn, board, scope, goal_id=goal_id)
        # Surface per-task claim→complete duration for the Goals & Tasks view
        # (board-context-pull Solution B). Additive: None until both stamps exist.
        from ._helpers import task_duration_seconds as _duration

        for _t in tasks:
            _t["duration_seconds"] = _duration(_t)
        return jsonify(tasks), 200
    except Exception as exc:
        logging.exception("comms_tasks_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/tasks/complete", methods=["POST"])
def comms_tasks_complete():
    """Mark a task as done and broadcast newly-unblocked tasks."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import complete_task as _complete_task

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )

        conn = _get_db()
        newly_ready = _complete_task(conn, message_id=message_id)
        # Guaranteed per-task progress for the single executor (the drain agent
        # completes via this route). The loop posts the equivalent in-process.
        post_task_status(conn, message_id, "Done")

        scope = data.get("feature") or data.get("scope") or ""
        for nrid in newly_ready:
            _broadcast_comms(
                scope,
                {
                    "type": "COMMS_UPDATE",
                    "message_id": nrid,
                    "event": "task_unblocked",
                    "feature": scope,
                },
            )

        return jsonify({"ok": True, "newly_ready": newly_ready}), 200
    except Exception as exc:
        logging.exception("comms_tasks_complete error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/tasks/claim", methods=["POST"])
def comms_tasks_claim():
    """Atomically claim a pending task (pending → in_progress)."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import claim_task as _claim_task

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        run_id = data.get("run_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )
        if not isinstance(run_id, str) or not run_id.strip():
            return jsonify({"error": "Field 'run_id' must be a non-empty string"}), 400

        conn = _get_db()
        claimed = _claim_task(conn, message_id=message_id, run_id=run_id)
        # Guaranteed 'Started' only on a real claim — a rejected double-claim
        # (already in_progress) must not post a second status.
        if claimed:
            post_task_status(conn, message_id, "Started")
        return jsonify({"claimed": claimed}), 200
    except Exception as exc:
        logging.exception("comms_tasks_claim error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/tasks/fail", methods=["POST"])
def comms_tasks_fail():
    """Mark a task failed and cascade-block transitive dependents."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import fail_task as _fail_task

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )

        reason = data.get("reason") or ""
        conn = _get_db()

        row = conn.execute(
            "SELECT scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        scope = row["scope"] if row is not None else ""

        blocked = _fail_task(conn, message_id=message_id, reason=reason)
        post_task_status(conn, message_id, "Failed", reason=reason)

        _broadcast_comms(
            scope,
            {"type": "COMMS_UPDATE", "event": "task_failed", "message_id": message_id},
        )
        for bid in blocked:
            _broadcast_comms(
                scope,
                {"type": "COMMS_UPDATE", "event": "task_blocked", "message_id": bid},
            )

        return jsonify({"ok": True, "blocked": blocked}), 200
    except Exception as exc:
        logging.exception("comms_tasks_fail error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
