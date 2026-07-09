"""Unit tests for pathly_orchestrator.fsm functions."""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from pathly_orchestrator.fsm import (
    append_event,
    evaluate_transition_rules,
    recover_state,
    route_feedback,
    run_transition_actions,
    write_state,
)


def _load_team_flow() -> dict:
    text = files("pathly_data").joinpath("core/flows/team.flow.yaml").read_text()
    return yaml.safe_load(text)


# ── recover_state ─────────────────────────────────────────────────────────────


def test_recover_state_no_state_json(tmp_path):
    flow = _load_team_flow()
    result = recover_state(tmp_path, flow)
    assert result["current_state"] == "STORMING"
    assert result["conv"] == 0
    assert result["open_feedback_files"] == []


def test_recover_state_with_state_json(tmp_path):
    flow = _load_team_flow()
    state_file = tmp_path / "STATE.json"
    state_file.write_text(
        json.dumps({"current": "BUILDING", "current_conversation": 2}), encoding="utf-8"
    )
    result = recover_state(tmp_path, flow)
    assert result["current_state"] == "BUILDING"
    assert result["conv"] == 2


def test_recover_state_open_feedback_files(tmp_path):
    flow = _load_team_flow()
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("some failures", encoding="utf-8")
    result = recover_state(tmp_path, flow)
    assert result["open_feedback_files"] == ["REVIEW_FAILURES.md"]


def test_recover_state_limits_defaults(tmp_path):
    flow = _load_team_flow()
    flow_copy = copy.deepcopy(flow)
    flow_copy.pop("limits", None)
    result = recover_state(tmp_path, flow_copy)
    assert result["limits"]["needs_context_per_stage"] == 3
    assert result["limits"]["feedback_rounds_per_stage"] == 2


def test_recover_state_limits_top_level(tmp_path):
    flow = _load_team_flow()
    flow_copy = copy.deepcopy(flow)
    flow_copy["limits"] = {"needs_context_per_stage": 5}
    result = recover_state(tmp_path, flow_copy)
    assert result["limits"]["needs_context_per_stage"] == 5
    assert result["limits"]["feedback_rounds_per_stage"] == 2


def test_recover_state_limits_per_state(tmp_path):
    flow = _load_team_flow()
    flow_copy = copy.deepcopy(flow)
    state_file = tmp_path / "STATE.json"
    state_file.write_text(json.dumps({"current": "BUILDING"}), encoding="utf-8")
    flow_copy["states_config"] = {
        "BUILDING": {"limits": {"needs_context_per_stage": 1}}
    }
    result = recover_state(tmp_path, flow_copy)
    assert result["limits"]["needs_context_per_stage"] == 1
    assert result["limits"]["feedback_rounds_per_stage"] == 2


# ── evaluate_transition_rules ─────────────────────────────────────────────────


def test_evaluate_l1_artifact_present(tmp_path):
    flow = _load_team_flow()
    (tmp_path / "IMPLEMENTATION_PLAN.md").write_text(
        "## Phase 1\nsome plan", encoding="utf-8"
    )
    result = evaluate_transition_rules(flow, "PLANNING", tmp_path)
    assert result == "DESIGNING"


def test_evaluate_l1_artifact_absent(tmp_path):
    flow = _load_team_flow()
    result = evaluate_transition_rules(flow, "PLANNING", tmp_path)
    assert result == "PLANNING"


def test_evaluate_l1_before_l2(tmp_path):
    # L1 (on_artifact) fires before L2 (on_content) — use a synthetic flow to avoid
    # coupling to team.flow.yaml's transition_rules structure
    flow = {
        "states": ["ALPHA", "BETA", "GAMMA"],
        "transitions": {"ALPHA": ["BETA"], "BETA": [], "GAMMA": []},
        "transition_rules": {
            "ALPHA": {
                "on_artifact": {"EXISTS.md": "BETA"},
                "on_content": [
                    {"file": "TRIGGER.md", "contains": "go", "next": "GAMMA"}
                ],
                "default": "ALPHA",
            }
        },
    }
    (tmp_path / "EXISTS.md").write_text("exists", encoding="utf-8")
    (tmp_path / "TRIGGER.md").write_text("go", encoding="utf-8")
    result = evaluate_transition_rules(flow, "ALPHA", tmp_path)
    assert result == "BETA"  # L1 fired first


def test_evaluate_l2_contains_match(tmp_path):
    flow = {
        "states": ["ALPHA", "BETA"],
        "transitions": {"ALPHA": ["BETA"], "BETA": []},
        "transition_rules": {
            "ALPHA": {
                "on_content": [
                    {"file": "STATUS.md", "contains": "ready", "next": "BETA"}
                ],
                "default": "ALPHA",
            }
        },
    }
    (tmp_path / "STATUS.md").write_text("system is ready to proceed", encoding="utf-8")
    result = evaluate_transition_rules(flow, "ALPHA", tmp_path)
    assert result == "BETA"


def test_evaluate_l2_regex_match(tmp_path):
    flow = {
        "states": ["ALPHA", "BETA"],
        "transitions": {"ALPHA": ["BETA"], "BETA": []},
        "transition_rules": {
            "ALPHA": {
                "on_content": [
                    {"file": "STATUS.md", "regex": r"error\s+\d+", "next": "BETA"}
                ],
                "default": "ALPHA",
            }
        },
    }
    (tmp_path / "STATUS.md").write_text("detected error 404", encoding="utf-8")
    result = evaluate_transition_rules(flow, "ALPHA", tmp_path)
    assert result == "BETA"


def test_evaluate_l2_no_match(tmp_path):
    flow = {
        "states": ["ALPHA", "BETA"],
        "transitions": {"ALPHA": ["BETA"], "BETA": []},
        "transition_rules": {
            "ALPHA": {
                "on_content": [
                    {"file": "STATUS.md", "contains": "ready", "next": "BETA"}
                ],
                "default": "ALPHA",
            }
        },
    }
    (tmp_path / "STATUS.md").write_text("not matching anything", encoding="utf-8")
    result = evaluate_transition_rules(flow, "ALPHA", tmp_path)
    assert result == "ALPHA"


def test_evaluate_l3_decide_sentinel(tmp_path):
    flow = {
        "states": ["DECIDING", "PATH_A", "PATH_B"],
        "transitions": {"DECIDING": ["PATH_A", "PATH_B"], "PATH_A": [], "PATH_B": []},
        "transition_rules": {
            "DECIDING": {
                "decide": {
                    "context_file": "CONTEXT.md",
                    "question": "Which path?",
                    "options": {"a": "PATH_A", "b": "PATH_B"},
                    "default": "PATH_A",
                }
            }
        },
    }
    result = evaluate_transition_rules(flow, "DECIDING", tmp_path)
    assert isinstance(result, dict)
    assert result.get("decide") is True
    assert "context_file" in result
    assert "question" in result
    assert "options" in result
    assert "default" in result


def test_evaluate_fallback_default(tmp_path):
    flow = _load_team_flow()
    result = evaluate_transition_rules(flow, "BUILDING", tmp_path)
    assert result == "REVIEWING"


def test_evaluate_no_rules_uses_transitions(tmp_path):
    flow = _load_team_flow()
    result = evaluate_transition_rules(flow, "STORMING", tmp_path)
    assert result == "PLANNING"


def test_evaluate_order_l1_before_l3(tmp_path):
    flow = {
        "states": ["DECIDING", "PATH_A", "PATH_B"],
        "transitions": {"DECIDING": ["PATH_A", "PATH_B"], "PATH_A": [], "PATH_B": []},
        "transition_rules": {
            "DECIDING": {
                "on_artifact": {"ARTIFACT.md": "PATH_B"},
                "decide": {
                    "context_file": "CONTEXT.md",
                    "question": "Which path?",
                    "options": {"a": "PATH_A", "b": "PATH_B"},
                    "default": "PATH_A",
                },
            }
        },
    }
    (tmp_path / "ARTIFACT.md").write_text("exists", encoding="utf-8")
    result = evaluate_transition_rules(flow, "DECIDING", tmp_path)
    assert result == "PATH_B"


# ── route_feedback ────────────────────────────────────────────────────────────


def test_route_feedback_empty_dir(tmp_path):
    flow = _load_team_flow()
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    result = route_feedback(flow, tmp_path)
    assert result is None


def test_route_feedback_no_dir(tmp_path):
    flow = _load_team_flow()
    result = route_feedback(flow, tmp_path)
    assert result is None


def test_route_feedback_single_file(tmp_path):
    flow = _load_team_flow()
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("failures", encoding="utf-8")
    result = route_feedback(flow, tmp_path)
    assert result is not None
    assert result["file"] == "REVIEW_FAILURES.md"
    assert result["target_agent"] == "builder"


def test_route_feedback_priority(tmp_path):
    flow = _load_team_flow()
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("failures", encoding="utf-8")
    (feedback_dir / "ARCH_FEEDBACK.md").write_text("arch notes", encoding="utf-8")
    result = route_feedback(flow, tmp_path)
    assert result is not None
    assert result["file"] == "ARCH_FEEDBACK.md"


def test_route_feedback_human_wins(tmp_path):
    flow = _load_team_flow()
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    human_content = "Please answer this question."
    (feedback_dir / "HUMAN_QUESTIONS.md").write_text(human_content, encoding="utf-8")
    (feedback_dir / "REVIEW_FAILURES.md").write_text("failures", encoding="utf-8")
    result = route_feedback(flow, tmp_path)
    assert result is not None
    assert result["file"] == "HUMAN_QUESTIONS.md"
    assert "instructions" in result
    assert result["instructions"] == human_content


# ── run_transition_actions ────────────────────────────────────────────────────


def _make_commit_flow() -> dict:
    # auto_commit is opt-in now (default OFF). The flow/action enables it explicitly to
    # exercise the commit path; the gated-off default is covered by its own test below.
    return {
        "storage_path": "pathly/plans/{topic}/",
        "transition_actions": {
            "BUILDING->REVIEWING": [
                {
                    "skill": "commit",
                    "message": "feat: complete building stage",
                    "auto_commit": True,
                }
            ]
        },
    }


def _make_archive_flow() -> dict:
    return {
        "storage_path": "pathly/plans/{topic}/",
        "transition_actions": {"RETRO->DONE": [{"skill": "archive-artifacts"}]},
    }


def test_run_transition_actions_git_commit(tmp_path):
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    flow = _make_commit_flow()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_transition_actions(
            flow, "BUILDING", "REVIEWING", storage_path, "my-topic", 1
        )

    calls = mock_run.call_args_list
    assert any(
        c
        == call(
            ["git", "add", "-A"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        for c in calls
    )
    assert any(
        c[0][0] == ["git", "commit", "-m", "feat: complete building stage"]
        and c[1].get("cwd") == str(tmp_path)
        and c[1].get("timeout") == 30
        for c in calls
    )


def test_run_transition_actions_git_nothing_to_commit(tmp_path):
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    flow = _make_commit_flow()

    def _mock_run(cmd, **kwargs):
        mock = MagicMock()
        if "commit" in cmd:
            mock.returncode = 1
            mock.stdout = "nothing to commit"
            mock.stderr = ""
        else:
            mock.returncode = 0
            mock.stdout = ""
            mock.stderr = ""
        return mock

    with patch("subprocess.run", side_effect=_mock_run):
        run_transition_actions(
            flow, "BUILDING", "REVIEWING", storage_path, "my-topic", 1
        )


def test_run_transition_actions_commit_gated_off_by_default(tmp_path):
    """Without an explicit opt-in (action auto_commit / app-setting), the commit action
    is gated OFF — no `git commit` runs, so changes stay in the working tree."""
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    flow = {
        "storage_path": "pathly/plans/{topic}/",
        "transition_actions": {
            "BUILDING->REVIEWING": [
                {"skill": "commit", "message": "feat: complete building stage"}
            ]
        },
    }
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_transition_actions(
            flow, "BUILDING", "REVIEWING", storage_path, "my-topic", 1
        )
    commit_calls = [
        c for c in mock_run.call_args_list if c[0][0][:2] == ["git", "commit"]
    ]
    assert commit_calls == []


def test_run_transition_actions_archive_artifacts(tmp_path):
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    feedback_dir = storage_path / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("failures", encoding="utf-8")
    (feedback_dir / "TEST_FAILURES.md").write_text("test failures", encoding="utf-8")

    flow = _make_archive_flow()
    run_transition_actions(flow, "RETRO", "DONE", storage_path, "my-topic", 1)

    artifacts_dir = (
        tmp_path / "pathly" / "pipeline-walkthrough" / "my-topic" / "artifacts"
    )
    assert (artifacts_dir / "REVIEW_FAILURES_conv1_attempt1.md").exists()
    assert (artifacts_dir / "TEST_FAILURES_conv1_attempt1.md").exists()


def test_run_transition_actions_archive_attempt_counter(tmp_path):
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    feedback_dir = storage_path / "feedback"
    feedback_dir.mkdir()
    (feedback_dir / "REVIEW_FAILURES.md").write_text("failures", encoding="utf-8")

    flow = _make_archive_flow()
    run_transition_actions(flow, "RETRO", "DONE", storage_path, "my-topic", 1)
    run_transition_actions(flow, "RETRO", "DONE", storage_path, "my-topic", 1)

    artifacts_dir = (
        tmp_path / "pathly" / "pipeline-walkthrough" / "my-topic" / "artifacts"
    )
    assert (artifacts_dir / "REVIEW_FAILURES_conv1_attempt1.md").exists()
    assert (artifacts_dir / "REVIEW_FAILURES_conv1_attempt2.md").exists()


def test_run_transition_actions_no_match(tmp_path):
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    flow = _make_commit_flow()
    run_transition_actions(flow, "STORMING", "PLANNING", storage_path, "my-topic", 1)


def test_run_transition_actions_wildcard(tmp_path):
    storage_path = tmp_path / "pathly" / "plans" / "my-topic"
    storage_path.mkdir(parents=True)
    flow = {
        "storage_path": "pathly/plans/{topic}/",
        "transition_actions": {
            "->REVIEWING": [{"skill": "commit", "message": "chore: to reviewing"}]
        },
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_transition_actions(
            flow, "BUILDING", "REVIEWING", storage_path, "my-topic", 1
        )

    assert mock_run.called


# ── write_state ───────────────────────────────────────────────────────────────


def test_write_state_creates_file(tmp_path):
    write_state(tmp_path, "BUILDING", {"feature": "x"})
    state_file = tmp_path / "STATE.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["current"] == "BUILDING"
    assert data["feature"] == "x"


def test_write_state_preserves_prior_fields(tmp_path):
    write_state(tmp_path, "REVIEWING", {"current_conversation": 2, "extra": "keep"})
    data = json.loads((tmp_path / "STATE.json").read_text(encoding="utf-8"))
    assert data["current"] == "REVIEWING"
    assert data["current_conversation"] == 2
    assert data["extra"] == "keep"


def test_write_state_creates_dir(tmp_path):
    nested = tmp_path / "nested" / "dir"
    write_state(nested, "BUILDING", {})
    assert (nested / "STATE.json").exists()


# ── append_event ──────────────────────────────────────────────────────────────


def test_append_event_creates_file(tmp_path):
    append_event(tmp_path, {"type": "A"})
    append_event(tmp_path, {"type": "B"})
    from pathly_orchestrator import db as _db

    conn = _db.get_db()
    project_root = str(tmp_path.parent.parent.parent)
    events = _db.read_events(conn, project_root, tmp_path.name)
    assert len(events) == 2
    for e in events:
        assert isinstance(e, dict)


def test_append_event_ts_injected(tmp_path):
    append_event(tmp_path, {"type": "TEST"})
    from pathly_orchestrator import db as _db

    conn = _db.get_db()
    project_root = str(tmp_path.parent.parent.parent)
    events = _db.read_events(conn, project_root, tmp_path.name)
    assert len(events) == 1
    assert "ts" in events[0]


def test_append_event_preserves_other_fields(tmp_path):
    append_event(
        tmp_path, {"type": "STATE_TRANSITION", "from": "BUILDING", "to": "REVIEWING"}
    )
    from pathly_orchestrator import db as _db

    conn = _db.get_db()
    project_root = str(tmp_path.parent.parent.parent)
    events = _db.read_events(conn, project_root, tmp_path.name)
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "STATE_TRANSITION"
    assert event["from"] == "BUILDING"
    assert event["to"] == "REVIEWING"
    assert "ts" in event
