"""Tests for get_transition_actions() and validate_flow_cli() in state.py."""

from __future__ import annotations
import sys
from pathlib import Path

import pytest
import yaml

from pathly_orchestrator.state import get_transition_actions, validate_flow_cli

FLOWS_DIR = Path(__file__).parent.parent / "src" / "pathly_data" / "core" / "flows"


# ── get_transition_actions() ──────────────────────────────────────────────────

def test_get_transition_actions_returns_full_dict_when_present():
    flow = {
        "transition_actions": {
            "BUILDING->REVIEWING": [{"type": "git_commit"}],
            "RETRO->DONE": [{"type": "archive_artifacts"}],
        }
    }
    result = get_transition_actions(flow)
    assert result == flow["transition_actions"]


def test_get_transition_actions_returns_empty_dict_when_key_absent():
    flow = {"states": ["A", "B"]}
    assert get_transition_actions(flow) == {}


def test_get_transition_actions_returns_empty_dict_when_key_is_none():
    assert get_transition_actions({"transition_actions": None}) == {}


def test_get_transition_actions_returns_empty_dict_when_key_is_falsy():
    assert get_transition_actions({"transition_actions": {}}) == {}


# ── validate_flow_cli() helpers ───────────────────────────────────────────────

def _run_cli(path: str, monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", ["pathly-validate-flow", path])
    with pytest.raises(SystemExit) as exc_info:
        validate_flow_cli()
    return exc_info.value.code


# ── validate_flow_cli(): real flow files ──────────────────────────────────────

def test_validate_team_flow_passes(monkeypatch, capsys):
    code = _run_cli(str(FLOWS_DIR / "team.flow.yaml"), monkeypatch)
    assert code == 0
    out = capsys.readouterr().out
    assert "OK:" in out


def test_validate_debug_flow_passes(monkeypatch, capsys):
    code = _run_cli(str(FLOWS_DIR / "debug.flow.yaml"), monkeypatch)
    assert code == 0
    out = capsys.readouterr().out
    assert "OK:" in out


# ── validate_flow_cli(): warning when transition_actions absent ───────────────

def test_validate_warns_but_exits_0_when_transition_actions_absent(monkeypatch, tmp_path, capsys):
    flow = {
        "storage_path": "plans/{topic}/",
        "states": ["A", "B"],
        "transitions": {"A": ["B"], "B": []},
        "agent_map": {"A": "builder"},
        "feedback_routing": {"IMPL_QUESTIONS": "planner"},
    }
    flow_file = tmp_path / "no_actions.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 0
    out = capsys.readouterr().out
    assert "Warning" in out
    assert "transition_actions" in out


# ── validate_flow_cli(): unknown action type exits 1 ─────────────────────────

def test_validate_exits_1_on_unknown_action_type(monkeypatch, tmp_path, capsys):
    flow = {
        "storage_path": "plans/{topic}/",
        "states": ["A", "B"],
        "transitions": {"A": ["B"], "B": []},
        "agent_map": {"A": "builder"},
        "feedback_routing": {"IMPL_QUESTIONS": "planner"},
        "transition_actions": {
            "A->B": [{"type": "invalid_action"}],
        },
    }
    flow_file = tmp_path / "bad_action.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 1
    out = capsys.readouterr().out
    assert "Unknown action type" in out


# ── validate_flow_cli(): invalid FROM->TO key exits 1 ────────────────────────

def test_validate_exits_1_on_invalid_transition_key(monkeypatch, tmp_path, capsys):
    flow = {
        "storage_path": "plans/{topic}/",
        "states": ["A", "B"],
        "transitions": {"A": ["B"], "B": []},
        "agent_map": {"A": "builder"},
        "feedback_routing": {"IMPL_QUESTIONS": "planner"},
        "transition_actions": {
            "X->Y": [{"type": "git_commit"}],
        },
    }
    flow_file = tmp_path / "bad_transition.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 1
    out = capsys.readouterr().out
    assert "does not exist in transitions" in out


# ── validate_flow_cli(): adapter_map validation ───────────────────────────────

def _minimal_flow(**extra) -> dict:
    base = {
        "storage_path": "plans/{topic}/",
        "states": ["BUILDING", "REVIEWING"],
        "transitions": {"BUILDING": ["REVIEWING"], "REVIEWING": []},
        "agent_map": {"BUILDING": "builder", "REVIEWING": "reviewer"},
        "feedback_routing": {},
        "transition_actions": {},
    }
    base.update(extra)
    return base


def test_validate_adapter_map_well_formed_passes(monkeypatch, tmp_path, capsys):
    flow = _minimal_flow(adapter_map={"default": "claude", "BUILDING": "codex"})
    flow_file = tmp_path / "good_adapter_map.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 0
    out = capsys.readouterr().out
    assert "OK:" in out


def test_validate_adapter_map_missing_default_fails(monkeypatch, tmp_path, capsys):
    flow = _minimal_flow(adapter_map={"BUILDING": "codex"})
    flow_file = tmp_path / "no_default.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 1
    out = capsys.readouterr().out
    assert "default" in out


def test_validate_adapter_map_unknown_adapter_fails(monkeypatch, tmp_path, capsys):
    flow = _minimal_flow(adapter_map={"default": "claude", "BUILDING": "cursor"})
    flow_file = tmp_path / "bad_adapter.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 1
    out = capsys.readouterr().out
    assert "cursor" in out


def test_validate_adapter_map_unknown_default_value_fails(monkeypatch, tmp_path, capsys):
    """The 'default' key's own value must also be in _KNOWN_ADAPTERS."""
    flow = _minimal_flow(adapter_map={"default": "cursor"})
    flow_file = tmp_path / "bad_default_value.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 1
    out = capsys.readouterr().out
    assert "cursor" in out


def test_validate_adapter_map_unknown_state_key_fails(monkeypatch, tmp_path, capsys):
    flow = _minimal_flow(adapter_map={"default": "claude", "NONEXISTENT": "codex"})
    flow_file = tmp_path / "bad_state_key.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 1
    out = capsys.readouterr().out
    assert "NONEXISTENT" in out


def test_validate_flow_without_adapter_map_still_passes(monkeypatch, tmp_path):
    flow = _minimal_flow()
    flow_file = tmp_path / "no_adapter_map.flow.yaml"
    flow_file.write_text(yaml.dump(flow), encoding="utf-8")

    code = _run_cli(str(flow_file), monkeypatch)
    assert code == 0


def test_validate_team_flow_with_adapter_map_still_passes(monkeypatch):
    """team.flow.yaml has no adapter_map — validator must still pass cleanly."""
    code = _run_cli(str(FLOWS_DIR / "team.flow.yaml"), monkeypatch)
    assert code == 0
