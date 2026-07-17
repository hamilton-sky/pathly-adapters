"""Goal executor dispatching endpoints (/comms/goals/*)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ...sse import _broadcast_comms, _broadcast_runner

bp = Blueprint("comms_goals", __name__)


@bp.route("/comms/goals/run", methods=["POST"])
def comms_goals_run():
    """Dispatch a goal's task-DAG to its executor."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message
        from pathly_orchestrator.supervisor.goal_run import start_goal_run

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        goal_id = data.get("goal_id", "")
        if not isinstance(goal_id, str) or not goal_id.strip():
            return jsonify({"error": "Field 'goal_id' must be a non-empty string"}), 400

        executor_override = data.get("executor")
        if executor_override is not None and not isinstance(executor_override, str):
            return jsonify({"error": "Field 'executor' must be a string or null"}), 400
        flow_override = data.get("flow")
        if flow_override is not None and not isinstance(flow_override, str):
            return jsonify({"error": "Field 'flow' must be a string or null"}), 400

        adapter = data.get("adapter", "") or "claude"
        model = data.get("model", "") or ""
        project_root = data.get("project_root", "") or ""
        # "" (unset) lets start_board_run resolve the app-wide default from Settings.
        progress = data.get("progress", "") or ""

        conn = _get_db()
        goal = conn.execute(
            "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (goal_id,),
        ).fetchone()
        board = goal["board"] if goal is not None else "feature"
        scope = goal["scope"] if goal is not None else ""

        def _board_post(text: str, phase: str | None = None) -> None:
            try:
                c = _get_db()
                mid = _post_message(
                    c,
                    board=board,
                    scope=scope,
                    from_agent="system",
                    type="status",
                    text=text,
                )
                payload = {
                    "type": "COMMS_UPDATE",
                    "event": "goal_run",
                    "goal_id": goal_id,
                    "message_id": mid,
                    "board": board,
                    "scope": scope,
                }
                if phase:
                    payload["phase"] = phase
                _broadcast_comms(scope, payload)
            except Exception:
                logging.debug("goal_run lifecycle post failed", exc_info=True)

        def _on_start(_run_id: str) -> None:
            _board_post("goal run started — dispatching executor…", phase="running")

        def _on_done(_run_id: str, res) -> None:
            # A user stop / crash must still clear the board's "Running…" timer pill —
            # never mislabel a killed or errored run as "finished".
            if isinstance(res, dict) and res.get("error"):
                if res.get("announced"):
                    return
                err = str(res.get("error"))
                low = err.lower()
                if (
                    res.get("status") == "aborted"
                    or "stop" in low
                    or "abort" in low
                    or "kill" in low
                ):
                    _board_post("goal run stopped", phase="stopped")
                    return
                _board_post(f"goal run failed — {err[:300]}", phase="error")
                return
            summary = ""
            if isinstance(res, dict):
                ex = res.get("executor", "")
                done = res.get("completed")
                summary = f"executor={ex}"
                if isinstance(done, list):
                    summary += f", completed={len(done)}"
            _board_post(f"goal run finished — {summary}", phase="done")

        result = start_goal_run(
            goal_id,
            executor_override=executor_override,
            flow_override=flow_override,
            project_root=project_root,
            adapter=adapter,
            model=model,
            progress=progress,
            broadcast_fn=_broadcast_runner,
            event_broadcast_fn=_broadcast_comms,
            on_start=_on_start,
            on_done=_on_done,
        )

        if result.get("ok"):
            return jsonify(result), 200
        reason = result.get("reason") or result.get("error") or ""
        status = {
            "not_found": 404,
            "not_goal": 400,
            "board_busy": 409,
            "project_busy": 409,
            "unknown_executor": 400,
            "unknown_flow": 400,
        }.get(reason, 400)
        return jsonify(result), status
    except Exception as exc:
        logging.exception("comms_goals_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/goals/refs-coverage", methods=["GET"])
def comms_goals_refs_coverage():
    """Report per-goal context_refs coverage (tasks-with-refs / total) — CT3/T3c.

    Makes the ISSUE-4 gap visible to a human before dispatch: a low coverage_pct means
    many tasks have no curated refs and will fall back to unverified auto-derived context.
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import goal_refs_coverage as _coverage

        goal_id = (request.args.get("goal_id") or "").strip()
        if not goal_id:
            return jsonify({"error": "Query parameter 'goal_id' is required"}), 400
        return jsonify(_coverage(_get_db(), goal_id)), 200
    except Exception as exc:
        logging.exception("comms_goals_refs_coverage error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/goals/stop", methods=["POST"])
def comms_goals_stop():
    """Stop the executor running for a goal."""
    try:
        from pathly_orchestrator.supervisor import board_lock, get_run
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message

        data = request.get_json() or {}
        goal_id = data.get("goal_id", "")
        if not isinstance(goal_id, str) or not goal_id.strip():
            return jsonify({"error": "Field 'goal_id' must be a non-empty string"}), 400

        conn = _get_db()
        row = conn.execute(
            "SELECT board, scope, type FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (goal_id,),
        ).fetchone()
        if row is None:
            return jsonify({"ok": False, "reason": "not_found"}), 404
        if row["type"] != "goal":
            return jsonify({"ok": False, "reason": "not_goal"}), 400

        board = row["board"] or "feature"
        scope = row["scope"] or ""
        stopped = False
        how = None
        run_id = None

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
            stopped = True
            how = "board_run"
        else:
            from pathly_orchestrator.supervisor.registry import get_state

            st = get_state(scope)
            if st is not None and st.status in (
                "running",
                "paused",
                "awaiting_decision",
            ):
                from pathly_orchestrator.supervisor.api import abort_run

                # announced=True: this route posts the "stopped" board message itself
                # below, so the run's on_done must stay quiet (no double-announce).
                abort_run(scope, announced=True)
                stopped = True
                how = "fsm"

        if stopped:
            try:
                mid = _post_message(
                    conn,
                    board=board,
                    scope=scope,
                    from_agent="system",
                    type="status",
                    text="⏹ goal run stopped by user",
                )
                _broadcast_comms(
                    scope,
                    {
                        "type": "COMMS_UPDATE",
                        "event": "goal_run",
                        "goal_id": goal_id,
                        "message_id": mid,
                        "board": board,
                        "scope": scope,
                        "phase": "stopped",
                    },
                )
            except Exception:
                pass
            return (
                jsonify({"ok": True, "stopped": True, "how": how, "run_id": run_id}),
                200,
            )

        return jsonify({"ok": True, "stopped": False, "reason": "not_running"}), 200
    except Exception as exc:
        logging.exception("comms_goals_stop error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/comms/goals/decompose", methods=["POST"])
def comms_goals_decompose():
    """Decompose a goal into a task DAG."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import post_message as _post_message
        from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        goal_id = data.get("goal_id", "")
        if not isinstance(goal_id, str) or not goal_id.strip():
            return jsonify({"error": "Field 'goal_id' must be a non-empty string"}), 400
        mode = data.get("mode", "") or "planner"
        if not isinstance(mode, str):
            return jsonify({"error": "Field 'mode' must be a string"}), 400
        adapter = data.get("adapter", "") or "claude"
        model = data.get("model", "") or ""
        project_root = data.get("project_root", "") or ""
        # "" (unset) lets start_board_run resolve the app-wide default from Settings.
        progress = data.get("progress", "") or ""
        # Layer-3 abilities (compose after the planner skill's fragments) + a gate "use once"
        # Sections trim. Both apply only to the single-agent decomposers (planner/plan); the
        # consultation FSM flow has no single prompt to override, so it ignores them.
        ability_ids = data.get("ability_ids")
        if not isinstance(ability_ids, list):
            ability_ids = []
        ability_ids = [a for a in ability_ids if isinstance(a, str)]
        prompt_override = data.get("prompt_override", "") or ""
        if not isinstance(prompt_override, str):
            prompt_override = ""

        conn = _get_db()
        goal = conn.execute(
            "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (goal_id,),
        ).fetchone()
        board = goal["board"] if goal is not None else "feature"
        scope = goal["scope"] if goal is not None else ""

        def _board_post(text: str, phase: str | None = None) -> None:
            try:
                c = _get_db()
                mid = _post_message(
                    c,
                    board=board,
                    scope=scope,
                    from_agent="system",
                    type="status",
                    text=text,
                )
                payload = {
                    "type": "COMMS_UPDATE",
                    "event": "goal_decompose",
                    "goal_id": goal_id,
                    "message_id": mid,
                    "board": board,
                    "scope": scope,
                }
                if phase:
                    payload["phase"] = phase
                _broadcast_comms(scope, payload)
            except Exception:
                logging.debug("goal_decompose lifecycle post failed", exc_info=True)

        def _on_start(_run_id: str) -> None:
            _board_post(f"🧩 decomposing goal via {mode}…", phase="running")

        def _on_done(_run_id: str, res) -> None:
            if isinstance(res, dict) and res.get("error"):
                # The ■ Stop route already posted "stopped" before aborting — stay quiet so
                # the stop isn't announced twice.
                if res.get("announced"):
                    return
                err = str(res.get("error"))
                low = err.lower()
                # A user stop (killed runner tab → abort) clears the pill as "stopped", not
                # "failed" — only a genuine crash is a failure. Either way we MUST post a
                # phase, or the board's "Decomposing…" timer pill ticks forever.
                if (
                    res.get("status") == "aborted"
                    or "stop" in low
                    or "abort" in low
                    or "kill" in low
                ):
                    _board_post("decomposition stopped", phase="stopped")
                    return
                _board_post(f"decomposition failed — {err[:300]}", phase="error")
                return
            _board_post("decomposition finished — task DAG seeded", phase="done")

        result = start_goal_decompose(
            goal_id,
            mode=mode,
            project_root=project_root,
            adapter=adapter,
            model=model,
            progress=progress,
            ability_ids=ability_ids or None,
            prompt_override=prompt_override,
            broadcast_fn=_broadcast_runner,
            on_start=_on_start,
            on_done=_on_done,
        )

        if result.get("ok"):
            return jsonify(result), 200
        reason = result.get("reason") or result.get("error") or ""
        status = {
            "not_found": 404,
            "not_goal": 400,
            "unknown_mode": 400,
            "already_decomposed": 409,
            "board_busy": 409,
        }.get(reason, 400)
        return jsonify(result), status
    except Exception as exc:
        logging.exception("comms_goals_decompose error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
