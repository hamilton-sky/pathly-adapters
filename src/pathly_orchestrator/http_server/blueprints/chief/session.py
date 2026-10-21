"""POST /chief/open, POST /chief/close and GET /chief/session (chief-agent).

A thin layer over ``supervisor/chief_session.py``. Opening and closing a chief are human acts
(Studio's launcher), so both refuse a caller that sends a live run token: an agent cannot open
a chief, and cannot close the one its project has. The limit is the one every human-only route
has: a caller with no token (or an unknown or revoked one) is treated as a human, because the
server cannot tell Studio from a local process until the UI token exists. Refusing the chief's
own token on these routes is the chief gate (ticket 08).

``project_root`` is normalised (``chief_session.normalise_project_root``) on all three routes,
so ``/p`` and ``/p/`` are one project.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("chief_session", __name__)

CLOSE_REASON = "closed from Studio"
_OPEN_FIELDS = ("project_root", "engine", "preset")


def _refuse_agent(action: str):
    """A 403 response when the caller holds a live run token, else None."""
    from pathly_orchestrator.http_server.run_identity import caller_identity

    if caller_identity(request).kind == "run":
        return jsonify({"error": f"{action} is refused for an agent run"}), 403
    return None


def _json_object() -> dict | None:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _kill_tab(session: dict) -> None:
    """Ask the spawn host to kill the chief's tab; the session is closed either way."""
    from ...sse import _broadcast_runner

    run_id = session["run_id"]
    try:
        _broadcast_runner(
            "chief:" + run_id,
            {"type": "TERMINAL_KILL", "tab_id": session["tab_id"], "run_id": run_id},
        )
    except Exception:
        logging.getLogger("pathly.http").warning(
            "chief: could not send TERMINAL_KILL for %s", run_id, exc_info=True
        )


@bp.route("/chief/open", methods=["POST"])
def chief_open():
    """Open a chief for a project: 201 ``{run_id, tab_id, tier, engine}``.

    ``prompt`` is optional (a built-in preset, or the user's ``chief/<preset>`` file, supplies
    the style). 400 for a missing or non-string field or an ``open_chief`` ``ValueError`` (its
    message is passed on; ``custom`` with no prompt is one), 403 for a live run token, 409
    ``{error, run_id, tab_id}`` when the project already has a chief.
    """
    try:
        refused = _refuse_agent("opening a chief")
        if refused is not None:
            return refused
        body = _json_object()
        if body is None:
            return jsonify({"error": "A JSON object body is required"}), 400
        for field in _OPEN_FIELDS:
            if not isinstance(body.get(field), str):
                return jsonify({"error": f"Field '{field}' must be a string"}), 400
        # `model` is optional. So is `prompt`: left out, the style is the user's file for the
        # preset or the built-in text of status, planner and operator; a key that is present
        # must be a string.
        for field in ("model", "prompt"):
            if field in body and not isinstance(body[field], str):
                return jsonify({"error": f"Field '{field}' must be a string"}), 400
        model = body.get("model", "")

        from ...sse import _broadcast_runner
        from pathly_orchestrator.supervisor.chief_session import (
            ChiefAlreadyOpen,
            open_chief,
        )

        try:
            result = open_chief(
                project_root=body["project_root"],
                engine=body["engine"],
                preset=body["preset"],
                prompt=body.get("prompt"),
                model=model,
                broadcast_fn=_broadcast_runner,
            )
        except ChiefAlreadyOpen as exc:
            return (
                jsonify(
                    {"error": str(exc), "run_id": exc.run_id, "tab_id": exc.tab_id}
                ),
                409,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result), 201
    except Exception as exc:
        logging.exception("chief_open error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/chief/close", methods=["POST"])
def chief_close():
    """Close the project's open chief and kill its tab: 200 ``{closed: true|false}``.

    The session is closed first (which revokes its token), then the host is told to kill the
    tab. ``closed`` is false when the project has no open chief, or the watcher closed it first.
    """
    try:
        refused = _refuse_agent("closing a chief")
        if refused is not None:
            return refused
        body = _json_object()
        if body is None:
            return jsonify({"error": "A JSON object body is required"}), 400
        project_root = body.get("project_root")
        if not isinstance(project_root, str) or not project_root:
            return jsonify({"error": "Field 'project_root' must be a string"}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.chief import open_session_for_project
        from pathly_orchestrator.supervisor.chief_session import (
            close_chief,
            normalise_project_root,
        )

        session = open_session_for_project(
            get_db(), normalise_project_root(project_root)
        )
        if session is None:
            return jsonify({"closed": False}), 200
        closed = close_chief(session["run_id"], CLOSE_REASON)
        if closed:
            _kill_tab(session)
        return jsonify({"closed": closed}), 200
    except Exception as exc:
        logging.exception("chief_close error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/chief/session", methods=["GET"])
def chief_session_state():
    """The project's open chief: ``{open: false}`` or ``{open: true, run_id, tab_id, tier,
    engine, opened_at, runs_started, max_runs_per_session, max_cost_usd_per_run}``.

    The last three say why a chief stopped: the runs the session has started, the limit and the
    ceiling for the cost of one run (``chief_budget``). 400 without a ``project_root`` query
    parameter."""
    try:
        project_root = request.args.get("project_root", "")
        if not project_root:
            return jsonify({"error": "Query parameter 'project_root' is required"}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.chief import open_session_for_project
        from pathly_orchestrator.supervisor.chief_session import (
            normalise_project_root,
        )

        from ...chief_budget import ceiling_usd, run_limit

        conn = get_db()
        row = open_session_for_project(conn, normalise_project_root(project_root))
        if row is None:
            return jsonify({"open": False}), 200
        return (
            jsonify(
                {
                    "open": True,
                    "run_id": row["run_id"],
                    "tab_id": row["tab_id"],
                    "tier": row["tier"],
                    "engine": row["engine"],
                    "opened_at": row["opened_at"],
                    "runs_started": row["runs_started"],
                    "max_runs_per_session": run_limit(conn),
                    "max_cost_usd_per_run": ceiling_usd(conn),
                }
            ),
            200,
        )
    except Exception as exc:
        logging.exception("chief_session_state error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
