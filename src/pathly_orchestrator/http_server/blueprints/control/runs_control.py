"""Run write API (unified-control-plane) — POST /runs/<run_id>/stop.

The run_id-addressed STOP: resolves a run_id to its live stop mechanism so the Pipeline can halt
ANY run from one place, instead of needing the topic / goal_id / board+scope key. Delegates to
``abort_run`` (FSM flows / team / consultation — run_id lives on a registry RunnerState) or the
board-lock stop (board single/evaluator, goal single/loop — run_id holds a board lock). A
finished / unknown run → ``{stopped: false, reason: "not_active"}``, 200 (idempotent).

Lazy imports INSIDE the handler per the layer rule (http_server may import supervisor/db, but only
inside route functions).
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from ...sse import _broadcast_comms, _broadcast_runner

bp = Blueprint("control_runs_control", __name__)

_ACTIVE = ("running", "paused", "awaiting_decision")


@bp.route("/runs/<run_id>/stop", methods=["POST"])
def stop_run_route(run_id: str):
    """Stop the run identified by ``run_id`` wherever it lives. Idempotent."""
    try:
        from pathly_orchestrator.supervisor import board_lock, get_run
        from pathly_orchestrator.supervisor.api import abort_run
        from pathly_orchestrator.supervisor.registry import _lock, _registry

        # 1. FSM registry run (Studio-Start flow / team / consultation): run_id lives on a
        #    RunnerState keyed by topic. abort_run hard-kills the PTY + sets status=aborted.
        topic = None
        with _lock:
            for t, st in _registry.items():
                if getattr(st, "run_id", "") == run_id and st.status in _ACTIVE:
                    topic = t
                    break
        if topic is not None:
            abort_run(topic, announced=True)
            return (
                jsonify({"ok": True, "stopped": True, "run_id": run_id, "via": "runner_abort"}),
                200,
            )

        # 2. Board-lock run (board single/evaluator, goal single/loop): run_id holds a board.
        #    Mirror /comms/run/stop's kill: TERMINAL_KILL SSE + mark the PTY result + release the
        #    lock (releasing also trips a loop's abort_check, so its scheduler winds down).
        found = board_lock.find_by_holder(run_id)
        if found is not None:
            board, scope = found
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
                from pathly_orchestrator.db.connection import get_db as _get_db
                from pathly_orchestrator.db.queries.comms import post_message as _post_message

                mid = _post_message(
                    _get_db(),
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
                    },
                )
            except Exception:
                pass
            return (
                jsonify({"ok": True, "stopped": True, "run_id": run_id, "via": "board_stop"}),
                200,
            )

        # 3. Not active (finished / unknown) — idempotent no-op.
        return (
            jsonify(
                {"ok": True, "stopped": False, "run_id": run_id, "reason": "not_active"}
            ),
            200,
        )
    except Exception as exc:
        logging.exception("control stop_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
