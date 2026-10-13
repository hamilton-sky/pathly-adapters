"""POST /comms/tasks/status — bulk task-state write-back for resolving agents.

The gap this closes: an agent that RESOLVES something has, until now, had no way to say so
in the board's system of record. On a representative board the evaluator was the most
expensive role on the run and its BOARD_EVAL.md ended with the sentence "Mark tasks
726aecdd, 4a0a6706, b7d9a7af as COMPLETE." Fourteen days later all three were still
``task_status='pending'``, ``attempts=0``, ``claimed_by=null`` — the resolution existed
only as prose in a markdown file while the board still said the work was open.

``/comms/tasks/complete`` already existed, but it is single-id and shaped for the executor's
drain loop (claim → work → complete). A resolving agent needs the OTHER shape: name the set
of tasks its analysis just settled, in one call, with a reason. Asking it to emit N curl
calls is how "mark complete" stays a sentence — the failure mode is the agent doing 0 of N,
not 3 of 5.

Scope is deliberately ``done`` and ``failed`` only:

* ``done``   — this task is settled; dependents unblock (via ``complete_task``).
* ``failed`` — this task cannot proceed; dependents cascade to ``blocked`` (via ``fail_task``).

Only an agent run may call it, and only for its own board: the caller must send a live
``X-Pathly-Run-Token``, each task must sit on the token's board and scope, and the audit line
is stamped as that caller. Without that, any process could mark every task done and walk a
run straight through the ``->DONE: require_tasks_done`` gate.

Re-opening a task (→ ``pending``) is NOT offered. Reopening is a supervisory act with a
human or an executor behind it (``reclaim_stale_tasks``, the Studio controls), and an agent
that can silently reopen its own failures can loop forever without anything closing.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms
from ._helpers import read_json_body

bp = Blueprint("comms_tasks_status", __name__)

# Same bound as the supersedes list — one call settles a batch, not a whole board.
MAX_TASK_IDS = 50
_ALLOWED = ("done", "failed")


def _collect_ids(data: dict) -> list[str]:
    """Accept ``task_ids: [...]`` or a single ``task_id``/``message_id``, de-duplicated."""
    raw = data.get("task_ids")
    if raw is None:
        one = data.get("task_id") or data.get("message_id")
        raw = [one] if isinstance(one, str) else []
    if not isinstance(raw, list):
        return []
    ids = [v.strip() for v in raw if isinstance(v, str) and v.strip()]
    return list(dict.fromkeys(ids))  # de-duplicated, order kept


@bp.route("/comms/tasks/status", methods=["POST"])
def comms_tasks_status():
    """Set a batch of tasks to a terminal state, with a reason, in one call."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import (
            complete_task as _complete_task,
            fail_task as _fail_task,
        )

        from pathly_orchestrator.http_server.run_identity import caller_identity

        identity = caller_identity(request)
        if identity.kind != "run" or not identity.board or not identity.scope:
            return (
                jsonify({"error": "needs a live X-Pathly-Run-Token (an agent run)"}),
                403,
            )
        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        status = str(data.get("status") or "").strip().lower()
        if status not in _ALLOWED:
            return (
                jsonify(
                    {
                        "error": f"Field 'status' must be one of {', '.join(_ALLOWED)}",
                        "note": "re-opening a task is a supervisory action, not an agent one",
                    }
                ),
                400,
            )

        task_ids = _collect_ids(data)
        if not task_ids:
            return (
                jsonify({"error": "Field 'task_ids' must be a non-empty list of ids"}),
                400,
            )
        if len(task_ids) > MAX_TASK_IDS:
            return jsonify({"error": f"At most {MAX_TASK_IDS} task ids per call"}), 400

        reason = data.get("reason")
        reason = reason.strip() if isinstance(reason, str) else ""
        scope = identity.scope

        conn = _get_db()
        updated: list[str] = []
        refused: list[str] = []
        newly_ready: list[str] = []
        cascaded: list[str] = []

        for tid in task_ids:
            # Existence check first: complete_task/fail_task both return [] for an unknown id
            # AND for an already-terminal one, so their return value cannot distinguish
            # "you named a stale id" from "it was already done" — and an agent that gets
            # ok:true for a typo'd id learns nothing.
            row = conn.execute(
                "SELECT task_status, board, scope, text FROM comms_messages "
                "WHERE id=? AND type='task' AND deleted_at IS NULL",
                (tid,),
            ).fetchone()
            if row is None:
                continue
            if (row["board"], row["scope"]) != (identity.board, identity.scope):
                refused.append(tid)  # another board's task: not this run's to settle
                continue
            if row["task_status"] == status:
                updated.append(tid)  # idempotent: already where the caller wants it
                continue
            if status == "done":
                newly_ready.extend(_complete_task(conn, message_id=tid))
            else:
                cascaded.extend(_fail_task(conn, message_id=tid, reason=reason))
            _audit_line(conn, request, row, status, reason)
            updated.append(tid)
            _broadcast_comms(
                scope,
                {
                    "type": "COMMS_UPDATE",
                    "message_id": tid,
                    "event": "task_done" if status == "done" else "task_failed",
                    "feature": scope,
                },
            )

        unknown = [t for t in task_ids if t not in updated and t not in refused]

        for mid in set(newly_ready) | set(cascaded):
            _broadcast_comms(
                scope,
                {
                    "type": "COMMS_UPDATE",
                    "message_id": mid,
                    "event": (
                        "task_unblocked" if mid in newly_ready else "task_blocked"
                    ),
                    "feature": scope,
                },
            )

        resp = {
            "ok": True,
            "status": status,
            "updated": updated,
            "newly_ready": sorted(set(newly_ready)),
        }
        if cascaded:
            resp["blocked"] = sorted(set(cascaded))
        if unknown:
            # Surfaced, never silently dropped — a resolving agent naming a stale id must
            # find out, because its whole contribution is knowing which tasks are settled.
            resp["unknown"] = unknown
        if refused:
            resp["refused"] = refused
        return jsonify(resp), 200
    except Exception as exc:
        logging.exception("comms_tasks_status error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


def _audit_line(conn, request, row, status: str, reason: str) -> None:
    """Post the task's Done/Failed status line, stamped as the calling run. Best-effort."""
    try:
        from pathly_orchestrator.db.queries.comms import post_message
        from pathly_orchestrator.http_server.run_identity import caller_identity
        from pathly_orchestrator.runner.provenance import stamp

        verb = "Done" if status == "done" else "Failed"
        text = row["text"] or ""
        line = (
            f"{verb}: {text[:80]} — {reason[:80]}"
            if reason
            else f"{verb}: {text[:110]}"
        )
        post_message(
            conn,
            board=row["board"],
            scope=row["scope"],
            from_agent=caller_identity(request).role or "agent",
            type="status",
            text=line,
            **stamp(caller_identity(request)),
        )
    except Exception:
        logging.debug("tasks/status audit line failed", exc_info=True)
