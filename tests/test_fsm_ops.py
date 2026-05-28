"""Integration tests for fsm_ops.py (next_action, complete_stage)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import pathly_orchestrator.fsm_ops as fsm_ops
from pathly_orchestrator.fsm_ops import complete_stage, next_action


DECIDE_FLOW = {
    "version": 1,
    "flow": "test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["DECIDING", "PATH_A", "PATH_B"],
    "transitions": {
        "DECIDING": ["PATH_A", "PATH_B"],
        "PATH_A": [],
        "PATH_B": [],
    },
    "agent_map": {
        "DECIDING": "team/decide-agent",
        "PATH_A": "team/path-a-agent",
        "PATH_B": "team/path-b-agent",
    },
    "feedback_routing": {},
    "transition_rules": {
        "DECIDING": {
            "decide": {
                "context_file": "CONTEXT.md",
                "question": "Which path?",
                "options": {"a": "PATH_A", "b": "PATH_B"},
                "default": "a",
            }
        }
    },
    "transition_actions": {},
}

ROUTING_FLOW = {
    "version": 1,
    "flow": "test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["BUILDING"],
    "transitions": {"BUILDING": []},
    "agent_map": {"BUILDING": "builder"},
    "feedback_routing": {},
    "transition_rules": {},
    "transition_actions": {},
}


def _storage_path(tmp_path: Path, topic: str = "test-topic") -> Path:
    p = tmp_path / "pathly" / "plans" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Basic routing tests ───────────────────────────────────────────────────────

def test_next_action_initial_state(tmp_path):
    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result["current_state"] == "STORMING"
    assert result["agent"] == "team/discover"


def test_next_action_includes_codex_worker_hint(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    assert result["agent"] == "builder"
    hint = result["codex_subagent"]
    assert hint["pathly_agent"] == "builder"
    assert hint["codex_role"] == "worker"
    assert "PATHLY AGENT: builder" in hint["instructions"]
    assert "instructions for BUILDING" in hint["instructions"]


def test_next_action_includes_menu_payload(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    menu = result["menu"]
    assert menu["state"] == "BUILDING"
    assert menu["feature"] == "test-topic"
    assert menu["agent"] == "builder"
    assert isinstance(menu["items"], list)
    assert menu["items"] == []
    assert "empty_message" in menu


def test_codex_hint_maps_research_agents_to_explorer():
    hint = fsm_ops._codex_subagent_hint("scout", "find the relevant files")

    assert hint["pathly_agent"] == "scout"
    assert hint["codex_role"] == "explorer"
    assert "find the relevant files" in hint["instructions"]


def test_complete_stage_after_planning(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "PLANNING"}), encoding="utf-8")
    (storage / "IMPLEMENTATION_PLAN.md").write_text("plan content", encoding="utf-8")

    result = complete_stage({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result.get("next_state") in ("BUILDING", "DESIGNING")


def test_complete_stage_blocked_by_review_failures(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("these tests failed", encoding="utf-8")

    result = complete_stage({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result.get("blocked") is True
    assert result.get("target_agent") == "builder"
    assert "# builder" in result["instructions"]
    assert result["codex_subagent"]["pathly_agent"] == "builder"
    assert result["codex_subagent"]["codex_role"] == "worker"


# ── Two-call decide protocol ──────────────────────────────────────────────────

def _make_decide_agent_files(tmp_path: Path) -> None:
    agents_dir = tmp_path / "fake_agents"
    agents_dir.mkdir(parents=True, exist_ok=True)


def _patch_load_flow(monkeypatch, flow: dict) -> None:
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda _name: flow)


def _patch_build_prompt(monkeypatch) -> None:
    monkeypatch.setattr(
        fsm_ops,
        "build_prompt",
        lambda flow_config, state_name, storage_path: f"instructions for {state_name}",
    )


def test_complete_stage_returns_decide_sentinel(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, DECIDE_FLOW)
    _patch_build_prompt(monkeypatch)

    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "DECIDING"}), encoding="utf-8")

    result = complete_stage({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    assert result.get("decide") is True
    assert isinstance(result.get("question"), str)
    assert isinstance(result.get("options"), dict)

    # STATE.json must be unchanged
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["current"] == "DECIDING"

    # No STATE_TRANSITION event written
    events_file = storage / "EVENTS.jsonl"
    if events_file.exists():
        lines = events_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            event = json.loads(line)
            assert event.get("type") != "STATE_TRANSITION"


def test_complete_stage_with_valid_decision(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, DECIDE_FLOW)
    _patch_build_prompt(monkeypatch)

    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "DECIDING"}), encoding="utf-8")

    result = complete_stage({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
        "decision": "a",
    })

    assert result.get("next_state") == "PATH_A"
    assert "agent" in result
    assert "instructions" in result

    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["current"] == "PATH_A"

    events_file = storage / "EVENTS.jsonl"
    assert events_file.exists()
    lines = events_file.read_text(encoding="utf-8").splitlines()
    event_types = [json.loads(l)["type"] for l in lines]
    assert "DECIDE_ROUTING" in event_types
    assert "STATE_TRANSITION" in event_types


def test_complete_stage_with_invalid_decision(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, DECIDE_FLOW)
    _patch_build_prompt(monkeypatch)

    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "DECIDING"}), encoding="utf-8")

    result = complete_stage({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
        "decision": "nonsense",
    })

    assert result.get("next_state") == "PATH_A"

    events_file = storage / "EVENTS.jsonl"
    assert events_file.exists()
    lines = events_file.read_text(encoding="utf-8").splitlines()
    decide_events = [json.loads(l) for l in lines if json.loads(l).get("type") == "DECIDE_ROUTING"]
    assert len(decide_events) == 1
    # The implementation mutates decision to the default before logging, so decision_input is "a"
    assert decide_events[0].get("decision_input") == "a"
