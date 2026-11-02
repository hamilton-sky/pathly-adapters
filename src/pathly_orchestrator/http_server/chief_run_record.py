"""Record the runs a chief session starts (chief-autopilot 08).

``record_chief_run`` is an ``after_request`` hook. It acts on the request the chief gate marked
as a start that took a run slot (``flask.g.chief_run_slot``, set by ``chief_budget.budget_refusal``
for ``STARTS_A_RUN`` and the ``retry`` verb, holding the session's run id). It must run before
``chief_budget.refund_run_slot``, which pops that mark: ``app.py`` registers it after the refund
hook, because Flask runs ``after_request`` hooks in reverse order of registration.

A row is recorded only for a 2xx whose JSON body says ``ok`` and names a ``run_id``: a ``retry``
of a run that is still active (or not found, or of a kind that cannot retry) answers 200 with
``ok: false`` and the OLD run id, which started nothing. The project root is the session's own
(``chief_sessions.project_root``), never the request body's. A failure is logged and the response
goes out unchanged: recording must never turn an answer into a 500.
"""

from __future__ import annotations

import logging

from flask import g


def _started_run_id(response) -> str | None:
    """The run a 2xx ``{ok: true, run_id}`` answer started, else None."""
    if not 200 <= response.status_code < 300 or not response.is_json:
        return None
    body = response.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("ok"):
        return None
    run_id = body.get("run_id")
    return run_id if isinstance(run_id, str) and run_id else None


def record_chief_run(response):
    """``after_request``: record the run a chief's start call began."""
    session_run_id = g.get("chief_run_slot")
    if session_run_id is None:
        return response
    try:
        run_id = _started_run_id(response)
        if run_id is None:
            return response
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.chief import get_session
        from pathly_orchestrator.db.queries.chief_session_runs import (
            record_session_run,
        )

        conn = get_db()
        session = get_session(conn, session_run_id)
        if session is None:
            return response
        record_session_run(conn, session_run_id, run_id, session["project_root"])
    except Exception:
        logging.getLogger("pathly.http").warning(
            "chief: could not record a run of %s", session_run_id, exc_info=True
        )
    return response
