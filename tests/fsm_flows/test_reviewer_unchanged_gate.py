"""``reviewer_unchanged`` fails the review stage when a reviewer spawn changed files (build-proof 09).

The gate reads the ``SPAWN_WINDOW`` events of the ``reviewer`` role since the run last entered
REVIEWING: a window that moved ``HEAD`` or changed a path other than ``REVIEW.md`` and feedback
files blocks ``REVIEWING->TESTING`` and ``REVIEWING->BUILDING`` with ``REVIEWER_CHANGED_FILES.md``
(routed to ``human``). Builder fix rounds also run inside REVIEWING, so only reviewer windows
count, and a window already reported is not reported again. Every case records its windows with
the real ``spawn_window.observe`` in a ``git init`` repo and runs the packaged flow's real gates.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import pathly_orchestrator.fsm_ops as fsm_ops
from pathly_orchestrator import eventlog
from pathly_orchestrator.fsm import route_feedback, run_gates
from pathly_orchestrator.fsm.gates import _proof
from pathly_orchestrator.fsm_ops import complete_stage
from pathly_orchestrator.proof import tree
from pathly_orchestrator.supervisor import spawn_window

FEATURE = "pathly/features/demo"
REVIEW = FEATURE + "/REVIEW.md"
REVIEW_FAILURES = FEATURE + "/feedback/REVIEW_FAILURES.md"
PASS = "RESULT: PASS\nReviewed: clean.\n"
FAILED = {
    "gate_failed": "reviewer_unchanged",
    "feedback_file": "REVIEWER_CHANGED_FILES.md",
}


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _write(root: Path, rel: str, text: str = "changed\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _write(root, "src/app.py", "x = 1\n")
    _write(root, "src/other.py", "y = 2\n")
    _write(root, FEATURE + "/IMPLEMENTATION_PLAN.md", "# Plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _storage(repo: Path) -> Path:
    return repo / FEATURE


def _load(name: str) -> dict:
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{name}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


@pytest.fixture
def flow() -> dict:
    return _load("team-build")


def _enter_reviewing(repo: Path, flow: dict, ts: str | None = None) -> None:
    event = {"type": "STATE_TRANSITION", "from": "BUILDING", "to": "REVIEWING"}
    if ts is not None:
        event["ts"] = ts
    eventlog.append_event(str(_storage(repo)), event, flow=flow)


def _spawn(repo: Path, flow: dict, role: str, run_id: str, work) -> None:
    """Run ``work()`` as a spawn of ``role``, recording its SPAWN_WINDOW."""
    state = SimpleNamespace(
        project_root=str(repo),
        topic="demo",
        storage_path=str(_storage(repo)),
        current_state="REVIEWING",
    )
    spawn_window.observe(state, flow, role, run_id, work)


def _gate(repo: Path, flow: dict, nxt: str = "TESTING"):
    return run_gates(
        flow, "REVIEWING", nxt, _storage(repo), "demo", 1, feature_scope="demo"
    )


def _feedback(repo: Path) -> Path:
    return _storage(repo) / "feedback" / "REVIEWER_CHANGED_FILES.md"


def _events(repo: Path, kind: str) -> list[dict]:
    return [e for e in eventlog.read_events(str(_storage(repo))) if e["type"] == kind]


def _edit(repo: Path, rel: str, text: str = "changed\n"):
    """A spawn body that writes one file."""
    return lambda: _write(repo, rel, text)


def _commit(repo: Path):
    """A spawn body that commits the working tree."""

    def work():
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "by the reviewer")

    return work


def _reviewer_writes_review(repo: Path):
    def work():
        _write(repo, REVIEW, PASS)
        _write(repo, REVIEW_FAILURES, "- [IMPL] nothing wrong.\n")

    return work


# ── the flows carry the gate ─────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_team_flows_run_the_gate_last_on_both_review_edges(name):
    flow = _load(name)
    for edge in ("REVIEWING->TESTING", "REVIEWING->BUILDING"):
        last = flow["gates"][edge][-1]
        assert last == {
            "type": "reviewer_unchanged",
            "on_fail": "REVIEWER_CHANGED_FILES.md",
        }, edge
    assert flow["gates"]["REVIEWING->TESTING"][0]["type"] == "verify_gate"
    assert [g["type"] for g in flow["gates"]["REVIEWING->BUILDING"]] == [
        "reviewer_unchanged"
    ]


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_team_flows_route_the_file_to_a_human_right_after_blocked_on_human(name):
    flow = _load(name)
    assert flow["feedback_routing"]["REVIEWER_CHANGED_FILES"] == "human"
    priority = flow["feedback_priority"]
    assert priority.index("REVIEWER_CHANGED_FILES") == (
        priority.index("BLOCKED_ON_HUMAN") + 1
    )


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_reviewing_prompt_says_to_change_nothing_and_not_commit(name):
    from pathly_orchestrator.fsm_compose_responses import _exit_requirement

    requirement = _exit_requirement(_load(name), "REVIEWING") or ""

    assert requirement.count("REVIEW.md") >= 2  # the verify_gate line and this one
    assert "do not commit" in requirement.lower()
    assert requirement.lower().count("do not commit") == 1  # two edges, one line


# ── a reviewer that changed something ────────────────────────────────────────


def test_a_reviewer_window_that_changed_a_source_file_blocks_review_to_testing(
    repo, flow
):
    _enter_reviewing(repo, flow)

    def work():
        _write(repo, REVIEW, PASS)
        _write(repo, "src/app.py", "x = 2\n")
        _write(repo, "src/new.py", "z = 3\n")
        (repo / "src/other.py").unlink()

    _spawn(repo, flow, "reviewer", "demo-1-a", work)

    assert _gate(repo, flow) == FAILED
    text = _feedback(repo).read_text(encoding="utf-8")
    for line in ("M src/app.py", "A src/new.py", "D src/other.py"):
        assert line in text
    assert "pathly/features/demo/REVIEW.md" not in text
    assert "judge" in text.lower()
    (event,) = _events(repo, "GATE_FAILED")
    assert event["gate"] == "reviewer_unchanged"
    assert event["transition"] == "REVIEWING->TESTING"
    assert event["run_ids"] == ["demo-1-a"]
    routed = route_feedback(flow, _storage(repo))
    assert routed["file"] == "REVIEWER_CHANGED_FILES.md"
    assert routed["target_agent"] == "human"


def test_a_reviewer_window_that_only_wrote_its_own_files_passes(repo, flow):
    _enter_reviewing(repo, flow)
    _spawn(repo, flow, "reviewer", "demo-1-a", _reviewer_writes_review(repo))

    assert _gate(repo, flow) is None
    assert _gate(repo, flow, "BUILDING") is None
    assert not _feedback(repo).exists()
    assert _events(repo, "GATE_FAILED") == []


def test_a_reviewer_window_with_a_new_commit_blocks(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    before = _git(repo, "rev-parse", "HEAD")

    _spawn(repo, flow, "reviewer", "demo-1-a", _commit(repo))
    after = _git(repo, "rev-parse", "HEAD")
    assert before != after

    assert _gate(repo, flow) == FAILED
    text = _feedback(repo).read_text(encoding="utf-8")
    assert "HEAD moved from %s to %s" % (before, after) in text
    assert "the reviewer committed" in text


def test_a_builder_window_inside_reviewing_that_changed_code_passes(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)

    _spawn(repo, flow, "builder", "demo-fb1-b", _edit(repo, "src/app.py", "x = 3\n"))

    assert _gate(repo, flow) is None
    assert _gate(repo, flow, "BUILDING") is None
    assert not _feedback(repo).exists()


def test_only_the_reviewer_windows_are_blamed_among_several(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "builder", "demo-fb1-b", _edit(repo, "src/app.py"))
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/other.py", "q\n"))

    assert _gate(repo, flow) == FAILED
    text = _feedback(repo).read_text(encoding="utf-8")
    assert "M src/other.py" in text
    assert "src/app.py" not in text


def test_after_the_file_is_removed_the_same_window_is_not_reported_again(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/app.py"))
    assert _gate(repo, flow) == FAILED

    _feedback(repo).unlink()  # a human kept or reverted the change and resumed

    assert _gate(repo, flow) is None
    assert _gate(repo, flow, "BUILDING") is None
    assert not _feedback(repo).exists()
    assert len(_events(repo, "GATE_FAILED")) == 1


def test_a_later_reviewer_window_is_still_reported_and_only_it_is_named(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/app.py"))
    assert _gate(repo, flow) == FAILED
    _feedback(repo).unlink()

    _spawn(repo, flow, "reviewer", "demo-2-c", _edit(repo, "src/other.py", "q\n"))

    assert _gate(repo, flow) == FAILED
    text = _feedback(repo).read_text(encoding="utf-8")
    assert "src/other.py" in text
    assert "src/app.py" not in text
    assert [e["run_ids"] for e in _events(repo, "GATE_FAILED")] == [
        ["demo-1-a"],
        ["demo-2-c"],
    ]


def test_review_to_building_is_blocked_the_same_way(repo, flow):
    _enter_reviewing(repo, flow)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/app.py"))

    assert _gate(repo, flow, "BUILDING") == FAILED
    assert "M src/app.py" in _feedback(repo).read_text(encoding="utf-8")
    (event,) = _events(repo, "GATE_FAILED")
    assert event["transition"] == "REVIEWING->BUILDING"
    assert route_feedback(flow, _storage(repo))["target_agent"] == "human"


# ── which windows count ──────────────────────────────────────────────────────


def test_a_window_from_before_the_last_entry_into_reviewing_is_not_judged(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/app.py"))
    later = datetime.now(timezone.utc) + timedelta(seconds=30)
    _enter_reviewing(repo, flow, later.strftime("%Y-%m-%dT%H:%M:%SZ"))

    assert _gate(repo, flow) is None


def test_no_reviewer_window_passes_and_says_why(repo, flow):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "builder", "demo-fb1-b", _edit(repo, "src/app.py"))

    assert _gate(repo, flow) is None
    (skipped,) = [
        e for e in _events(repo, "GATE_SKIPPED") if e["gate"] == "reviewer_unchanged"
    ]
    assert skipped["reason"] == "no_reviewer_window"


def test_outside_a_git_repo_there_is_no_window_and_the_gate_passes(tmp_path, flow):
    plain = tmp_path / "plain"
    _write(plain, REVIEW, PASS)
    _enter_reviewing(plain, flow)
    _spawn(plain, flow, "reviewer", "demo-1-a", _edit(plain, "src/app.py"))

    assert _gate(plain, flow) is None
    reasons = [e["reason"] for e in _events(plain, "GATE_SKIPPED")]
    assert "no_reviewer_window" in reasons


def test_unreadable_windows_fail_open(repo, flow, monkeypatch):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/app.py"))

    def boom(*args, **kwargs):
        raise RuntimeError("db is down")

    monkeypatch.setattr(_proof, "windows_since", boom)

    assert _gate(repo, flow) is None
    reasons = [e["reason"] for e in _events(repo, "GATE_SKIPPED")]
    assert "windows_unreadable" in reasons


def test_a_tree_diff_git_cannot_make_fails_open_but_a_moved_head_still_blocks(
    repo, flow, monkeypatch
):
    _enter_reviewing(repo, flow)
    _write(repo, REVIEW, PASS)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, "src/app.py"))
    monkeypatch.setattr(tree, "changes_or_none", lambda *a, **k: None)

    assert _gate(repo, flow) is None
    reasons = [e["reason"] for e in _events(repo, "GATE_SKIPPED")]
    assert "git_diff_failed" in reasons

    _spawn(repo, flow, "reviewer", "demo-2-c", _commit(repo))
    assert _gate(repo, flow) == FAILED


# ── through the real complete_stage ──────────────────────────────────────────


def test_complete_stage_parks_on_a_human_and_resumes_once_the_file_is_removed(
    repo, flow, monkeypatch
):
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: flow)
    monkeypatch.setattr(
        fsm_ops, "build_prompt", lambda *args, **kwargs: f"instructions for {args[1]}"
    )
    eventlog.write_state(str(_storage(repo)), {"current": "REVIEWING"}, flow)
    _enter_reviewing(repo, flow)
    _spawn(repo, flow, "reviewer", "demo-1-a", _edit(repo, REVIEW, PASS))
    _spawn(repo, flow, "reviewer", "demo-1-b", _edit(repo, "src/app.py"))
    payload = {"flow": "team-build", "topic": "demo", "project_root": str(repo)}

    parked = complete_stage(payload)

    assert parked["blocked"] is True
    assert parked["target_agent"] == "human"
    assert parked["decision"] == "escalate"
    assert parked["file"] == "REVIEWER_CHANGED_FILES.md"
    assert parked["current_state"] == "REVIEWING"
    assert "M src/app.py" in parked["instructions"]

    _feedback(repo).unlink()
    resumed = complete_stage(payload)

    assert resumed.get("next_state") == "TESTING"
