"""Integration tests for fsm_ops.py (next_action, complete_stage)."""

from __future__ import annotations

import json
import logging
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
    # Feature-centric layout: the team flow resolves a topic to pathly/features/<topic>/.
    p = tmp_path / "pathly" / "features" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Basic routing tests ───────────────────────────────────────────────────────


def test_next_action_initial_state(tmp_path):
    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
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

    result = next_action(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )

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

    result = next_action(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )

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
    (storage / "IMPLEMENTATION_PLAN.md").write_text(
        "## Phase 1\nplan content", encoding="utf-8"
    )

    result = complete_stage(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
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
    (feedback_dir / "REVIEW_FAILURES.md").write_text(
        "these tests failed", encoding="utf-8"
    )

    result = complete_stage(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
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
    assert result["warnings"] == [
        {"code": "open_feedback", "file": "REVIEW_FAILURES.md"}
    ]


# ── Two-call decide protocol ──────────────────────────────────────────────────


def _patch_load_flow(monkeypatch, flow: dict) -> None:
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: flow)


def _patch_build_prompt(monkeypatch) -> None:
    monkeypatch.setattr(
        fsm_ops,
        "build_prompt",
        lambda *args, **kwargs: f"instructions for {args[1]}",
    )


def test_complete_stage_returns_decide_sentinel(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, DECIDE_FLOW)
    _patch_build_prompt(monkeypatch)

    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "DECIDING"}), encoding="utf-8")

    result = complete_stage(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )

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

    result = complete_stage(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
            "decision": "a",
        }
    )

    assert result.get("current_state") == "PATH_A"
    assert "agent" in result
    assert "instructions" in result
    assert result["schema_version"] == "1"
    assert result["decision"] == "continue"
    assert result["role"] == result["agent"]

    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["current"] == "PATH_A"

    # Events now in SQLite, not EVENTS.jsonl
    from pathly_orchestrator import db as _db

    _conn = _db.get_db()
    events = _db.read_events(_conn, str(tmp_path), "test-topic")
    event_types = [e["type"] for e in events]
    assert "DECIDE_ROUTING" in event_types
    assert "STATE_TRANSITION" in event_types


def test_complete_stage_with_invalid_decision(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, DECIDE_FLOW)
    _patch_build_prompt(monkeypatch)

    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "DECIDING"}), encoding="utf-8")

    result = complete_stage(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
            "decision": "nonsense",
        }
    )

    assert result.get("current_state") == "PATH_A"
    assert result["decision"] == "continue"

    # Events now in SQLite, not EVENTS.jsonl
    from pathly_orchestrator import db as _db

    _conn = _db.get_db()
    events = _db.read_events(_conn, str(tmp_path), "test-topic")
    decide_events = [e for e in events if e.get("type") == "DECIDE_ROUTING"]
    assert len(decide_events) == 1
    # The implementation mutates decision to the default before logging, so decision_input is "a"
    assert decide_events[0].get("decision_input") == "a"


# ── Adapter-neutral envelope tests ───────────────────────────────────────────


def test_agent_hint_uses_neutral_keys(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )

    hint = result["agent_hint"]
    assert "agent" in hint
    assert "role" in hint
    assert "codex_role" not in hint
    assert "pathly_agent" not in hint


def test_codex_subagent_retains_legacy_keys(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action(
        {
            "flow": "test",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )

    codex = result["codex_subagent"]
    assert "codex_role" in codex
    assert "pathly_agent" in codex


def test_current_state_key_on_next_action(tmp_path):
    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert "current_state" in result
    assert "next_state" not in result


def test_current_state_key_on_complete_stage(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "PLANNING"}), encoding="utf-8")
    # Must contain the PLANNING->DESIGNING on_content marker ('## Phase'), otherwise the
    # rule falls through to default:PLANNING and this is a no-op self-loop rather than an advance.
    (storage / "IMPLEMENTATION_PLAN.md").write_text(
        "## Phase 1\nplan content", encoding="utf-8"
    )

    result = complete_stage(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    # A successful advance reports BOTH the new current_state and an explicit next_state
    # (the advance signal the supervisor/runner driver loops gate on). They are equal: the
    # FSM has already transitioned, so current_state == next_state == the state advanced into.
    assert "current_state" in result
    assert result["current_state"] == "DESIGNING"
    assert result["next_state"] == "DESIGNING"


def test_escalate_decision_when_target_is_human(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "HUMAN_QUESTIONS.md").write_text(
        "needs human input", encoding="utf-8"
    )

    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert result["decision"] == "escalate"
    assert result["target_agent"] == "human"


def test_block_decision_when_target_is_non_human_agent(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text(
        "these tests failed", encoding="utf-8"
    )

    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert result["decision"] == "block"
    assert result["target_agent"] != "human"


def test_blocked_response_has_agent_hint_and_storage_path(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text(
        "these tests failed", encoding="utf-8"
    )

    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert result.get("blocked") is True
    assert "agent_hint" in result
    assert "storage_path" in result


def test_next_action_corrupt_state_escalate_has_storage_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fsm_ops,
        "recover_state",
        lambda *_: (_ for _ in ()).throw(RuntimeError("corrupt")),
    )

    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )

    assert result["decision"] == "escalate"
    assert "storage_path" in result


def test_blocked_response_warnings_contain_open_feedback(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text(
        "these tests failed", encoding="utf-8"
    )

    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert any(w.get("code") == "open_feedback" for w in result["warnings"])


def test_escalate_when_no_routable_feedback(tmp_path, monkeypatch):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "BUILDING"}), encoding="utf-8")
    # No feedback/ directory — route_feedback will return None

    monkeypatch.setattr(
        fsm_ops,
        "run_gates",
        lambda *_: {
            "gate_failed": "verify_gate",
            "feedback_file": "REVIEW_FAILURES.md",
        },
    )

    result = complete_stage(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert result["decision"] == "escalate"
    assert result.get("blocked") is True


def test_escalate_response_not_continuable(tmp_path):
    storage = _storage_path(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "REVIEWING"}), encoding="utf-8")
    feedback_dir = storage / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "HUMAN_QUESTIONS.md").write_text(
        "needs human input", encoding="utf-8"
    )

    result = next_action(
        {
            "flow": "team",
            "topic": "test-topic",
            "project_root": str(tmp_path),
        }
    )
    assert result["decision"] == "escalate"
    assert result.get("blocked") is True
    assert "next_state" not in result


# ── preferred_adapter tests ───────────────────────────────────────────────────


def test_resolve_adapter_state_in_map():
    flow = {**ROUTING_FLOW, "adapter_map": {"default": "claude", "BUILDING": "codex"}}
    assert fsm_ops._resolve_adapter(flow, "BUILDING") == "codex"


def test_resolve_adapter_state_not_in_map_uses_default():
    flow = {**ROUTING_FLOW, "adapter_map": {"default": "claude", "REVIEWING": "codex"}}
    assert fsm_ops._resolve_adapter(flow, "BUILDING") == "claude"


def test_resolve_adapter_no_adapter_map_returns_empty():
    assert fsm_ops._resolve_adapter(ROUTING_FLOW, "BUILDING") == ""


def test_next_action_preferred_adapter_from_state(tmp_path, monkeypatch):
    flow = {**ROUTING_FLOW, "adapter_map": {"default": "claude", "BUILDING": "codex"}}
    _patch_load_flow(monkeypatch, flow)
    _patch_build_prompt(monkeypatch)

    result = next_action(
        {"flow": "test", "topic": "test-topic", "project_root": str(tmp_path)}
    )
    assert result["preferred_adapter"] == "codex"


def test_next_action_preferred_adapter_fallback_to_default(tmp_path, monkeypatch):
    flow = {**ROUTING_FLOW, "adapter_map": {"default": "claude", "REVIEWING": "codex"}}
    _patch_load_flow(monkeypatch, flow)
    _patch_build_prompt(monkeypatch)

    result = next_action(
        {"flow": "test", "topic": "test-topic", "project_root": str(tmp_path)}
    )
    assert result["preferred_adapter"] == "claude"


def test_next_action_preferred_adapter_empty_when_no_map(tmp_path, monkeypatch):
    _patch_load_flow(monkeypatch, ROUTING_FLOW)
    _patch_build_prompt(monkeypatch)

    result = next_action(
        {"flow": "test", "topic": "test-topic", "project_root": str(tmp_path)}
    )
    assert result["preferred_adapter"] == ""


def test_blocked_response_carries_preferred_adapter():
    state_info = {
        "current_state": "REVIEWING",
        "conv": 1,
        "retry_count": 0,
        "limits": {},
    }
    feedback = {"target_agent": "builder", "file": "REVIEW_FAILURES.md"}
    result = fsm_ops._blocked_response(feedback, state_info, preferred_adapter="codex")
    assert result["preferred_adapter"] == "codex"


def test_build_prompt_includes_pipeline_history(tmp_path):
    """build_prompt appends ## Pipeline History when EVENTS.jsonl has AGENT_DONE entries."""
    from unittest.mock import patch
    from pathly_orchestrator.fsm_ops import build_prompt

    # Set up temp project root: pathly/plans/test-feature/EVENTS.jsonl
    feature = "test-feature"
    plan_dir = tmp_path / "pathly" / "plans" / feature
    plan_dir.mkdir(parents=True, exist_ok=True)
    # Write event via eventlog so it goes to DB (works in both normal and PATHLY_DB_ONLY mode)
    from pathly_orchestrator.eventlog import append_event as _ae

    _ae(
        str(plan_dir),
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 1,
            "summary": "smoke test entry",
            "ts": "2026-01-01T00:00:00Z",
            "schema_version": 1,
        },
    )

    storage_path = (
        plan_dir  # storage_path.name == feature, .parent.parent.parent == tmp_path
    )
    flow_config = {
        "agent_map": {"BUILDING": "quick"},
        "composition": {},
    }

    with patch(
        "pathly_orchestrator.fsm_compose._load_agent_text",
        return_value="base agent text",
    ):
        result = build_prompt(flow_config, "BUILDING", storage_path)

    assert (
        "## Pipeline History" in result
    ), f"History block missing from prompt:\n{result}"
    assert "smoke test entry" in result, f"History entry missing from prompt:\n{result}"


def test_build_prompt_threads_goal_id_into_composition(tmp_path):
    """Regression: the FSM/consultation path must thread goal_id into the caps so the
    terminal planner keeps its goal_id-gated task-dag-post fragment. Before the fix,
    build_prompt passed the bare adapter string → goal_id absent → DAG-seeding dropped →
    a `decompose via consultation` run finished without ever seeding the board DAG."""
    from pathly_orchestrator.fsm_ops import build_prompt

    feature = "goal-decompose-feature"
    plan_dir = tmp_path / "pathly" / "plans" / feature
    plan_dir.mkdir(parents=True, exist_ok=True)
    flow_config = {
        "agent_map": {"PLANNING": "planning/plan"},
        "composition": {},
    }

    _MARKER = "## Posting the task DAG to the Comms Board"

    with_goal = build_prompt(flow_config, "PLANNING", plan_dir, "goal-123")
    assert _MARKER in with_goal, (
        "task-dag-post fragment was dropped even though goal_id was supplied — "
        "goal_id is not reaching compose_skill"
    )

    # No goal_id (ordinary feature run) → gated fragment correctly stays dropped.
    without_goal = build_prompt(flow_config, "PLANNING", plan_dir, "")
    assert _MARKER not in without_goal


def test_build_prompt_uses_parent_board_scope_for_goal(tmp_path):
    """A goal-decompose run's on-disk storage nests under the parent feature
    (pathly/features/<feature>/goals/<slug>) and its dir name is the goal slug (run
    isolation), but its stage agents must post to / read the PARENT board the goal lives
    on. build_prompt must inject the parent scope as <feature>, not the slug, when goal_id
    is given — otherwise the consultation's artifacts orphan onto a throwaway slug-scoped
    board instead of the feature board it was spawned from."""
    from unittest.mock import patch
    from pathly_orchestrator.fsm_ops import build_prompt
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_messages import post_message

    parent = "cli-command-center"
    slug = "studio-climonitorbar-review-3453c9bb"

    # The goal lives on the parent FEATURE board.
    goal_id = post_message(
        get_db(),
        board="feature",
        scope=parent,
        from_agent="human",
        type="goal",
        text="Studio CliMonitorBar review",
    )

    # On-disk storage nests under the parent feature; the run's dir name is the slug (isolation).
    slug_dir = tmp_path / "pathly" / "features" / parent / "goals" / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    flow_config = {"agent_map": {"ARCHITECTING": "quick"}, "composition": {}}

    with patch(
        "pathly_orchestrator.fsm_compose._load_agent_text",
        return_value="base agent text",
    ):
        with_goal = build_prompt(flow_config, "ARCHITECTING", slug_dir, goal_id)
        without_goal = build_prompt(flow_config, "ARCHITECTING", slug_dir, "")

    # goal_id present → board scope resolves to the parent feature.
    assert f"Feature: {parent}" in with_goal
    assert f"Feature: {slug}" not in with_goal
    # No goal_id (ordinary run) → board scope = storage dir name, byte-identical to before.
    assert f"Feature: {slug}" in without_goal
    assert f"Feature: {parent}" not in without_goal


# ── T2.4 — FSM loads flow from rows (Phase 2 regression) ─────────────────────


@pytest.mark.parametrize(
    "flow_name,expected_first_state",
    [
        ("team", "STORMING"),
        ("debug", "INVESTIGATING"),
        ("explore", "FRAMING"),
        ("test", "STORMING"),
        ("quick-fix", "SCOPING"),
    ],
)
def test_load_flow_from_rows(flow_name, expected_first_state):
    """_load_flow returns a rows-assembled dict equal to the original YAML."""
    import sqlite3 as _sqlite3
    import yaml as _yaml
    from importlib.resources import files as _files
    from pathly_orchestrator.db.migrations import _run_migrations
    from pathly_orchestrator.db.queries.flow_defs import upsert_flow_definition

    # Build an isolated in-memory DB with the flow rows populated.
    # We cannot use get_db() here (that returns the per-test DB which already has
    # the flows from _refresh_flows). Instead, patch _load_flow to use a fresh conn.
    conn = _sqlite3.connect(":memory:")
    conn.row_factory = _sqlite3.Row
    _run_migrations(conn)

    text = (
        _files("pathly_data")
        .joinpath(f"core/flows/{flow_name}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    original = _yaml.safe_load(text)
    upsert_flow_definition(conn, None, flow_name, "", text)

    import json as _json
    from pathly_orchestrator.db.queries.flow_defs import (
        _assemble_flow_dict,
        read_flow_definitions,
        read_flow_nodes,
    )

    rows = read_flow_definitions(conn, project_root=None)
    row = next(r for r in rows if r["name"] == flow_name)
    node_rows = read_flow_nodes(conn, row["id"])
    assert node_rows, f"No node rows found for {flow_name}"

    flow_level_config = _json.loads(row.get("config_json") or "{}")
    assembled = _assemble_flow_dict(conn, row["id"], flow_level_config)

    assert assembled["states"][0] == expected_first_state
    assert "states" in assembled
    assert "transitions" in assembled
    assert "agent_map" in assembled
    assert assembled == original, (
        f"Assembled dict does not match original for {flow_name}. "
        f"Keys in original not in assembled: {set(original) - set(assembled)}. "
        f"Keys in assembled not in original: {set(assembled) - set(original)}."
    )


# ── _resolve_storage_path tests ──────────────────────────────────────────────


def test_resolve_storage_path_prefers_new_style(tmp_path):
    """New-style pathly/<topic>/ is returned when that directory exists."""
    topic = "my-feature"
    new_dir = tmp_path / "pathly" / topic
    new_dir.mkdir(parents=True)
    flow = {**ROUTING_FLOW, "storage_path": "pathly/plans/{topic}/"}
    result = fsm_ops._resolve_storage_path(flow, str(tmp_path), topic)
    assert result == new_dir


def test_resolve_storage_path_falls_back_to_plans(tmp_path):
    """Falls back to pathly/plans/<topic>/ when new-style dir does not exist."""
    topic = "legacy-feature"
    flow = {**ROUTING_FLOW, "storage_path": "pathly/plans/{topic}/"}
    result = fsm_ops._resolve_storage_path(flow, str(tmp_path), topic)
    assert result == tmp_path / "pathly" / "plans" / topic


def test_resolve_storage_path_legacy_not_shadowed_by_missing_new_style(tmp_path):
    """New-style dir that does NOT exist does not shadow legacy path."""
    topic = "comms-board"
    legacy_dir = tmp_path / "pathly" / "plans" / topic
    legacy_dir.mkdir(parents=True)
    flow = {**ROUTING_FLOW, "storage_path": "pathly/plans/{topic}/"}
    result = fsm_ops._resolve_storage_path(flow, str(tmp_path), topic)
    assert result == legacy_dir


def test_resolve_storage_path_raises_on_absolute_topic(tmp_path):
    """Absolute topic in P1 mode: raises ValueError."""
    flow = {
        "storage_path": "pathly/plans/{topic}/",
    }
    topic = str(tmp_path / "some" / "absolute")  # an absolute path on this OS
    with pytest.raises(ValueError, match="unsafe topic"):
        fsm_ops._resolve_storage_path(flow, str(tmp_path), topic)


def test_resolve_storage_path_normal_slug_no_warning(tmp_path, caplog):
    """Plain slug must produce no storage warning and return the new-style dir."""
    flow = {
        "storage_path": "pathly/plans/{topic}/",
    }
    topic = "my-feature-slug"
    new_style = tmp_path / "pathly" / topic
    new_style.mkdir(parents=True)
    with caplog.at_level(logging.WARNING, logger="pathly.storage"):
        result = fsm_ops._resolve_storage_path(flow, str(tmp_path), topic)
    storage_warnings = [r for r in caplog.records if r.name == "pathly.storage"]
    assert len(storage_warnings) == 0
    assert result == new_style
