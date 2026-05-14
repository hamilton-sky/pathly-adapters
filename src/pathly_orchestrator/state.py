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


def load_flow(yaml_path: str) -> dict:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    missing = _REQUIRED_FLOW_KEYS - set(flow.keys())
    if missing:
        for key in sorted(missing):
            print(f"Missing required field: {key}")
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
