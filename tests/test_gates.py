"""Unit and integration tests for run_gates() — Conv 1 and Conv 2 (scope_gate)."""
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


# ── scope_gate tests ──────────────────────────────────────────────────────────

def _make_flow_with_scope_gate(gates: dict | None = None) -> dict:
    if gates is None:
        gates = {
            "A->B": [
                {
                    "type": "scope_gate",
                    "scope_file": "SCOPE.md",
                    "on_fail": "SCOPE_VIOLATION.md",
                }
            ]
        }
    flow = _make_flow(gates)
    flow["feedback_routing"]["SCOPE_VIOLATION"] = "builder"
    return flow


def test_scope_gate_pass(tmp_path, monkeypatch):
    """Diff only touches declared files — gate passes, no feedback file written."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files changed:\n- src/foo.py\n- src/bar.py\n", encoding="utf-8"
    )
    state_sha = "abc123"
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "conv_start_sha": state_sha}), encoding="utf-8"
    )

    monkeypatch.setattr(
        fsm_mod.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "R", (), {"returncode": 0, "stdout": "src/foo.py\nsrc/bar.py\n", "stderr": ""}
        )(),
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None
    assert not (storage / "feedback" / "SCOPE_VIOLATION.md").exists()


def test_scope_gate_fail_undeclared_path(tmp_path, monkeypatch):
    """Diff includes a path not in declared scope — gate fails, SCOPE_VIOLATION.md written."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files:\n- src/foo.py\n", encoding="utf-8"
    )
    state_sha = "abc123"
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "conv_start_sha": state_sha}), encoding="utf-8"
    )

    monkeypatch.setattr(
        fsm_mod.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "R", (), {"returncode": 0, "stdout": "src/foo.py\nsrc/UNEXPECTED.py\n", "stderr": ""}
        )(),
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is not None
    assert result["gate_failed"] == "scope_gate"
    assert result["feedback_file"] == "SCOPE_VIOLATION.md"
    assert (storage / "feedback" / "SCOPE_VIOLATION.md").exists()

    events_file = storage / "EVENTS.jsonl"
    events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()]
    gate_events = [e for e in events if e.get("type") == "GATE_FAILED"]
    assert len(gate_events) == 1
    assert gate_events[0]["gate"] == "scope_gate"


def test_scope_gate_no_declared_scope(tmp_path):
    """Scope file exists but contains no file list — GATE_SKIPPED emitted, gate passes."""
    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "This file has no declared paths.\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "conv_start_sha": "abc123"}), encoding="utf-8"
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None

    events_file = storage / "EVENTS.jsonl"
    events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()]
    skipped = [e for e in events if e.get("type") == "GATE_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "no_declared_scope"


def test_scope_gate_no_baseline_sha(tmp_path):
    """STATE.json has no conv_start_sha — GATE_SKIPPED emitted, gate passes."""
    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files:\n- src/foo.py\n", encoding="utf-8"
    )
    # STATE.json without conv_start_sha
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A"}), encoding="utf-8"
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None

    events_file = storage / "EVENTS.jsonl"
    events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines()]
    skipped = [e for e in events if e.get("type") == "GATE_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "no_baseline_sha"


def test_verify_gate_pass_marker_in_body_not_line1(tmp_path):
    """Pass marker present in body but NOT on line 1 — gate must fail (line-1 sentinel)."""
    p = tmp_path / "VERIFY.md"
    p.write_text("# Header\nRESULT: PASS\nSome notes\n", encoding="utf-8")
    assert _verify_passed(p, "RESULT: PASS") is False
