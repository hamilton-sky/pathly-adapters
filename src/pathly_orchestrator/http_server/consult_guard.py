"""The consult guard: a consult run cannot post its own answer (chief-autopilot-round-two 17).

A ``type: answer`` post frees the tasks parked on its question the moment ``post_message`` writes
it (``release_on_answer``), before the router measures what the consult changed. So a consult
delivers its answer in its completion summary and Pathly posts it. This ``before_request`` answers
403 ``{"error": "a consult answers in its completion summary; Pathly posts the answer"}`` to
``POST /comms/answer``, and to ``POST /comms/post`` whose JSON body has ``"type": "answer"``, when
the caller holds a live run token whose run id starts ``consult-``.

Every other post of a consult (status, discovery, question) passes, an answer from any other
caller is unchanged, and a body that is not JSON passes to the route, which refuses it. A revoked
token never gets here: ``run_token_guard``, registered before this hook in ``app.py``, answers it
401.
"""

from __future__ import annotations

ANSWER_PATH = "/comms/answer"
POST_PATH = "/comms/post"
REFUSAL = "a consult answers in its completion summary; Pathly posts the answer"


def _posts_an_answer(request) -> bool:
    if request.path == ANSWER_PATH:
        return True
    if request.path != POST_PATH:
        return False
    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        read_json_body,
    )

    data = read_json_body()
    return isinstance(data, dict) and data.get("type") == "answer"


def consult_guard():
    """403 for a consult run's own answer; None lets every other request through."""
    from flask import jsonify, request

    from pathly_orchestrator.http_server.run_identity import RUN_TOKEN_HEADER

    if request.method != "POST":
        return None
    token = (request.headers.get(RUN_TOKEN_HEADER) or "").strip()
    if not token or not _posts_an_answer(request):
        return None

    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.consult_routes import CONSULT_RUN_PREFIX
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    row = resolve_run_token(get_db(), token)
    run_id = row.get("run_id") if row is not None else None
    if not (isinstance(run_id, str) and run_id.startswith(CONSULT_RUN_PREFIX)):
        return None
    return jsonify({"error": REFUSAL}), 403
