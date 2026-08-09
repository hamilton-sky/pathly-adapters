"""Spawn-policy resolution at the spawn sites (spawn-policy P1b).

Turns the DB-backed per-agent model config (``db/queries/app_settings``) into the effective model
for one spawn. This is where "pick the model per agent" takes EFFECT.

Fail-safe by construction: returns the caller's ``model`` unchanged unless a VALID policy exists
for this agent's role **and** this run's ``adapter`` (company) — so an unconfigured system behaves
exactly as before, and a mis-configured / cross-provider entry is ignored rather than breaking the
spawn. Never raises into the spawn path.

Company-override (choosing a *different* adapter than the run picked) is intentionally OUT of scope
here — the run's adapter is respected. That precedence (Settings company vs the flow/per-run
adapter) is a separate, later concern; this layer only sets the MODEL within the chosen company.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("pathly.supervisor")


def effective_model(agent: str, adapter: str, model: str) -> str:
    """Resolve the model for a spawn.

    An explicit ``model`` always wins. Otherwise apply the configured model for ``agent`` IF it is
    for this run's ``adapter`` and valid for it; else return ``model`` unchanged. Never raises.
    """
    if model or not agent:
        return model
    try:
        from ..adapters import validate_adapter_model
        from ..db.connection import get_db
        from ..db.queries.app_settings import resolve_agent_model

        resolved = resolve_agent_model(get_db(), agent)
        if (
            resolved
            and resolved["model"]
            and resolved["adapter"] == adapter
            and validate_adapter_model(adapter, resolved["model"]) is None
        ):
            return resolved["model"]
    except Exception:
        logger.debug("spawn-policy effective_model skipped", exc_info=True)
    return model
