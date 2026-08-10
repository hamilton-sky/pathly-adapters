"""Run write API (unified-control-plane) — POST /runs/<run_id>/stop, /runs/<run_id>/<action>.

The run_id-addressed control surface: resolves a run_id to its live control mechanism so the
Pipeline can act on ANY run from one place, instead of needing the topic / goal_id / board+scope
key. Delegates to the exact functions the existing ``/runner/*`` control routes call
(``pause_run``/``resume_run``/``abort_run``/``reroute_run``/``start_run`` in
``supervisor/api.py``) — never reinventing the control logic. Resolution + the shared
abort/stop + retry bodies live in ``_helpers.py`` so this file stays under the 400-line cap.

- ``stop``/``abort``: registry (FSM flows/team/consultation) → ``abort_run``, else a board-lock
  holder (board single/evaluator, goal single/loop) → board stop, else ``not_active``.
- ``pause``/``resume``/``advance``/``reroute``: only meaningful against an ACTIVE registry run;
  a board-lock run returns ``{"ok": false, "reason": "unsupported_for_kind"}``.
- ``retry``: registry lookup across ANY status (a retry targets a FINISHED run); an active run
  or a board-lock run are both rejected (``already_active`` / ``unsupported_for_kind``).
- A finished/unknown run_id → ``{"ok": false, "reason": "not_active"}``, 200 (idempotent).

Lazy imports INSIDE the handler per the layer rule (http_server may import supervisor/db, but
only inside route functions).
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("control_runs_control", __name__)

_ALLOWED_ACTIONS = frozenset({"pause", "resume", "advance", "reroute", "retry", "abort"})


@bp.route("/runs/<run_id>/stop", methods=["POST"])
def stop_run_route(run_id: str):
    """Stop the run identified by ``run_id`` wherever it lives. Idempotent."""
    try:
        from ._helpers import resolve_and_abort

        payload, status = resolve_and_abort(run_id)
        return jsonify(payload), status
    except Exception as exc:
        logging.exception("control stop_run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runs/<run_id>/<action>", methods=["POST"])
def run_action_route(run_id: str, action: str):
    """Perform ``action`` on the run identified by ``run_id``, wherever it lives."""
    if action not in _ALLOWED_ACTIONS:
        return (
            jsonify(
                {
                    "error": f"Unknown action {action!r}; must be one of "
                    f"{sorted(_ALLOWED_ACTIONS)}"
                }
            ),
            400,
        )
    try:
        from ._helpers import ACTIVE_STATUSES, find_registry_run, handle_retry, resolve_and_abort

        if action == "abort":
            payload, status = resolve_and_abort(run_id)
            return jsonify(payload), status

        body = request.get_json(silent=True) or {}
        lookup_statuses = None if action == "retry" else ACTIVE_STATUSES
        found = find_registry_run(run_id, statuses=lookup_statuses)

        if found is None:
            from pathly_orchestrator.supervisor import board_lock

            if board_lock.find_by_holder(run_id) is not None:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "run_id": run_id,
                            "action": action,
                            "reason": "unsupported_for_kind",
                        }
                    ),
                    200,
                )
            return (
                jsonify(
                    {"ok": False, "run_id": run_id, "action": action, "reason": "not_active"}
                ),
                200,
            )
        topic, state = found

        if action == "retry":
            payload, status = handle_retry(run_id, topic, state, body)
            return jsonify(payload), status

        from pathly_orchestrator.supervisor.api import pause_run, reroute_run, resume_run

        if action == "pause":
            pause_run(topic)
        elif action in ("resume", "advance"):
            resume_run(topic)
        else:  # reroute
            adapter = body.get("adapter", "")
            if not isinstance(adapter, str) or not adapter.strip():
                return jsonify({"error": "Field 'adapter' must be a non-empty string"}), 400
            reroute_run(topic, adapter)
            return (
                jsonify(
                    {
                        "ok": True,
                        "run_id": run_id,
                        "action": action,
                        "topic": topic,
                        "adapter": adapter,
                        "stage": body.get("stage"),
                    }
                ),
                200,
            )

        return jsonify({"ok": True, "run_id": run_id, "action": action, "topic": topic}), 200
    except Exception as exc:
        logging.exception("control run_action error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
