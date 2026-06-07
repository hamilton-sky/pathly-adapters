"""Tests for on_state_counter transition rule level in evaluate_transition_rules."""
from __future__ import annotations

import json
from pathlib import Path

from pathly_orchestrator.fsm import evaluate_transition_rules
from pathly_orchestrator import eventlog as el


def _storage(tmp_path: Path, convs_done: int = 1, convs_total: int = 3) -> Path:
    storage = tmp_path / "pathly" / "plans" / "test"
    storage.mkdir(parents=True)
    # Write via eventlog so state goes to DB (works in both normal and PATHLY_DB_ONLY mode)
    el.write_state(str(storage), {"current": "REVIEWING", "convs_done": convs_done, "convs_total": convs_total})
    return storage


def _flow(op: str = "lt") -> dict:
    return {
        "transitions": {"REVIEWING": ["BUILDING", "TESTING"]},
        "transition_rules": {
            "REVIEWING": {
                "on_state_counter": {
                    "field": "convs_done",
                    "op": op,
                    "compare_to": "convs_total",
                    "next": "BUILDING",
                },
                "default": "TESTING",
            }
        },
    }


def test_on_state_counter_condition_met(tmp_path):
    """convs_done=1 < convs_total=3 → returns 'BUILDING'."""
    storage = _storage(tmp_path, convs_done=1, convs_total=3)
    result = evaluate_transition_rules(_flow(), "REVIEWING", storage)
    assert result == "BUILDING"


def test_on_state_counter_condition_unmet(tmp_path):
    """convs_done=3 == convs_total=3, op=lt → condition false → falls through to default 'TESTING'."""
    storage = _storage(tmp_path, convs_done=3, convs_total=3)
    result = evaluate_transition_rules(_flow(), "REVIEWING", storage)
    assert result == "TESTING"


def test_on_state_counter_missing_field(tmp_path):
    """STATE.json missing 'convs_done' → falls through without raising → default returned."""
    storage = tmp_path / "pathly" / "plans" / "test"
    storage.mkdir(parents=True)
    # convs_done intentionally absent — condition must fall through gracefully
    el.write_state(str(storage), {"current": "REVIEWING", "convs_total": 3})
    result = evaluate_transition_rules(_flow(), "REVIEWING", storage)
    assert result == "TESTING"


def test_on_state_counter_malformed_op(tmp_path):
    """Unknown op 'xlt' → falls through without raising → default returned."""
    storage = _storage(tmp_path, convs_done=1, convs_total=3)
    result = evaluate_transition_rules(_flow(op="xlt"), "REVIEWING", storage)
    assert result == "TESTING"
