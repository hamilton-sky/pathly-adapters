"""Where a stage writes, and which board it posts to.

``resolve_board_scope`` in particular is the guard against the project-scope trap: a project
board's DB scope is the project ROOT, and a stage that normalizes it differently posts onto a
board nobody is reading.
"""

from __future__ import annotations

from pathlib import Path

from .fsm_compose_tables import _SKILL_AGENT_ROLE


def resolve_stage_out_path(
    flow_config: dict, state_name: str, storage_path: Path
) -> str | None:
    """The on-disk ``<out_path>`` a stage declares (its primary artifact), resolved from the
    composition manifest via the SAME (agent_role, skill) -> ``manifest_role_file`` path
    ``build_prompt`` uses to substitute ``<out_path>`` into the prompt.

    Returns None when the state maps to no composed skill (bare-role stage) or the role has no
    manifest entry. Used by artifact reconciliation to attach a stage's declared output to the
    board directly from the FSM's own record (state-one-authority: replaces the retired
    ARTIFACTS.jsonl ledger scan — no disk mirror)."""
    try:
        agent = (flow_config.get("agent_map") or {}).get(state_name)
        if not agent or "/" not in agent:
            return None
        _role = _SKILL_AGENT_ROLE.get(agent)
        agent_role = _role if _role is not None else agent.split("/")[-1]
        from pathly_orchestrator.compose import manifest_role_file

        entry = manifest_role_file(agent_role, agent)
        if entry is None:
            return None
        feature_path = Path(storage_path).as_posix().rstrip("/")
        return f"{feature_path}/{entry[0]}"
    except Exception:
        return None


def resolve_board_scope(feature: str, project_root: str, goal_id: str = "") -> str:
    """Board scope a run posts to / retrieves context from — its PARENT identity.

    A plain feature pipeline: this IS the feature (the storage dir name). A
    goal-decompose run (the consultation FSM): the on-disk topic is the goal slug
    for run isolation, but board writes must target the parent feature/project
    board the goal lives on — else the PO/architect/… artifacts orphan onto a
    throwaway slug-scoped board instead of the board the consultation was spawned
    from (the bug fix). Extracted from build_prompt so the supervisor can stamp
    the SAME value into telemetry events at spawn (run-identity) — one derivation,
    so the prompt's ``<feature>`` and the stamped ``board_scope`` never drift.
    """
    board_scope = feature
    if feature == "project":
        # A PROJECT-scoped run (storage pathly/project/ → basename 'project') posts to / reads
        # the project board, whose scope is the NORMALIZED project_root — NOT the literal
        # 'project' dir basename, which the board + comms_context never key by. Mirrors
        # comms/project.py::_project_scope. Without this the stage's board writes (the
        # project-decompose feature cards, PO/architect notes) orphan at scope='project',
        # invisible on the per-root project board — AND the ≥2-features gate, which counts at
        # scope=project_root, sees 0 and fails the run after it actually seeded features.
        board_scope = (project_root or "").replace("\\", "/").rstrip("/") or feature
    if goal_id:
        try:
            from pathly_orchestrator.db.connection import get_db as _gd
            from pathly_orchestrator.db.queries.comms_messages import (
                get_goal_board_scope as _ggbs,
            )

            _bs = _ggbs(_gd(project_root or None), goal_id)
            if _bs is not None:
                # _bs = (board_tier, scope). We take only the scope: the board-post
                # fragments (comms-post, board-init) and record-phase hardcode
                # board='feature', so the *feature*-tier goal path is what's fully
                # supported here. A project/global-tier goal decompose is an edge case
                # (project goals normally become features, not DAG-decomposed): its
                # posts would land under scope=<project_root> on the feature board, and
                # its project-board context is still surfaced via retrieve_board_context's
                # own project channel. Threading _bs[0] through to the post sites is a
                # follow-up (needs a `<board>` fragment variable), not done here.
                board_scope = _bs[1]
        except Exception:
            board_scope = feature
    return board_scope
