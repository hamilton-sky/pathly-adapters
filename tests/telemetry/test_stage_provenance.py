"""Tests for runner/provenance.py — a MEASURED, server-side record of what a stage's
spawn actually changed on disk, as a companion to the agent-authored AGENT_DONE summary.

Real git repos and real subprocesses, same reasoning as command_gate's own tests: a
measurement whose whole value is "the server ran git itself" is not worth mocking away.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from pathly_orchestrator.runner.provenance import (
    capture_stage_provenance,
    record_stage_provenance,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


# ── capture_stage_provenance ────────────────────────────────────────────────────


def test_returns_none_outside_a_git_repo(tmp_path):
    assert capture_stage_provenance(str(tmp_path)) is None


def test_clean_worktree_reports_head_sha_and_no_diff(tmp_path):
    repo = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    info = capture_stage_provenance(str(repo))

    assert info == {"head_sha": head, "diff_stat": "", "files_changed": 0}


def test_a_modified_file_shows_up_in_the_diff(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "a.py").write_text("x = 2\ny = 3\n", encoding="utf-8")

    info = capture_stage_provenance(str(repo))

    assert info is not None
    assert info["files_changed"] == 1
    assert "a.py" in info["diff_stat"]


def test_untracked_files_count_too(tmp_path):
    """git diff HEAD alone misses this — a brand new file is the most common builder
    act, and untracked files never appear in `git diff`, only `git status`."""
    repo = _init_repo(tmp_path)
    (repo / "new_module.py").write_text("value = 1\n", encoding="utf-8")

    info = capture_stage_provenance(str(repo))

    assert info["files_changed"] == 1
    assert "new_module.py" in info["diff_stat"]


def test_own_storage_tree_is_exempt_from_the_count(tmp_path):
    """A run's own pathly/features (or legacy pathly/plans) bookkeeping is not code the
    builder touched — same exemption fsm/gates/scope.py already applies, and for the
    same reason (a fresh feature's own state file would otherwise inflate every count).
    """
    repo = _init_repo(tmp_path)
    (repo / "pathly" / "features" / "f").mkdir(parents=True)
    (repo / "pathly" / "features" / "f" / "STATE.json").write_text(
        "{}", encoding="utf-8"
    )
    (repo / "pathly" / "plans" / "g").mkdir(parents=True)
    (repo / "pathly" / "plans" / "g" / "STATE.json").write_text("{}", encoding="utf-8")

    info = capture_stage_provenance(str(repo))

    assert info["files_changed"] == 0
    assert "pathly/features" not in info["diff_stat"]
    assert "pathly/plans" not in info["diff_stat"]


def test_own_storage_exemption_does_not_hide_real_changes_alongside_it(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "pathly" / "features" / "f").mkdir(parents=True)
    (repo / "pathly" / "features" / "f" / "STATE.json").write_text(
        "{}", encoding="utf-8"
    )
    (repo / "real_change.py").write_text("value = 1\n", encoding="utf-8")

    info = capture_stage_provenance(str(repo))

    assert info["files_changed"] == 1
    assert "real_change.py" in info["diff_stat"]


def test_multiple_changed_files_are_all_counted(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "a.py").write_text("x = 99\n", encoding="utf-8")
    (repo / "b.py").write_text("y = 1\n", encoding="utf-8")
    _git(repo, "add", "b.py")  # staged-but-uncommitted counts too (diff HEAD)

    info = capture_stage_provenance(str(repo))

    assert info["files_changed"] == 2
    assert "a.py" in info["diff_stat"]
    assert "b.py" in info["diff_stat"]


def test_this_is_the_full_diff_from_head_not_isolated_to_one_stage(tmp_path):
    """Documented, deliberate scope: cumulative since the last commit, not a per-stage
    delta — the module's own docstring explains why that is the honest unit here."""
    repo = _init_repo(tmp_path)
    (repo / "stage_one.py").write_text("s1 = True\n", encoding="utf-8")
    after_stage_one = capture_stage_provenance(str(repo))

    (repo / "stage_two.py").write_text("s2 = True\n", encoding="utf-8")
    after_stage_two = capture_stage_provenance(str(repo))

    assert after_stage_one["files_changed"] == 1
    assert after_stage_two["files_changed"] == 2  # both stages' changes, cumulative
    assert (
        after_stage_one["head_sha"] == after_stage_two["head_sha"]
    )  # no commit happened


def test_git_failure_returns_none_not_a_raise(tmp_path):
    repo = _init_repo(tmp_path)
    with patch("subprocess.run", side_effect=OSError("git not found")):
        assert capture_stage_provenance(str(repo)) is None


def test_git_timeout_returns_none_not_a_raise(tmp_path):
    repo = _init_repo(tmp_path)
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=15),
    ):
        assert capture_stage_provenance(str(repo)) is None


# ── record_stage_provenance ──────────────────────────────────────────────────────


def _fake_state(
    project_root: str, flow: str = "team", topic: str = "f", state: str = "BUILDING"
):
    return MagicMock(
        project_root=project_root, flow=flow, topic=topic, current_state=state
    )


def test_record_writes_a_stage_provenance_event(tmp_path):
    from pathly_orchestrator import eventlog

    repo = _init_repo(tmp_path)
    (repo / "changed.py").write_text("z = 1\n", encoding="utf-8")
    storage = repo / "pathly" / "features" / "f"
    storage.mkdir(parents=True)

    with patch("pathly_orchestrator.runner.argv._storage_path", return_value=storage):
        record_stage_provenance(_fake_state(str(repo)), "run-abc")

    events = eventlog.read_events(str(storage))
    provenance = [e for e in events if e.get("type") == "STAGE_PROVENANCE"]
    assert len(provenance) == 1
    assert provenance[0]["run_id"] == "run-abc"
    assert provenance[0]["stage"] == "BUILDING"
    assert provenance[0]["files_changed"] == 1
    assert "changed.py" in provenance[0]["diff_stat"]
    assert provenance[0]["head_sha"]


def test_record_is_a_silent_noop_outside_git(tmp_path):
    """No repo → capture returns None → nothing written; must not raise either."""
    from pathly_orchestrator import eventlog

    storage = tmp_path / "pathly" / "features" / "f"
    storage.mkdir(parents=True)

    with patch("pathly_orchestrator.runner.argv._storage_path", return_value=storage):
        record_stage_provenance(_fake_state(str(tmp_path)), "run-abc")

    events = eventlog.read_events(str(storage))
    assert not any(e.get("type") == "STAGE_PROVENANCE" for e in events)


def test_record_never_raises_on_a_broken_storage_resolver(tmp_path):
    """Best-effort: a resolution failure must not break the terminal-result callback."""
    repo = _init_repo(tmp_path)
    with patch(
        "pathly_orchestrator.runner.argv._storage_path",
        side_effect=RuntimeError("boom"),
    ):
        record_stage_provenance(_fake_state(str(repo)), "run-abc")  # must not raise


# ── End to end through the real /runner/terminal/result route ────────────────────


def test_terminal_result_endpoint_records_provenance(tmp_path, monkeypatch):
    """Mirrors test_runner_terminal_result_fills_otel_and_invocation_tables — same
    endpoint, same fixture shape, asserting the NEW side effect lands alongside the
    existing otel span."""
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.eventlog import read_events
    from pathly_orchestrator.http_server import app, _rate_counters
    from pathly_orchestrator.supervisor import RunnerState, _lock, _registry
    from pathly_orchestrator.supervisor.registry import create_run, drop_run

    _rate_counters.clear()
    with _lock:
        _registry.clear()

    # The repo must NOT be tmp_path itself: conftest's _isolate_db fixture patches
    # Path.home() to tmp_path, so `.pathly/pathly.db` would land INSIDE the repo and
    # show up as an extra untracked path once get_db() runs.
    repo = _init_repo(tmp_path / "repo")
    (repo / "builder_output.py").write_text("done = True\n", encoding="utf-8")
    topic = "prov-feature"
    storage = repo / "pathly" / "plans" / topic
    storage.mkdir(parents=True)

    with _lock:
        st = RunnerState(
            topic=topic,
            flow="team",
            project_root=str(repo),
            model="m",
            timeout=60,
            run_id="run-prov-1",
            current_state="BUILDING",
            current_adapter="claude",
        )
        st.status = "running"
        _registry[topic] = st
    create_run("run-prov-1")

    app.config["TESTING"] = True
    try:
        with app.test_client() as c:
            r = c.post(
                "/runner/terminal/result",
                json={
                    "topic": topic,
                    "run_id": "run-prov-1",
                    "exit_code": 0,
                    "stdout_tail": "",
                    "wall_seconds": 2,
                },
            )
            assert r.status_code == 200

        events = read_events(str(storage))
        provenance = [e for e in events if e.get("type") == "STAGE_PROVENANCE"]
        assert len(provenance) == 1, events
        assert provenance[0]["run_id"] == "run-prov-1"
        assert provenance[0]["files_changed"] == 1
        assert "builder_output.py" in provenance[0]["diff_stat"]
    finally:
        drop_run("run-prov-1")
        with _lock:
            _registry.clear()
