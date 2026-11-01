"""Task claims (/comms/tasks/claim, /comms/tasks/run): ``claimed_by`` names the claiming run.

A caller with a live run token claims as that token's run, whatever ``run_id`` its body sends
(the drain-dag skill sends the literal ``"$GOAL_ID-single"``); a tokenless caller keeps the body
value. ``/comms/tasks/run`` mints its run id first, claims with it, then starts the board run
under that id, so the task names the run that works on it. The loop scheduler claims in-process
as ``sched-<task>#N`` and does not come through here.
"""

from __future__ import annotations

import logging
import uuid

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner
from ._helpers import post_task_status, read_json_body
from .tasks import _release_claim

bp = Blueprint("comms_tasks_claim", __name__)


@bp.route("/comms/tasks/claim", methods=["POST"])
def comms_tasks_claim():
    """Atomically claim a pending task (pending → in_progress)."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import claim_task as _claim_task

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        message_id = data.get("message_id", "")
        run_id = data.get("run_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )
        from pathly_orchestrator.http_server.run_identity import caller_identity

        caller = caller_identity(request)
        if caller.kind == "run" and caller.run_id:
            run_id = (
                caller.run_id
            )  # the token names the run; the body's run_id is ignored
        elif not isinstance(run_id, str) or not run_id.strip():
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


@bp.route("/comms/tasks/run", methods=["POST"])
def comms_tasks_run():
    """Run ONE task headlessly: claim it, spawn a builder on its prompt, complete on success.

    Ad-hoc per-task execution from the Goals & Tasks view — independent of the goal executor's
    single/loop/team strategies. The task's ``text`` IS a self-contained builder prompt.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import claim_task as _claim_task
        from pathly_orchestrator.db.queries.comms import complete_task as _complete_task
        from pathly_orchestrator.supervisor.board_run import start_board_run

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )

        adapter = data.get("adapter", "") or "claude"
        # Model per engine: claude needs an EXPLICIT model — an empty --model mangles the argv and
        # the CLI's own default tier may be inaccessible → the 404 we saw. Non-claude engines take
        # an empty model as "use the engine's own default" (adapters.validate_adapter_model), so we
        # only force a claude model when the engine IS claude.
        model = data.get("model") or (
            "claude-sonnet-4-6" if adapter == "claude" else ""
        )
        project_root = data.get("project_root", "") or ""
        progress = data.get("progress", "") or ""
        # Layer-3 abilities compose after the build skill's fragments; a gate Sections trim
        # (prompt_override) is sent verbatim in place of the composed build prompt.
        ability_ids = data.get("ability_ids")
        if not isinstance(ability_ids, list):
            ability_ids = []
        ability_ids = [a for a in ability_ids if isinstance(a, str)]
        prompt_override = data.get("prompt_override", "") or ""
        if not isinstance(prompt_override, str):
            prompt_override = ""

        conn = _get_db()
        row = conn.execute(
            "SELECT id, board, scope, text, type, task_status FROM comms_messages "
            "WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        if row is None:
            return jsonify({"ok": False, "reason": "not_found"}), 404
        if (row["type"] or "") != "task":
            return jsonify({"ok": False, "reason": "not_task"}), 400
        if row["task_status"] == "done":
            return jsonify({"ok": False, "reason": "already_done"}), 409
        if row["task_status"] == "in_progress":
            return jsonify({"ok": False, "reason": "already_running"}), 409

        board = row["board"] or "feature"
        scope = row["scope"] or ""
        task_text = row["text"] or ""
        # Minted before the claim and handed to the run, so claimed_by names the run that works it.
        run_id = str(uuid.uuid4())

        if not _claim_task(conn, message_id=message_id, run_id=run_id):
            return jsonify({"ok": False, "reason": "busy"}), 409
        post_task_status(conn, message_id, "Started")

        def _emit(phase: str) -> None:
            _broadcast_comms(
                scope,
                {
                    "type": "COMMS_UPDATE",
                    "event": "task_run",
                    "message_id": message_id,
                    "board": board,
                    "scope": scope,
                    "phase": phase,
                },
            )

        def _on_done(_rid: str, res) -> None:
            c = _get_db()
            # A clean process exit does NOT mean the task succeeded: a CLI that 404s / rejects the
            # model exits with is_error/api_error_status set (subtype may even say "success"), which
            # a bare `error` check misses. Reuse the supervisor's failure guard AND the CLI's own
            # is_error flag so a failed run reverts to pending instead of being marked done.
            from pathly_orchestrator.supervisor.scheduler import _outcome_is_failure

            failed = isinstance(res, dict) and (
                res.get("error")
                or res.get("is_error")
                or res.get("api_error_status")
                or _outcome_is_failure(res)
            )
            if failed:
                _release_claim(
                    c, message_id
                )  # let it be retried; don't cascade-fail dependents
                post_task_status(c, message_id, "Run failed")
                _emit("error")
                return
            newly_ready = _complete_task(c, message_id=message_id)
            post_task_status(c, message_id, "Done")
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
            _emit("done")

        instructions = (
            "Build EXACTLY this one task and nothing else — it is a self-contained builder prompt "
            "(what to build · Files · Done when). Do not start other tasks.\n\n"
            + task_text
        )
        result = start_board_run(
            board,
            scope,
            "single-agent",
            instructions=instructions,
            project_root=project_root,
            model=model,
            adapter=adapter,
            skill="development/build",
            ability_ids=ability_ids or None,
            prompt_override=prompt_override or "",
            progress=progress,
            broadcast_fn=_broadcast_runner,
            on_done=_on_done,
            run_id=run_id,
        )
        if isinstance(result, dict) and result.get("ok"):
            _emit("running")
            return (
                jsonify(
                    {
                        "ok": True,
                        "run_id": result.get("run_id"),
                        "message_id": message_id,
                    }
                ),
                200,
            )

        _release_claim(
            conn, message_id
        )  # spawn refused (board busy, etc.) → free the claim
        reason = (result or {}).get("reason") or "spawn_failed"
        return jsonify(result or {"ok": False, "reason": reason}), (
            409 if reason == "board_busy" else 400
        )
    except Exception as exc:
        logging.exception("comms_tasks_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
