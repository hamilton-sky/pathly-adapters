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
