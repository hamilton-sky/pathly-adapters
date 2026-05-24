"""Unit and integration tests for run_gates() — Conv 1."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathly_orchestrator.fsm import run_gates, _verify_passed
from pathly_orchestrator.fsm_ops import complete_stage


# ── Helpers ───────────────────────────────────────────────────────────────────

def _storage(tmp_path: Path, topic: str = "test-feature") -> Path:
    p = tmp_path / "pathly" / "plans" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


def _make_flow(gates: dict) -> dict:
    return {
        "version": 1,
        "flow": "test",
        "storage_path": "pathly/plans/{topic}/",
        "states": ["A", "B", "C", "DONE"],
        "transitions": {"A": ["B"], "B": ["C"], "C": ["DONE"], "DONE": []},
        "agent_map": {
            "A": "team/build",
            "B": "team/review",
            "C": "team/test",
            "DONE": "team/retro",
        },
        "feedback_routing": {
            "REVIEW_FAILURES": "builder",
            "HUMAN_QUESTIONS": "human",
        },
        "transition_rules": {"A": {"default": "B"}, "B": {"default": "C"}},
        "transition_actions": {},
        "gates": gates,
    }


# ── _verify_passed unit tests ─────────────────────────────────────────────────

def test_verify_gate_pass(tmp_path):
    p = tmp_path / "VERIFY.md"
    p.write_text("RESULT: PASS\nsome other text", encoding="utf-8")
    assert _verify_passed(p, "RESULT: PASS") is True


def test_verify_gate_fail_absent(tmp_path):
    p = tmp_path / "VERIFY.md"
    assert _verify_passed(p, "RESULT: PASS") is False


def test_verify_gate_fail_wrong_marker(tmp_path):
    # "RESULT: PASS" appears in the body but is not the first non-blank line
    p = tmp_path / "VERIFY.md"
    p.write_text("RESULT: FAIL\nRESULT: PASS\n", encoding="utf-8")
    assert _verify_passed(p, "RESULT: PASS") is False


def test_verify_gate_fail_empty(tmp_path):
    p = tmp_path / "VERIFY.md"
    p.write_text("", encoding="utf-8")
    assert _verify_passed(p, "RESULT: PASS") is False


# ── run_gates unit tests ──────────────────────────────────────────────────────

def test_require_artifact_pass(tmp_path):
    storage = _storage(tmp_path)
    (storage / "REVIEW.md").write_text("lgtm", encoding="utf-8")
    flow = _make_flow({"A->B": [{"type": "require_artifact", "artifact": "REVIEW.md", "on_fail": "HUMAN_QUESTIONS.md"}]})
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None


def test_require_artifact_fail(tmp_path):
    storage = _storage(tmp_path)
    flow = _make_flow({"A->B": [{"type": "require_artifact", "artifact": "REVIEW.md", "on_fail": "HUMAN_QUESTIONS.md"}]})

    result = run_gates(flow, "A", "B", storage, "test-feature", 1)

    assert result is not None
    assert result["gate_failed"] == "require_artifact"
    assert result["feedback_file"] == "HUMAN_QUESTIONS.md"

    # on_fail file written to feedback/
    assert (storage / "feedback" / "HUMAN_QUESTIONS.md").exists()

    # GATE_FAILED event recorded
    events_file = storage / "EVENTS.jsonl"
    assert events_file.exists()
    events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()]
    gate_events = [e for e in events if e.get("type") == "GATE_FAILED"]
    assert len(gate_events) == 1
    assert gate_events[0]["gate"] == "require_artifact"
    assert gate_events[0]["transition"] == "A->B"

    # STATE.json must not have been created
    assert not (storage / "STATE.json").exists()


def test_unknown_gate_type_raises(tmp_path):
    storage = _storage(tmp_path)
    flow = _make_flow({"A->B": [{"type": "magic_gate", "artifact": "X.md", "on_fail": "F.md"}]})
    with pytest.raises(RuntimeError, match="Unknown gate type"):
        run_gates(flow, "A", "B", storage, "test-feature", 1)


# ── complete_stage integration tests ─────────────────────────────────────────

def _make_team_like_flow() -> dict:
    """Minimal flow mirroring team.flow.yaml BUILDING->REVIEWING gate."""
    return {
        "version": 1,
        "flow": "test",
        "storage_path": "pathly/plans/{topic}/",
        "states": ["BUILDING", "REVIEWING", "DONE"],
        "transitions": {"BUILDING": ["REVIEWING"], "REVIEWING": ["DONE"], "DONE": []},
        "agent_map": {
            "BUILDING": "team/build",
            "REVIEWING": "team/review",
            "DONE": "team/retro",
        },
        "feedback_routing": {
            "REVIEW_FAILURES": "builder",
        },
        "transition_rules": {
            "BUILDING": {"default": "REVIEWING"},
            "REVIEWING": {"default": "DONE"},
        },
        "transition_actions": {},
        "gates": {
            "BUILDING->REVIEWING": [
                {
                    "type": "verify_gate",
                    "artifact": "VERIFY.md",
                    "pass_marker": "RESULT: PASS",
                    "on_fail": "REVIEW_FAILURES.md",
                }
            ]
        },
    }


def test_complete_stage_gate_blocks(tmp_path, monkeypatch):
    """State must not advance when gate fails."""
    import pathly_orchestrator.fsm_ops as fsm_ops

    flow = _make_team_like_flow()
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda _name: flow)
    monkeypatch.setattr(
        fsm_ops,
        "build_prompt",
        lambda fc, state, sp: f"instructions for {state}",
    )

    storage = _storage(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "BUILDING"}), encoding="utf-8")
    # VERIFY.md absent — gate must block

    result = complete_stage({
        "flow": "test",
        "topic": "test-feature",
        "project_root": str(tmp_path),
    })

    assert result.get("blocked") is True
    # STATE.json still says BUILDING
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["current"] == "BUILDING"


def test_complete_stage_gate_then_advance(tmp_path, monkeypatch):
    """After feedback resolved and gate passes, state must advance."""
    import pathly_orchestrator.fsm_ops as fsm_ops

    flow = _make_team_like_flow()
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda _name: flow)
    monkeypatch.setattr(
        fsm_ops,
        "build_prompt",
        lambda fc, state, sp: f"instructions for {state}",
    )

    storage = _storage(tmp_path)
    state_file = storage / "STATE.json"
    state_file.write_text(json.dumps({"current": "BUILDING"}), encoding="utf-8")

    # Write passing VERIFY.md
    (storage / "VERIFY.md").write_text("RESULT: PASS\n", encoding="utf-8")

    result = complete_stage({
        "flow": "test",
        "topic": "test-feature",
        "project_root": str(tmp_path),
    })

    assert result.get("next_state") == "REVIEWING"
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["current"] == "REVIEWING"
