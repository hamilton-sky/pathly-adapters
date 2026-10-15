"""HQ prompt endpoint — POST /hq/prompt.

The one call Studio's HQ panel makes before a board-grounded local-model
answer: it returns the exact system prompt + user turn to send (the live
board packet included) and the manifest of what that packet holds — or,
for an action request, the read-only redirect to show instead of calling
the model. With ``enabled_actions`` it returns the OPERATOR turn
(hq_operator) plus the function definitions the model may call; a call is a
proposal, executed only by ``POST /hq/actions/run``. Builds text, writes nothing.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("hq_prompt", __name__)


@bp.route("/hq/prompt", methods=["POST"])
def hq_prompt():
    """Body ``{message, board, project_root?, model?, sections?, enabled_actions?}``.

    ``sections`` is the list of board sections the user ticked (Studio's
    context checkboxes); omitted means the default set, ``[]`` means none.

    200 ``{redirect, system_prompt, prompt, manifest, context_tokens}``:
    ``redirect`` set means show it and skip the model (system_prompt, prompt
    and manifest are then null). Otherwise send ``system_prompt`` + ``prompt``
    to the model with a context of at least ``context_tokens``.
    ``manifest.unavailable`` is true when the packet could not be built (the
    prompt then carries the ``[board context unavailable]`` marker). An
    unknown or empty board is not an error: its empty packet tells the model
    there is nothing on the board yet. 400 when ``message`` or ``board`` is
    missing.

    ``enabled_actions``: the composer's ticked actions (at most 8, else 400).
    The server keeps only those Settings makes available; when any remain the
    response adds ``tools`` (function definitions to offer the model) and
    ``actions`` (their names), and the turn is the operator turn. None left
    (or omitted): the read-only turn, ``tools: []``.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.hq_settings import (
            get_hq_budget_tokens,
            get_hq_default_model,
        )
        from pathly_orchestrator.hq_actions import (
            TooManyActions,
            effective_actions,
            schema_tokens,
        )
        from pathly_orchestrator.hq_models import hq_required_context
        from pathly_orchestrator.hq_operator import prepare_operator_turn
        from pathly_orchestrator.hq_prompt import prepare_hq_turn

        from ._helpers import available_actions, manifest

        body = request.get_json(silent=True) or {}
        message = str(body.get("message") or "").strip()
        board = str(body.get("board") or "").strip()
        if not message or not board:
            return jsonify({"error": "'message' and 'board' are required"}), 400
        project_root = str(body.get("project_root") or "").strip() or None
        raw_sections = body.get("sections")
        sections = (
            [str(s) for s in raw_sections] if isinstance(raw_sections, list) else None
        )

        requested = body.get("enabled_actions")
        if requested is not None and not isinstance(requested, list):
            return jsonify({"error": "'enabled_actions' must be a list"}), 400

        conn = get_db()
        try:
            actions = effective_actions(requested, available_actions(conn))
        except TooManyActions as exc:
            return jsonify({"error": str(exc)}), 400
        budget = get_hq_budget_tokens(conn)
        model_id = str(body.get("model") or "").strip() or get_hq_default_model(conn)

        if actions:
            turn = prepare_operator_turn(
                message, board, project_root, budget, sections, actions
            )
        else:
            turn = prepare_hq_turn(message, board, project_root, budget, sections)
        if turn.redirect is not None:
            return (
                jsonify(
                    {
                        "redirect": turn.redirect,
                        "system_prompt": None,
                        "prompt": None,
                        "manifest": None,
                        "context_tokens": 0,
                        "tools": [],
                        "actions": [],
                    }
                ),
                200,
            )
        return (
            jsonify(
                {
                    "redirect": None,
                    "system_prompt": turn.system_prompt,
                    "prompt": turn.prompt,
                    "manifest": manifest(turn.packet, model_id, budget, board, actions),
                    # Offered functions ride in the context too.
                    "context_tokens": hq_required_context(budget)
                    + sum(schema_tokens(a) for a in actions),
                    "tools": turn.tools,
                    "actions": actions,
                }
            ),
            200,
        )
    except Exception as exc:
        logging.exception("hq prompt error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
