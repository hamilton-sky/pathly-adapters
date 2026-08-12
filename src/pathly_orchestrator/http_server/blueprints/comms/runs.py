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
        # Layer-3 abilities: prompt_library row ids to compose after the skill's fragments.
        ability_ids = data.get("ability_ids")
        if not isinstance(ability_ids, list):
            ability_ids = []
        ability_ids = [a for a in ability_ids if isinstance(a, str)]
        # Gate "use once" Sections trim: an explicit prompt that overrides composition.
        prompt_override = data.get("prompt_override", "") or ""
        interactive = bool(data.get("interactive", False))

        # "" (unset) is passed through so start_board_run resolves the app-wide default
        # from Settings; an explicit quiet/normal/verbose overrides it for this run.
        progress = (data.get("progress", "") or "").strip().lower()
        if progress not in ("quiet", "normal", "verbose"):
            progress = ""

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

        def _board_post(
            text: str, phase: str | None = None, run_id: str | None = None
        ) -> None:
            try:
                conn = _get_db()
                mid = _post_message(
                    conn,
                    board=board,
                    scope=scope,
                    from_agent="system",
                    type="status",
                    text=text,
                    run_id=run_id,
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
                f"{label} started on this board… (via {adapter})",
                phase="running",
                run_id=_run_id,
            )

        def _on_done(_run_id: str, res) -> None:
            summary = ""
            if isinstance(res, dict):
                summary = str(res.get("result") or res.get("summary") or "done")
            _board_post(
                f"{label} finished via {adapter} — {summary[:280]}",
                phase="done",
                run_id=_run_id,
            )
            # Backstop for evaluate.md Step 3: an evaluator run MUST post a BOARD_EVAL analysis
            # artifact. If it finished cleanly WITHOUT one (agent answered as free-form text /
            # discovery instead), warn the human so a text-only reply isn't mistaken for a real
            # evaluation. Windowed to this run so a stale prior artifact doesn't mask a miss.
            if mode == "evaluator" and not (isinstance(res, dict) and res.get("error")):
                try:
                    from datetime import datetime, timedelta, timezone

                    c = _get_db()
                    cutoff = (
                        datetime.now(timezone.utc) - timedelta(minutes=15)
                    ).isoformat()
                    has_eval = c.execute(
                        "SELECT 1 FROM comms_messages WHERE scope=? AND type='artifact' "
                        "AND deleted_at IS NULL AND ts >= ? "
                        "AND (artifact_path LIKE '%BOARD_EVAL%' OR text LIKE '%BOARD_EVAL%') LIMIT 1",
                        (scope, cutoff),
                    ).fetchone()
                    if not has_eval:
                        # SALVAGE the analysis instead of only warning. The agent commonly
                        # over-applies Step 4's "DAG already exists → skip" to the WHOLE run and
                        # returns a text-only reply — but Step 3 (the BOARD_EVAL artifact) is
                        # evaluate's mandatory primary deliverable and must always exist. Capture
                        # the run's reply AS that artifact so a re-run isn't required.
                        reply = (summary or "").strip()
                        trivial = reply.lower() in (
                            "",
                            "done",
                            "finished",
                            "complete",
                            "ok",
                        )
                        saved = False
                        if project_root and not trivial:
                            try:
                                import os as _os

                                sub = (
                                    _os.path.join("pathly", "project")
                                    if board == "project"
                                    else _os.path.join("pathly", "features", scope)
                                )
                                art_dir = _os.path.join(project_root, sub, "artifacts")
                                _os.makedirs(art_dir, exist_ok=True)
                                art_path = _os.path.join(art_dir, "BOARD_EVAL.md")
                                with open(art_path, "w", encoding="utf-8") as _f:
                                    _f.write(
                                        "# Board Evaluation\n\n"
                                        "_Auto-captured from the evaluate run's reply — the agent "
                                        "returned a text-only answer instead of posting the "
                                        "artifact itself._\n\n" + reply + "\n"
                                    )
                                mid = _post_message(
                                    c,
                                    board=board,
                                    scope=scope,
                                    from_agent="evaluator",
                                    type="artifact",
                                    text=(
                                        "Board evaluation (auto-captured from the run reply). "
                                        + reply[:200]
                                    ),
                                    artifact_path=art_path.replace("\\", "/"),
                                    artifact_type="md",
                                )
                                _broadcast_comms(
                                    scope,
                                    {
                                        "type": "COMMS_UPDATE",
                                        "event": "board_run",
                                        "message_id": mid,
                                        "board": board,
                                        "scope": scope,
                                        "phase": "done",
                                    },
                                )
                                saved = True
                            except Exception:
                                logging.debug(
                                    "evaluator BOARD_EVAL salvage-write failed",
                                    exc_info=True,
                                )
                        if not saved:
                            # Nothing meaningful to salvage → keep the original warning.
                            mid = _post_message(
                                c,
                                board=board,
                                scope=scope,
                                from_agent="system",
                                type="warning",
                                text=(
                                    "Evaluate finished but posted no BOARD_EVAL analysis artifact — "
                                    "the run returned only a text reply. Re-run Evaluate; if the board "
                                    "already has a goal/task DAG, the evaluator must still post the "
                                    "analysis artifact (it may skip only the goal/task proposals)."
                                ),
                            )
                            _broadcast_comms(
                                scope,
                                {
                                    "type": "COMMS_UPDATE",
                                    "event": "board_run",
                                    "message_id": mid,
                                    "board": board,
                                    "scope": scope,
                                    "phase": "warning",
                                },
                            )
                except Exception:
                    logging.debug("evaluator BOARD_EVAL backstop failed", exc_info=True)

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
            ability_ids=ability_ids or None,
            prompt_override=prompt_override if isinstance(prompt_override, str) else "",
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
