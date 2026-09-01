"""Task DAG endpoints (/comms/tasks/*)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner
from ._helpers import post_task_status, read_json_body

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

        data = read_json_body()
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

        data = read_json_body()
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


def _release_claim(conn, message_id: str) -> None:
    """Revert an in_progress task back to pending (used when a manual run refuses/fails)."""
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', claimed_by=NULL, claimed_at=NULL "
        "WHERE id=? AND task_status='in_progress'",
        (message_id,),
    )
    conn.commit()


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
        run_id = "task-" + message_id[:8]

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


@bp.route("/comms/tasks/stop", methods=["POST"])
def comms_tasks_stop():
    """Stop a single-task run: kill its board run (if any) and revert the task to pending."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.supervisor import board_lock, get_run

        data = read_json_body({})
        message_id = data.get("message_id", "")
        if not isinstance(message_id, str) or not message_id.strip():
            return (
                jsonify({"error": "Field 'message_id' must be a non-empty string"}),
                400,
            )

        conn = _get_db()
        row = conn.execute(
            "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        if row is None:
            return jsonify({"ok": False, "reason": "not_found"}), 404
        board = row["board"] or "feature"
        scope = row["scope"] or ""

        run_id = board_lock.holder(board, scope)
        if run_id:
            tab_id = f"runner-{run_id[-10:]}"
            try:
                _broadcast_runner(
                    scope, {"type": "TERMINAL_KILL", "tab_id": tab_id, "run_id": run_id}
                )
            except Exception:
                pass
            try:
                run = get_run(run_id)
                if run is not None:
                    run.mark_pty_result(
                        {"exit_code": 130, "result": {"result": "stopped by user"}}
                    )
            except Exception:
                pass
            board_lock.release(board, scope, run_id)

        _release_claim(
            conn, message_id
        )  # in_progress → pending (idempotent; on_done also does this)
        _broadcast_comms(
            scope,
            {
                "type": "COMMS_UPDATE",
                "event": "task_run",
                "message_id": message_id,
                "board": board,
                "scope": scope,
                "phase": "stopped",
            },
        )
        return jsonify({"ok": True, "stopped": bool(run_id)}), 200
    except Exception as exc:
        logging.exception("comms_tasks_stop error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
