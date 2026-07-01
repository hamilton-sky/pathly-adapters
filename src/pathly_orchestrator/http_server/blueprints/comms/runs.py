"""Board run management endpoints (/comms/run, /comms/run/stop)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner

bp = Blueprint("comms_runs", __name__)


@bp.route("/comms/run", methods=["POST"])
def comms_run():
    """Spawn a single-agent board run."""
    try:
        from pathly_orchestrator.supervisor.board_run import start_board_run

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        board = data.get("board", "feature")
        scope = data.get("scope")
        mode = data.get("mode", "single-agent")
        instructions = data.get("instructions", "") or ""
        project_root = data.get("project_root", "") or ""
        agent = data.get("agent", "") or ""
        skill = data.get("skill", "") or ""
        system_prompt = data.get("system_prompt", "") or ""
        interactive = bool(data.get("interactive", False))

        progress = (data.get("progress", "") or "normal").strip().lower()
        if progress not in ("quiet", "normal", "verbose"):
            progress = "normal"

        _DEFAULT_MODEL = {"claude": "claude-sonnet-4-6", "codex": "gpt-5.4"}
        adapter = (data.get("adapter", "") or "claude").strip().lower()
        if adapter not in _DEFAULT_MODEL:
            adapter = "claude"
        model = data.get("model", "") or _DEFAULT_MODEL[adapter]

        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"

        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message

        def _board_post(text: str, phase: str | None = None) -> None:
            try:
                conn = _get_db()
                mid = _post_message(
                    conn,
                    board=board,
                    scope=scope,
                    from_agent="system",
                    type="status",
                    text=text,
                )
                payload = {
                    "type": "COMMS_UPDATE",
                    "event": "board_run",
                    "message_id": mid,
                    "board": board,
                    "scope": scope,
                }
                if phase:
                    payload["phase"] = phase
                _broadcast_comms(scope, payload)
            except Exception:
                logging.debug("board_run lifecycle post failed", exc_info=True)

        label = agent if isinstance(agent, str) and agent else mode

        def _on_start(_run_id: str) -> None:
            _board_post(
                f"🤖 {label} started on this board… (via {adapter})", phase="running"
            )

        def _on_done(_run_id: str, res) -> None:
            summary = ""
            if isinstance(res, dict):
                summary = str(res.get("result") or res.get("summary") or "done")
            _board_post(
                f"✅ {label} finished via {adapter} — {summary[:280]}", phase="done"
            )

        result = start_board_run(
            board,
            scope,
            mode,
            instructions,
            project_root=project_root,
            adapter=adapter,
            model=model,
            agent=agent if isinstance(agent, str) else "",
            skill=skill if isinstance(skill, str) else "",
            system_prompt=system_prompt if isinstance(system_prompt, str) else "",
            interactive=interactive,
            progress=progress,
            broadcast_fn=_broadcast_runner,
            on_start=_on_start,
            on_done=_on_done,
        )

        if not result.get("ok"):
            return (
                jsonify({"ok": False, "error": result.get("error", "board_busy")}),
                409,
            )

        return jsonify(result), 200
    except Exception as exc:
        logging.exception("comms_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/run/stop", methods=["POST"])
def comms_run_stop():
    """Stop the agent currently running on a board."""
    try:
        from pathly_orchestrator.supervisor import board_lock, get_run
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message

        data = request.get_json() or {}
        board = data.get("board", "feature")
        scope = data.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        if not isinstance(board, str) or board not in ("feature", "project", "global"):
            board = "feature"

        run_id = board_lock.holder(board, scope)
        if not run_id:
            return jsonify({"ok": True, "stopped": False, "reason": "not_running"}), 200

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
                    {"exit_code": 0, "result": {"result": "stopped by user"}}
                )
        except Exception:
            pass
        board_lock.release(board, scope, run_id)

        try:
            conn = _get_db()
            mid = _post_message(
                conn,
                board=board,
                scope=scope,
                from_agent="system",
                type="status",
                text="⏹ run stopped by user",
            )
            _broadcast_comms(
                scope,
                {
                    "type": "COMMS_UPDATE",
                    "event": "board_run",
                    "message_id": mid,
                    "board": board,
                    "scope": scope,
                    "phase": "stopped",
                },
            )
        except Exception:
            pass

        return jsonify({"ok": True, "stopped": True, "run_id": run_id}), 200
    except Exception as exc:
        logging.exception("comms_run_stop error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/run/status", methods=["GET"])
def comms_run_status():
    """Report whether a board currently has an active runner (board-lock held).

    Lets Studio reconcile a board-run pill WITHOUT depending on the comms SSE: the
    store polls this while a run is 'running' and clears the pill once the lock
    releases — so a run that finishes while the board is unmounted (the user
    navigated away) still lands. Mirrors the editor's client-side completion poll.
    """
    try:
        from pathly_orchestrator.supervisor import board_lock

        board = request.args.get("board", "feature")
        scope = request.args.get("scope", "")
        if board not in ("feature", "project", "global"):
            board = "feature"
        if not isinstance(scope, str) or not scope.strip():
            return jsonify({"error": "Field 'scope' is required"}), 400
        return (
            jsonify(
                {
                    "ok": True,
                    "running": board_lock.is_locked(board, scope),
                    "holder": board_lock.holder(board, scope),
                }
            ),
            200,
        )
    except Exception as exc:
        logging.exception("comms_run_status error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
