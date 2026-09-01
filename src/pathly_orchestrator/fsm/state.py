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
import json
import sys
from importlib.resources import files
from pathlib import Path

import yaml

# One extra .parent vs. old state.py because this file is in fsm/ sub-package.
_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "pathly_data"
    / "schemas"
    / "state.schema.json"
)
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

# GENERIC FALLBACK, not the state machine of any live flow. None of the 9 shipped
# core/flows/*.flow.yaml carry this exact vocabulary (IDLE, DISCOVERING,
# REVIEW_BLOCKED, ...) or these exact transitions — every real caller
# (fsm_ops.py, fsm_ops_complete.py) always passes its own flow_config, which
# eventlog.write_state/append_event validate against instead (via valid_states()/
# flow_transitions()). STATES/VALID_STATES/TRANSITIONS exist ONLY as the
# still-enforced legality check for a caller that omits flow — see
# eventlog.write_state's `flow is None` branch and
# tests/fsm_flows/test_orchestrator.py's write_state/append_event legality tests.
STATES: dict[str, list[str]] = _SCHEMA["transitions"]
VALID_STATES: frozenset[str] = frozenset(STATES.keys())
TRANSITIONS: dict[str, list[str]] = STATES

_KNOWN_ADAPTERS: frozenset[str] = frozenset(
    {"claude", "codex", "copilot", "antigravity"}
)

_REQUIRED_FLOW_KEYS = {
    "storage_path",
    "states",
    "transitions",
    "agent_map",
    "feedback_routing",
}
_KNOWN_OPTIONAL_FLOW_KEYS = {
    "transition_rules",
    "version",
    "flow",
    "transition_actions",
    "adapter_map",
    "composition",
    "feedback_priority",
    "parallel_states",
}
# Isolation strategies a `parallel_states` entry may name, mapping 1:1 onto
# supervisor/isolation.py's implementations. `worktree` validates but warns —
# WorktreeIsolation is still a documented stub that raises NotImplementedError.
_ISOLATION_VOCAB = {"lane", "serial", "worktree"}
_ACTION_VOCAB = {
    "git_commit",
    "commit",
    "archive_artifacts",
    "archive-artifacts",
}


def load_flow(yaml_path: str) -> dict:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_transition_actions(flow: dict) -> dict:
    return flow.get("transition_actions") or {}


def valid_states(flow: dict) -> frozenset[str]:
    return frozenset(flow.get("states", []))


def flow_transitions(flow: dict) -> dict[str, frozenset[str]]:
    return {k: frozenset(v) for k, v in flow.get("transitions", {}).items()}


def _validate_parallel_states(
    flow: dict, errors: list[str], warnings: list[str]
) -> None:
    """Validate the optional ``parallel_states`` block (fsm-fan-out Phase B).

    A state opts into fan-out — one FSM state executing its ready tasks and joining —
    by naming itself here. Absent means today's exact behavior (one spawn per stage),
    so every existing flow is unaffected::

        parallel_states:
          BUILDING:
            max_workers: 4        # optional; default = the isolation's own answer
            isolation: lane       # optional; lane | serial | worktree

    Schema only. Nothing reads this yet — Phase C is what branches on it.
    """
    if "parallel_states" not in flow:
        return
    parallel_states = flow["parallel_states"]
    if not isinstance(parallel_states, dict):
        errors.append(
            "parallel_states: value must be a dict mapping state names to their config"
        )
        return

    declared_states = set(flow.get("states") or [])
    for state_key, config in parallel_states.items():
        if state_key not in declared_states:
            errors.append(
                f"parallel_states key '{state_key}' is not a declared state in 'states'"
            )
        # `BUILDING:` with no body parses as None — a legal "all defaults" entry.
        if config is None:
            continue
        if not isinstance(config, dict):
            errors.append(
                f"parallel_states['{state_key}']: config must be a dict (or empty for defaults)"
            )
            continue

        if "max_workers" in config:
            max_workers = config["max_workers"]
            # bool is a subclass of int — `max_workers: true` is a mistake, not a cap of 1.
            if (
                isinstance(max_workers, bool)
                or not isinstance(max_workers, int)
                or max_workers < 1
            ):
                errors.append(
                    f"parallel_states['{state_key}'].max_workers must be a positive"
                    f" integer (got {max_workers!r})"
                )

        if "isolation" in config:
            isolation = config["isolation"]
            if isolation not in _ISOLATION_VOCAB:
                errors.append(
                    f"parallel_states['{state_key}'].isolation: unknown strategy"
                    f" {isolation!r} (known: {sorted(_ISOLATION_VOCAB)})"
                )
            elif isolation == "worktree":
                warnings.append(
                    f"Warning: parallel_states['{state_key}'].isolation is 'worktree' —"
                    " WorktreeIsolation is still a stub (raises NotImplementedError)."
                )


def validate_flow_dict(flow: dict) -> tuple[list[str], list[str]]:
    """Validate a parsed flow dict. Returns ``(errors, warnings)``.

    Pure — no argv, no I/O, no ``sys.exit`` — so callers and tests can reuse it.
    ``validate_flow_cli`` is the thin wrapper that loads the file, prints both
    lists, and exits non-zero when ``errors`` is non-empty.
    """
    errors: list[str] = []
    warnings: list[str] = []

    missing = _REQUIRED_FLOW_KEYS - set(flow.keys())
    if missing:
        for key in sorted(missing):
            errors.append(f"Missing required field: {key}")

    if "transition_actions" not in flow:
        warnings.append(
            "Warning: transition_actions key absent — flow has no declared side effects"
        )
    else:
        ta = flow["transition_actions"] or {}
        all_transitions: set[tuple[str, str]] = set()
        for from_state, targets in (flow.get("transitions") or {}).items():
            for to_state in targets or []:
                all_transitions.add((from_state, str(to_state)))
        all_states = set(flow.get("states") or [])

        for key, actions in ta.items():
            parts = str(key).split("->", 1)
            if len(parts) != 2:
                errors.append(
                    f"transition_actions key '{key}' must use FROM->TO format"
                )
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

            for action in actions or []:
                if isinstance(action, dict):
                    action_type = action.get("skill") or action.get("type")
                else:
                    action_type = None
                if action_type not in _ACTION_VOCAB:
                    errors.append(
                        f"Unknown action type '{action_type}' in transition_actions[{key}]"
                    )

    # adapter_map validation (optional field — omitting it is fully backward compatible)
    if "adapter_map" in flow:
        adapter_map = flow["adapter_map"] or {}
        if "default" not in adapter_map:
            errors.append("adapter_map: 'default' key is required")
        declared_states = set(flow.get("states") or [])
        for key, value in adapter_map.items():
            if value not in _KNOWN_ADAPTERS:
                errors.append(
                    f"adapter_map['{key}']: unknown adapter '{value}'"
                    f" (known: {sorted(_KNOWN_ADAPTERS)})"
                )
            if key != "default" and key not in declared_states:
                errors.append(
                    f"adapter_map key '{key}' is not a declared state in 'states'"
                )

    # composition: validation (optional field — omitting it is fully backward compatible)
    if "composition" in flow:
        composition = flow["composition"]
        if not isinstance(composition, dict):
            errors.append(
                "composition: value must be a dict mapping state names to block names"
            )
        else:
            declared_states = set(flow.get("states") or [])
            from pathly_orchestrator.compose import resolve_block

            for state_key, block_name in composition.items():
                if state_key not in declared_states:
                    errors.append(
                        f"composition key '{state_key}' is not a declared state in 'states'"
                    )
                if not isinstance(block_name, str) or not block_name:
                    errors.append(
                        f"composition['{state_key}']: block name must be a non-empty string"
                    )
                    continue
                try:
                    resolve_block(block_name, None)
                except KeyError:
                    errors.append(
                        f"composition['{state_key}']: unknown block name '{block_name}'"
                    )

    _validate_parallel_states(flow, errors, warnings)

    # Addition 1 — Agent-contract validation (warning only; contracts may not ship with adapters)
    for agent in (flow.get("agent_map") or {}).values():
        agent_path = files("pathly_data").joinpath(f"core/agents/{agent}.md")
        try:
            agent_path.read_bytes()
        except (FileNotFoundError, TypeError, Exception):
            warnings.append(f"Warning: Missing agent contract: core/agents/{agent}.md")

    # Addition 2 — Decide-block option count
    for state, rule in (flow.get("transition_rules") or {}).items():
        if isinstance(rule, dict) and "decide" in rule:
            decide = rule["decide"]
            if isinstance(decide, dict) and len(decide.get("options", {})) < 2:
                warnings.append(
                    f"Warning: decide block in state '{state}' has fewer than 2 options."
                )

    return errors, warnings


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

    errors, warnings = validate_flow_dict(flow)
    for warning in warnings:
        print(warning)
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
