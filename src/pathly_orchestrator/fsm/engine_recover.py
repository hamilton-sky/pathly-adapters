"""FSM state recovery — reads storage_path to reconstruct current state + limits."""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_LIMITS = {
    "needs_context_per_stage": 3,
    "feedback_rounds_per_stage": 2,
}


def recover_state(
    storage_path: Path, flow: dict, state_doc: dict | None = None
) -> dict:
    """Read STATE.json / DB and return current state info dict.

    Returns: {current_state, conv, open_feedback_files, limits, corrupted_state}
    state_doc: pre-loaded DB dict — if provided, STATE.json is skipped.
    """
    corrupted_state = False
    if state_doc is not None:
        current_state = state_doc.get("current", flow["states"][0])
        conv = state_doc.get("current_conversation", 0)
    else:
        # pathly:allow-mirror-read: DB-first recovery fallback — disk snapshot only when no DB state_doc
        state_file = storage_path / "STATE.json"
        if state_file.exists():
            try:
                loaded = json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                loaded = {}
                corrupted_state = True
            current_state = loaded.get("current", flow["states"][0])
            conv = loaded.get("current_conversation", 0)
        else:
            current_state = flow["states"][0]
            conv = 0

    # A persisted `current` this flow does not declare is stale/foreign — e.g. a feature seeded
    # under an older flow shape (STORMING was dropped from team.flow.yaml), or one whose last run
    # used a different flow. Downstream lookups (agent_map[current], transition rules) would
    # KeyError, so recover to the flow's seed state (states[0]) here. This mirrors
    # supervisor.goal_executor._reset_fsm_state_for_flow, but at the read layer so EVERY caller
    # (direct /runner/start AND goal runs) is covered — not just goal runs. DONE is a declared
    # state, so a finished feature is never reset by this.
    states = flow.get("states") or []
    if states and current_state not in states:
        current_state = states[0]

    feedback_dir = storage_path / "feedback"
    if feedback_dir.exists():
        open_feedback_files = [
            f.name for f in sorted(feedback_dir.iterdir()) if f.suffix == ".md"
        ]
    else:
        open_feedback_files = []

    limits = dict(_DEFAULT_LIMITS)
    top_limits = flow.get("limits")
    if top_limits:
        limits.update(top_limits)

    states_config = flow.get("states_config", {})
    if isinstance(states_config, dict):
        per_state = states_config.get(current_state, {})
        if isinstance(per_state, dict):
            per_state_limits = per_state.get("limits", {})
            if per_state_limits:
                limits.update(per_state_limits)

    return {
        "current_state": current_state,
        "conv": conv,
        "open_feedback_files": open_feedback_files,
        "limits": limits,
        "corrupted_state": corrupted_state,
    }
