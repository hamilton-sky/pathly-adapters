"""Tests for supervisor/goal_verify.py — ground truth for the loop executor's DAG.

The loop executor decides success from each task's own self-reported outcome
(scheduler._outcome_is_failure) with no equivalent of the FSM path's command_gate — a
goal could drain every task "successfully" over code that does not build. These tests
cover the fix: verify_clean_drain reuses fsm.gates.command.check_command_gate against
verify.build / verify.test once the DAG reports an unambiguous clean drain, and turns a
failure into the same {"error": ...} shape goals.py's on_done already treats as failed.

Real subprocesses, same reasoning as test_command_gate.py: a check whose whole value is
"it actually ran the command" is not worth testing against a mock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pathly_orchestrator.supervisor.goal_verify import (
    post_gate_failure_escalation,
    verify_clean_drain,
    verify_goal_completion,
)


def _py(code: str) -> str:
    return json.dumps([sys.executable, "-c", code])


def _set_verify(key: str, command: str) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), f"verify.{key}", command)


def _goal_dir(tmp_path: Path) -> Path:
    d = tmp_path / "pathly" / "features" / "f" / "goals" / "g"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── verify_goal_completion ────────────────────────────────────────────────────


def test_unconfigured_is_fail_open(tmp_path):
    """No verify.build / verify.test configured — inert, same contract as command_gate."""
    assert verify_goal_completion(str(_goal_dir(tmp_path))) is None


def test_passing_build_and_test_returns_none(tmp_path):
    _set_verify("build", _py("raise SystemExit(0)"))
    _set_verify("test", _py("raise SystemExit(0)"))
    assert verify_goal_completion(str(_goal_dir(tmp_path))) is None


def test_failing_build_is_reported_before_test_even_runs(tmp_path):
    """build is checked first — mirrors team.flow.yaml's BUILDING gate preceding TESTING."""
    marker = tmp_path / "test-ran"
    _set_verify("build", _py("raise SystemExit(1)"))
    _set_verify("test", _py(f"open(r'{marker}', 'w').close()"))

    result = verify_goal_completion(str(_goal_dir(tmp_path)))

    assert result == {
        "gate": "build",
        "reason": result["reason"],
        "feedback_file": result["feedback_file"],
    }
    assert not marker.exists(), "test command ran even though build already failed"


def test_failing_test_is_reported_when_build_passes(tmp_path):
    _set_verify("build", _py("raise SystemExit(0)"))
    _set_verify("test", _py("print('2 failed'); raise SystemExit(1)"))

    result = verify_goal_completion(str(_goal_dir(tmp_path)))

    assert result["gate"] == "test"
    assert "2 failed" in result["reason"]


def test_feedback_file_is_readable_at_the_reported_path(tmp_path):
    goal_dir = _goal_dir(tmp_path)
    _set_verify(
        "build", _py("print('undefined reference to foo'); raise SystemExit(2)")
    )

    result = verify_goal_completion(str(goal_dir))

    on_disk = Path(result["feedback_file"]).read_text(encoding="utf-8")
    assert "undefined reference to foo" in on_disk
    assert on_disk == result["reason"]


# ── verify_clean_drain: skip conditions ───────────────────────────────────────


def test_skips_when_goal_dir_is_none(tmp_path):
    _set_verify("build", _py("raise SystemExit(1)"))
    res = {"completed": ["t1"], "failed": [], "blocked": [], "deadlocked": []}

    verify_clean_drain(res, None, "feature", "f", "goal-1")

    assert "error" not in res


def test_skips_when_nothing_completed(tmp_path):
    """An aborted-before-anything-ran drain has nothing to verify."""
    _set_verify("build", _py("raise SystemExit(1)"))
    res = {"completed": [], "failed": [], "blocked": [], "deadlocked": []}

    verify_clean_drain(res, str(_goal_dir(tmp_path)), "feature", "f", "goal-1")

    assert "error" not in res


def test_skips_when_any_task_failed():
    """The scheduler's own failure already explains itself — don't pile on a gate verdict."""
    res = {"completed": ["t1"], "failed": ["t2"], "blocked": [], "deadlocked": []}
    verify_clean_drain(res, "/does/not/matter", "feature", "f", "goal-1")
    assert "error" not in res


def test_skips_when_anything_blocked_or_deadlocked():
    for key in ("blocked", "deadlocked"):
        res = {"completed": ["t1"], "failed": [], "blocked": [], "deadlocked": []}
        res[key] = ["t2"]
        verify_clean_drain(res, "/does/not/matter", "feature", "f", "goal-1")
        assert "error" not in res


# ── verify_clean_drain: the actual gate ───────────────────────────────────────


def test_clean_drain_with_passing_verify_reports_no_error(tmp_path):
    _set_verify("build", _py("raise SystemExit(0)"))
    res = {"completed": ["t1", "t2"], "failed": [], "blocked": [], "deadlocked": []}

    verify_clean_drain(res, str(_goal_dir(tmp_path)), "feature", "f", "goal-1")

    assert "error" not in res


def test_clean_drain_with_failing_verify_sets_error_like_a_failed_run(tmp_path):
    """This is the whole point: every task said success, but res still ends up looking
    like on_done's existing failure branch (goals.py checks res.get('error'))."""
    _set_verify("build", _py("print('link error'); raise SystemExit(1)"))
    res = {"completed": ["t1", "t2"], "failed": [], "blocked": [], "deadlocked": []}

    verify_clean_drain(res, str(_goal_dir(tmp_path)), "feature", "f", "goal-1")

    assert res["gate_failed"] == "build"
    assert "verify.build failed" in res["error"]


def test_a_lying_task_cannot_pass_the_goal_gate(tmp_path):
    """Every task reports success (nothing failed/blocked) but the code does not build —
    exactly the hole this closes."""
    _set_verify("build", _py("raise SystemExit(1)"))
    res = {"completed": ["t1"], "failed": [], "blocked": [], "deadlocked": []}

    verify_clean_drain(res, str(_goal_dir(tmp_path)), "feature", "f", "goal-1")

    assert "error" in res


# ── escalation ─────────────────────────────────────────────────────────────────


def test_gate_failure_posts_an_answerable_escalation(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_active_escalations

    _set_verify("test", _py("print('assertion failed'); raise SystemExit(1)"))
    goal_dir = _goal_dir(tmp_path)
    gate_failure = verify_goal_completion(str(goal_dir))
    assert gate_failure is not None

    post_gate_failure_escalation("feature", "f", "goal-1", gate_failure)

    conn = get_db()
    escalations = get_active_escalations(conn, boards=["feature"], scopes=["f"])
    assert any("verify.test" in e["text"] for e in escalations)
    assert any("assertion failed" in e["text"] for e in escalations)
    assert all(
        e.get("goal_id") == "goal-1" for e in escalations if "verify.test" in e["text"]
    )


def test_escalation_posting_never_raises_on_a_bad_db(monkeypatch):
    """Best-effort: a broken escalation post must not break the goal-run result."""
    import pathly_orchestrator.db.connection as conn_mod

    def _boom():
        raise RuntimeError("db is down")

    monkeypatch.setattr(conn_mod, "get_db", _boom)

    post_gate_failure_escalation(
        "feature", "f", "goal-1", {"gate": "build", "reason": "x", "feedback_file": "y"}
    )  # must not raise
