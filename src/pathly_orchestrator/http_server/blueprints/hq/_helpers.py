"""Shared HQ route helpers: the context manifest, one shape for both routes.

``GET /hq/context`` and ``POST /hq/prompt`` both report what context a model
turn carries; Studio renders it under the answer. Pure functions, no DB.
"""

from __future__ import annotations


def available_actions(conn) -> list[str]:
    """The operator actions Settings lets HQ use (local-operator): the stored
    ``hq.actions.available`` checked against the catalog, else the default."""
    from pathly_orchestrator.db.queries.hq_settings import get_hq_available_actions
    from pathly_orchestrator.hq_actions import default_available, normalize_names

    stored = get_hq_available_actions(conn)
    return default_available() if stored is None else normalize_names(stored)


def manifest(
    packet, model_id: str, budget: int, board: str, actions: list[str] | None = None
) -> dict:
    """``{board, tokens_est, budget, sections, model, eligible_model, unavailable, actions}``.

    ``board`` is the scope the packet was built for — Studio shows it on the
    context line, the one place HQ says which board an answer is about.

    *packet* is a ``hq_context.ContextPacket``, or None when the board context
    could not be assembled (``unavailable: true``, no sections). ``actions``:
    the operator actions this turn offered the model (none: read-only).
    """
    from pathly_orchestrator.hq_models import hq_eligible

    return {
        "board": board,
        "tokens_est": packet.tokens_est if packet is not None else 0,
        "budget": budget,
        "sections": [
            {
                "name": s.name,
                "included": s.included,
                "cut_reason": s.cut_reason,
                "tokens": s.tokens,
            }
            for s in (packet.sections if packet is not None else [])
        ],
        "model": model_id,
        "eligible_model": hq_eligible(model_id, budget),
        "unavailable": packet is None,
        "actions": list(actions or []),
    }
