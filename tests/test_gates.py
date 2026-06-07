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


def _read_events_from_db(storage: Path, topic: str = "test-feature") -> list[dict]:
    """Read events from SQLite (events now stored in pathly.db, not EVENTS.jsonl)."""
    from pathly_orchestrator import db as _db
    conn = _db.get_db()
    project_root = str(storage.parent.parent.parent)
    return _db.read_events(conn, project_root, topic)


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

    # GATE_FAILED event recorded (now in SQLite, not EVENTS.jsonl)
    events = _read_events_from_db(storage)
    gate_events = [e for e in events if e.get("type") == "GATE_FAILED"]
    assert len(gate_events) == 1
    assert gate_events[0]["gate"] == "require_artifact"
    assert gate_events[0]["transition"] == "A->B"
    assert gate_events[0].get("ts"), "GATE_FAILED event must have a non-empty ts field"

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
    assert result.get("target_agent"), "blocked response must include a non-empty target_agent"
    assert result.get("file"), "blocked response must include a non-empty file"
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

    assert result.get("current_state") == "REVIEWING"
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
        "Files changed:\n- `src/foo.py`\n- `src/bar.py`\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"started_at": "2025-01-01T00:00:00+00:00", "preexisting_dirty": []}}),
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "diff" in args:
            return type("R", (), {"returncode": 0, "stdout": "src/foo.py\nsrc/bar.py\n", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None
    assert not (storage / "feedback" / "SCOPE_VIOLATION.md").exists()


def test_scope_gate_fail_undeclared_path(tmp_path, monkeypatch):
    """Diff includes a path not in declared scope — gate fails, SCOPE_VIOLATION.md written."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files:\n- `src/foo.py`\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"started_at": "2025-01-01T00:00:00+00:00", "preexisting_dirty": []}}),
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "diff" in args:
            return type("R", (), {"returncode": 0, "stdout": "src/foo.py\nsrc/UNEXPECTED.py\n", "stderr": ""})()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is not None
    assert result["gate_failed"] == "scope_gate"
    assert result["feedback_file"] == "SCOPE_VIOLATION.md"
    assert (storage / "feedback" / "SCOPE_VIOLATION.md").exists()

    events = _read_events_from_db(storage)
    gate_events = [e for e in events if e.get("type") == "GATE_FAILED"]
    assert len(gate_events) == 1
    assert gate_events[0]["gate"] == "scope_gate"
    assert gate_events[0].get("ts"), "GATE_FAILED event must have a non-empty ts field"


def test_scope_gate_no_declared_scope(tmp_path, monkeypatch):
    """Scope file exists but contains no file list — GATE_SKIPPED emitted, gate passes."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "This file has no declared paths.\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"started_at": "2025-01-01T00:00:00+00:00", "preexisting_dirty": []}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        fsm_mod.subprocess, "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None

    events = _read_events_from_db(storage)
    skipped = [e for e in events if e.get("type") == "GATE_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "no_declared_scope"


def test_scope_gate_no_build_baseline(tmp_path):
    """STATE.json has no build_baseline — GATE_SKIPPED with reason no_build_baseline, gate passes."""
    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files:\n- `src/foo.py`\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A"}), encoding="utf-8"
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None

    events = _read_events_from_db(storage)
    skipped = [e for e in events if e.get("type") == "GATE_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "no_build_baseline"


def test_scope_gate_degraded_truncated_baseline(tmp_path):
    """build_baseline.truncated=True → GATE_DEGRADED emitted and gate passes (permissive)."""
    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text("Files:\n- `src/foo.py`\n", encoding="utf-8")
    (storage / "STATE.json").write_text(
        json.dumps({
            "current": "A",
            "build_baseline": {
                "started_at": "2025-01-01T00:00:00+00:00",
                "preexisting_dirty": ["x.py"] * 500,
                "truncated": True,
            },
        }),
        encoding="utf-8",
    )

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None  # gate passes in permissive mode

    events = _read_events_from_db(storage)
    degraded = [e for e in events if e.get("type") == "GATE_DEGRADED"]
    assert len(degraded) == 1
    assert degraded[0]["gate"] == "scope_gate"


def test_verify_gate_pass_marker_in_body_not_line1(tmp_path):
    """Pass marker present in body but NOT on line 1 — gate must fail (line-1 sentinel)."""
    p = tmp_path / "VERIFY.md"
    p.write_text("# Header\nRESULT: PASS\nSome notes\n", encoding="utf-8")
    assert _verify_passed(p, "RESULT: PASS") is False


def test_no_gates_on_transition(tmp_path):
    """Empty gates dict means no gate is checked — run_gates returns None (transition proceeds)."""
    storage = _storage(tmp_path)
    flow = _make_flow({})
    result = run_gates(flow, "BUILDING", "REVIEWING", storage, "t", 0)
    assert result is None


# ── plan-file exemption tests ─────────────────────────────────────────────────

def test_scope_gate_plan_files_exempt(tmp_path, monkeypatch):
    """Builder edits CONVERSATION_PROMPTS.md and PROGRESS.md only — gate passes, no GATE_FAILED."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    # Declared scope references a codebase file, but builder only touched plan files.
    (storage / "SCOPE.md").write_text(
        "Files:\n- `src/app.py`\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"started_at": "2025-01-01T00:00:00Z", "preexisting_dirty": []}}),
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "diff" in args:
            return type("R", (), {
                "returncode": 0,
                "stdout": "pathly/plans/test-feature/CONVERSATION_PROMPTS.md\npathly/plans/test-feature/PROGRESS.md\n",
                "stderr": "",
            })()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None
    assert not (storage / "feedback" / "SCOPE_VIOLATION.md").exists()


def test_scope_gate_plan_files_with_declared_codebase_pass(tmp_path, monkeypatch):
    """Builder edits declared codebase files AND plan files — gate still passes."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files:\n- `src/app.py`\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"started_at": "2025-01-01T00:00:00Z", "preexisting_dirty": []}}),
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "diff" in args:
            return type("R", (), {
                "returncode": 0,
                "stdout": "src/app.py\npathly/plans/test-feature/CONVERSATION_PROMPTS.md\npathly/plans/test-feature/PROGRESS.md\n",
                "stderr": "",
            })()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is None
    assert not (storage / "feedback" / "SCOPE_VIOLATION.md").exists()


def test_scope_gate_plan_files_do_not_mask_undeclared_codebase(tmp_path, monkeypatch):
    """Plan-file edits are exempt, but an undeclared codebase file still triggers GATE_FAILED."""
    import pathly_orchestrator.fsm as fsm_mod

    storage = _storage(tmp_path)
    (storage / "SCOPE.md").write_text(
        "Files:\n- `src/app.py`\n", encoding="utf-8"
    )
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "build_baseline": {"started_at": "2025-01-01T00:00:00Z", "preexisting_dirty": []}}),
        encoding="utf-8",
    )

    def fake_run(args, **kwargs):
        if "diff" in args:
            return type("R", (), {
                "returncode": 0,
                # src/out_of_scope.py is not declared — should still fail
                "stdout": "src/app.py\nsrc/out_of_scope.py\npathly/plans/test-feature/PROGRESS.md\n",
                "stderr": "",
            })()
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(fsm_mod.subprocess, "run", fake_run)

    flow = _make_flow_with_scope_gate()
    result = run_gates(flow, "A", "B", storage, "test-feature", 1)
    assert result is not None
    assert result["gate_failed"] == "scope_gate"
    assert (storage / "feedback" / "SCOPE_VIOLATION.md").exists()
