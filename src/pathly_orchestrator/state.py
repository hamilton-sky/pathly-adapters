"""
FSM state for STATE.json.

The LLM writes STATE.json directly — it does not import this file.
This file provides flow-agnostic helpers for reading *.flow.yaml files
and a CLI for validating them.

STATE.json lives at <storage_path>/STATE.json and is rewritten after every event.

── Schema ────────────────────────────────────────────────────────────────────

{
  "current": "<FSM state name>",    // must be in flow["states"]
  "feature": "<feature-name>",
  "rigor": "lite|standard|strict",
  "current_conversation": 0,        // 0 = not in build stage yet; 1+ = active conv
  "retry_count_by_key": {           // key = "conv-N:FILENAME.md"
    "conv-2:REVIEW_FAILURES.md": 1
  },
  "iteration_by_stage": {           // key = FSM stage name, value = attempt count
    "BUILDING": 2
  },
  "updated_at": "2026-05-11T10:30:00Z"
}

── FSM States ────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import sys
from pathlib import Path

import yaml

_REQUIRED_FLOW_KEYS = {"storage_path", "states", "transitions", "agent_map", "feedback_routing"}
_KNOWN_OPTIONAL_FLOW_KEYS = {"transition_rules", "version", "flow", "transition_actions"}
_ACTION_VOCAB = {"git_commit", "update_progress", "archive_artifacts"}


def load_flow(yaml_path: str) -> dict:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_transition_actions(flow: dict) -> dict:
    return flow.get("transition_actions") or {}


def valid_states(flow: dict) -> frozenset[str]:
    return frozenset(flow.get("states", []))


def flow_transitions(flow: dict) -> dict[str, frozenset[str]]:
    return {k: frozenset(v) for k, v in flow.get("transitions", {}).items()}


def validate_flow_cli() -> None:
    if len(sys.argv) < 2:
        print("Usage: pathly-validate-flow <path>")
        sys.exit(1)
    path = sys.argv[1]
    try:
        flow = load_flow(path)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        sys.exit(1)

    errors: list[str] = []

    missing = _REQUIRED_FLOW_KEYS - set(flow.keys())
    if missing:
        for key in sorted(missing):
            errors.append(f"Missing required field: {key}")

    if "transition_actions" not in flow:
        print(f"Warning: transition_actions key absent — flow has no declared side effects")
    else:
        ta = flow["transition_actions"] or {}
        all_transitions: set[tuple[str, str]] = set()
        for from_state, targets in (flow.get("transitions") or {}).items():
            for to_state in (targets or []):
                all_transitions.add((from_state, str(to_state)))
        all_states = set(flow.get("states") or [])

        for key, actions in ta.items():
            parts = str(key).split("->", 1)
            if len(parts) != 2:
                errors.append(f"transition_actions key '{key}' must use FROM->TO format")
                continue
            from_state, to_state = parts
            if from_state:
                if (from_state, to_state) not in all_transitions:
                    errors.append(
                        f"transition_actions key '{key}' does not exist in transitions"
                    )
            else:
                if to_state not in all_states:
                    errors.append(
                        f"transition_actions wildcard '->{to_state}' target is not a known state"
                    )

            for action in (actions or []):
                action_type = action.get("type") if isinstance(action, dict) else None
                if action_type not in _ACTION_VOCAB:
                    errors.append(
                        f"Unknown action type '{action_type}' in transition_actions[{key}]"
                    )

    if errors:
        for err in errors:
            print(err)
        sys.exit(1)
    print(f"OK: {path}")
    sys.exit(0)


# ── Example STATE.json ────────────────────────────────────────────────────────
#
# {
#   "current": "REVIEWING",
#   "feature": "security-fixes",
#   "rigor": "lite",
#   "current_conversation": 2,
#   "retry_count_by_key": {
#     "conv-2:REVIEW_FAILURES.md": 1
#   },
#   "iteration_by_stage": {
#     "BUILDING": 2
#   },
#   "updated_at": "2026-05-11T10:45:00Z"
# }
#
# iteration_by_stage is optional. When present, each key is an FSM stage name
# and each value is the number of times that stage has been entered. This
# supplements retry_count_by_key (which tracks per-file retry counts) with a
# coarser per-stage view.
