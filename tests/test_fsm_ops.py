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
    assert result["schema_version"] == "1"
    assert result["decision"] == "continue"
    assert result["role"] == "team/discover"
    assert "agent" in result["agent_hint"]
    assert "role" in result["agent_hint"]
    assert "codex_role" in result["codex_subagent"]
    assert "pathly_agent" in result["codex_subagent"]
    assert result["stage_brief"]["state"] == "STORMING"
    assert "open_feedback" in result["stage_brief"]
    assert "warnings" in result
    assert "storage_path" in result


def test_next_action_includes_codex_worker_hint(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    assert result["agent"] == "builder"
    hint = result["agent_hint"]
    assert hint["agent"] == "builder"
    assert hint["role"] == "worker"
    assert "PATHLY AGENT: builder" in hint["instructions"]
    assert "instructions for BUILDING" in hint["instructions"]
    # codex_subagent still exposes the old Codex-specific keys for backward compat
    codex = result["codex_subagent"]
    assert codex["pathly_agent"] == "builder"
    assert codex["codex_role"] == "worker"


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
    hint = fsm_ops._agent_hint("scout", "find the relevant files")

    assert hint["agent"] == "scout"
    assert hint["role"] == "explorer"
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
    assert result.get("current_state") in ("BUILDING", "DESIGNING")
    assert result["schema_version"] == "1"
    assert result["decision"] == "continue"
    assert result["role"] == result["agent"]
    assert "agent" in result["agent_hint"]
    assert "role" in result["agent_hint"]
    assert "codex_role" in result["codex_subagent"]
    assert "pathly_agent" in result["codex_subagent"]
    assert "stage_brief" in result
    assert "storage_path" in result


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
    assert result["decision"] == "block"
    assert result["agent_hint"]["agent"] == "builder"
    assert result["agent_hint"]["role"] == "worker"
    assert result["codex_subagent"]["codex_role"] == "worker"
    assert result["codex_subagent"]["pathly_agent"] == "builder"
    assert "stage_brief" in result
    assert "storage_path" in result
    assert result["warnings"] == [{"code": "open_feedback", "file": "REVIEW_FAILURES.md"}]


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

    assert result.get("current_state") == "PATH_A"
    assert "agent" in result
    assert "instructions" in result
    assert result["schema_version"] == "1"
    assert result["decision"] == "continue"
    assert result["role"] == result["agent"]

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

    assert result.get("current_state") == "PATH_A"
    assert result["decision"] == "continue"

    events_file = storage / "EVENTS.jsonl"
    assert events_file.exists()
    lines = events_file.read_text(encoding="utf-8").splitlines()
    decide_events = [json.loads(l) for l in lines if json.loads(l).get("type") == "DECIDE_ROUTING"]
    assert len(decide_events) == 1
    # The implementation mutates decision to the default before logging, so decision_input is "a"
    assert decide_events[0].get("decision_input") == "a"


# ── Adapter-neutral envelope tests ───────────────────────────────────────────

def test_agent_hint_uses_neutral_keys(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    hint = result["agent_hint"]
    assert "agent" in hint
    assert "role" in hint
    assert "codex_role" not in hint
    assert "pathly_agent" not in hint


def test_codex_subagent_retains_legacy_keys(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action({
        "flow": "test",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    codex = result["codex_subagent"]
    assert "codex_role" in codex
    assert "pathly_agent" in codex


def test_current_state_key_on_next_action(tmp_path):
    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert "current_state" in result
    assert "next_state" not in result


def test_current_state_key_on_complete_stage(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "PLANNING"}), encoding="utf-8")
    (storage / "IMPLEMENTATION_PLAN.md").write_text("plan content", encoding="utf-8")

    result = complete_stage({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert "current_state" in result
    assert "next_state" not in result


def test_escalate_decision_when_target_is_human(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "HUMAN_QUESTIONS.md").write_text("needs human input", encoding="utf-8")

    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result["decision"] == "escalate"
    assert result["target_agent"] == "human"


def test_block_decision_when_target_is_non_human_agent(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("these tests failed", encoding="utf-8")

    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result["decision"] == "block"
    assert result["target_agent"] != "human"


def test_blocked_response_has_agent_hint_and_storage_path(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("these tests failed", encoding="utf-8")

    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result.get("blocked") is True
    assert "agent_hint" in result
    assert "storage_path" in result


def test_next_action_corrupt_state_escalate_has_storage_path(tmp_path, monkeypatch):
    monkeypatch.setattr(fsm_ops, "recover_state", lambda *_: (_ for _ in ()).throw(RuntimeError("corrupt")))

    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })

    assert result["decision"] == "escalate"
    assert "storage_path" in result


def test_blocked_response_warnings_contain_open_feedback(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("these tests failed", encoding="utf-8")

    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert any(w.get("code") == "open_feedback" for w in result["warnings"])


def test_escalate_when_no_routable_feedback(tmp_path, monkeypatch):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "BUILDING"}), encoding="utf-8")
    # No feedback/ directory — route_feedback will return None

    monkeypatch.setattr(
        fsm_ops,
        "run_gates",
        lambda *_args, **_kwargs: {"gate_failed": "verify_gate", "feedback_file": "REVIEW_FAILURES.md"},
    )

    result = complete_stage({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result["decision"] == "escalate"
    assert result.get("blocked") is True


def test_escalate_response_not_continuable(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "HUMAN_QUESTIONS.md").write_text("needs human input", encoding="utf-8")

    result = next_action({
        "flow": "team",
        "topic": "test-topic",
        "project_root": str(tmp_path),
    })
    assert result["decision"] == "escalate"
    assert result.get("blocked") is True
    assert "next_state" not in result
