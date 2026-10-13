"""Which board tiers a run may see — and how to address each one.

One resolution serves both directions of the board channel: the context PUSHED into a prompt
(``comms_context.board_context_for``) and the tiers an agent may PULL itself via
``/comms/search`` (the ``board-search`` fragment's ``<search_tiers>``). They have to come from
the same place — an agent told it may search a tier its own context channel is not reading
would be reaching AROUND the board-scope governance instead of extending inside it.
"""

from __future__ import annotations

# What a run sees when nothing is configured (or the setting cannot be read at all). Mirrors
# db/queries/app_settings._BOARD_SCOPE_DEFAULT and retrieve_board_context's own default.
ALL_TIERS: dict[str, bool] = {"feature": True, "project": True, "global": True}


def read_tiers(project_root: str, scope: str, role: str = "") -> dict[str, bool] | None:
    """The stored tier selection for a run: per-ROLE row, else per-feature row, else default.

    Returns None when the setting cannot be read at all (no DB) — callers already treat None
    as "all tiers", the same answer an absent setting gets, so a DB hiccup never silently
    narrows what an agent is shown.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_board_scope

        return get_board_scope(get_db(), project_root or "", scope, role=role or None)
    except Exception:
        return None


def resolve_board_scope_setting(
    board: str, scope: str, project_root: str, role: str = ""
) -> dict[str, bool] | None:
    """Tier selection for a run on *board*/*scope*.

    Only a feature board has a per-feature (now also per-role) row to read; a project- or
    global-tier run has none and takes the fixed mix it has always taken — its own tier plus
    global, never the feature tier, whose scope key would be a project root nobody posts to.
    """
    if board == "feature":
        return read_tiers(project_root, scope, role)
    return {"feature": False, "project": board == "project", "global": True}


def search_tiers_value(
    tiers: dict[str, bool] | None, feature: str, project_root: str
) -> str:
    """Render ``<search_tiers>`` — the tiers this run may query, WITH the scope addressing each.

    The scope value is a different shape per tier (feature board -> the feature/board slug,
    project board -> the normalized project root, global board -> the literal "global"), and a
    mismatched board/scope pair is not an error: ``/comms/search`` returns [], which reads to
    the agent exactly like "the board knows nothing". So the pairs are rendered here from the
    same values ``retrieve_board_context`` searches with, rather than left to the agent to
    reconstruct.
    """
    tiers = ALL_TIERS if tiers is None else tiers
    # Same normalization the board itself keys by (comms/project.py::_project_scope,
    # fsm_compose_paths.resolve_board_scope) — a raw project_root can still carry Windows
    # backslashes, which address no board at all.
    norm_root = (project_root or "").replace("\\", "/").rstrip("/")
    pairs: list[str] = []
    if tiers.get("feature", True) and feature:
        pairs.append(f'board "feature" + scope "{feature}"')
    if tiers.get("project", True) and norm_root:
        pairs.append(f'board "project" + scope "{norm_root}"')
    if tiers.get("global", True):
        pairs.append('board "global" + scope "global"')
    if not pairs:
        # Every tier off is a deliberate "this agent reads no board". Say so rather than
        # falling back to the own board — that would be search reaching around the setting.
        return "(none — board reads are disabled for this run; do not search)"
    return "; ".join(pairs)
