"""The run-token guard: a ``before_request`` hook that refuses a run token Pathly does not know.

A request whose ``X-Pathly-Run-Token`` does not resolve to a live token (never minted, or its
``revoked_at`` is set) gets 401 ``{"error": "unknown run token"}`` on every route. Without it such
a caller fell back to anonymous (``caller_identity``), and anonymous loopback callers may do
everything, so a token leaked from a finished run, or an invented one, was a way around the chief
gate. A request with no header, or with the header empty, stays anonymous; a live token of any
role passes on.

A revoked token whose row has role ``chief`` is left to ``chief_gate``, which answers it 401
``chief session closed``. Registered in ``app.py`` after ``_log_request`` (so the secret check and
the rate limit run first) and before ``chief_gate``.
"""

from __future__ import annotations

import logging

from .chief_budget import forget_run_slot
from .run_identity import RUN_TOKEN_HEADER

logger = logging.getLogger("pathly.http")


def run_token_guard():
    """401 for a token that is not live (a revoked chief token aside); None lets it through."""
    from flask import jsonify, request

    token = (request.headers.get(RUN_TOKEN_HEADER) or "").strip()
    if not token:
        return None

    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import lookup_run_token

    row = lookup_run_token(get_db(), token)
    if row is not None and (
        row.get("revoked_at") is None or row.get("role") == "chief"
    ):
        return None
    # The refusal ends the request before chief_gate drops a run-slot marker an earlier request
    # left on ``flask.g``; drop it here so ``refund_run_slot`` does not give that slot back.
    forget_run_slot()
    logger.info(
        "refused an unknown or revoked run token from %s",
        request.remote_addr or "unknown",
    )
    return jsonify({"error": "unknown run token"}), 401
