"""Route a posted role question to a consult (chief-autopilot-round-two 04).

``trigger_consult`` is an ``after_request`` hook. For ``POST /comms/post`` answered 200 with
``ok`` and a ``message_id``, when the request body's ``type`` is ``question``, it calls
``supervisor.consult_router.on_question`` with the asking run's token's ``project_root``,
``board`` and ``scope`` (``caller_identity``, the ``run_tokens`` row; never the body's, so a run
cannot point a consult at another project or board), ``broadcast_fn=sse._broadcast_spawn`` and
``host_present=bool(sse._spawn_clients)`` (the queues a spawn host reads, ``/events/spawn``). It never changes the response and never raises: a failure
is logged, so routing can never turn a stored post into a 500.
"""

from __future__ import annotations

import logging

from flask import request

POST_PATH = "/comms/post"


def _posted_id(response) -> str | None:
    """The message id a 200 ``{ok: true, message_id}`` answer stored, else None."""
    if response.status_code != 200 or not response.is_json:
        return None
    body = response.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("ok"):
        return None
    message_id = body.get("message_id")
    return message_id if isinstance(message_id, str) and message_id else None


def trigger_consult(response):
    """``after_request``: route the role question a ``POST /comms/post`` just stored."""
    if request.method != "POST" or request.path != POST_PATH:
        return response
    try:
        message_id = _posted_id(response)
        if message_id is None:
            return response
        from pathly_orchestrator.http_server import sse
        from pathly_orchestrator.http_server.blueprints.comms._helpers import (
            read_json_body,
        )

        data = read_json_body() or {}
        if data.get("type") != "question":
            return response
        from pathly_orchestrator.http_server.run_identity import caller_identity
        from pathly_orchestrator.supervisor.consult_router import on_question

        asker = caller_identity(request)
        on_question(
            message_id,
            project_root=asker.project_root,
            board=asker.board,
            scope=asker.scope,
            broadcast_fn=sse._broadcast_spawn,
            host_present=bool(sse._spawn_clients),
        )
    except Exception:
        logging.getLogger("pathly.http").warning(
            "consult: could not route a posted question", exc_info=True
        )
    return response
