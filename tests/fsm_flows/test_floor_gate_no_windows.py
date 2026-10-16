"""``floor_gate`` in a run that recorded no spawn windows (build-proof 17).

Only the supervisor records a ``SPAWN_WINDOW``, so an interactive ``/pathly`` run has none. There
a plan file another role wrote (the reviewer's ``REVIEW.md``, a planner's edit) cannot be
attributed, and the gate must not blame it on the builder: a path some role may write is excused
and ``FLOOR_CHECKED`` carries a note. Every other category is judged as before, a path no role may
write is still a ``plan-edit``, and once a window exists the windows decide again.

Every case drives the real ``next_action`` and ``complete_stage`` over ``team-build`` in a
``git init`` project, writing files directly (``_write``) so that the run records no window; only
the last case records one with ``_as``.
"""

from __future__ import annotations

import pytest
from review_packet_support import (
    FEATURE,
    _args,
    _as,
    _claim,
    _enter_building,
    _git,
    _storage,
    _write,
    flow,
    repo,
)

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms_tasks import complete_task
from pathly_orchestrator.fsm.gates import _proof

TESTS = "tests/test_calc.py"
STORIES = FEATURE + "/USER_STORIES.md"
REVIEW = FEATURE + "/REVIEW.md"
NESTED = FEATURE + "/notes/NOTES.md"
CLEAN = "def test_calc():\n    assert 1 + 1 == 2\n"
FEEDBACK = "FLOOR_FAILURES.md"
NO_WINDOWS = "no spawn windows"
UNREADABLE = "spawn windows unreadable"


@pytest.fixture
def proj(repo):
    """The shared project plus a committed test file, plan document and passing review."""
    _write(repo, TESTS, CLEAN)
    _write(repo, STORIES, "# Stories\n- one\n")
    _write(repo, REVIEW, "RESULT: PASS\nBaseline.\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "tests, stories and review")
    return repo


def _complete(repo) -> dict:
    return fsm_ops.complete_stage(_args(repo))


def _events(repo, kind: str) -> list[dict]:
    return [e for e in eventlog.read_events(str(_storage(repo))) if e["type"] == kind]


def _feedback_path(repo):
    return _storage(repo) / "feedback" / FEEDBACK


def _notes(repo, text: str) -> list[str]:
    """The warnings of the last ``FLOOR_CHECKED`` that carry ``text``."""
    return [w for w in _events(repo, "FLOOR_CHECKED")[-1]["warnings"] if text in w]


def _reviewing(repo, flow, build=None) -> str:
    """Build, then advance to REVIEWING with the task still open. Returns the task id."""
    _enter_building(repo, flow)
    task_id = _claim()
    if build is None:
        _write(repo, "src/app.py", "x = 2\ny = 2\n")
    else:
        build()
    moved = _complete(repo)
    assert moved.get("next_state") == "REVIEWING", moved
    return task_id


def _assert_passes_with_the_note(repo, task_id: str) -> None:
    complete_task(get_db(), task_id)

    moved = _complete(repo)

    assert moved.get("next_state") == "TESTING", moved
    assert not _feedback_path(repo).exists()
    assert not [e for e in _events(repo, "GATE_FAILED") if e["gate"] == "floor_gate"]
    assert len(_notes(repo, NO_WINDOWS)) == 1, _events(repo, "FLOOR_CHECKED")
    assert not _events(repo, "SPAWN_WINDOW")


def _assert_blocked(repo, task_id: str, finding: str) -> str:
    complete_task(get_db(), task_id)

    blocked = _complete(repo)

    assert blocked.get("blocked") is True, blocked
    assert blocked["target_agent"] == "builder"
    assert blocked["file"] == FEEDBACK
    text = _feedback_path(repo).read_text(encoding="utf-8")
    assert finding in text, text
    assert eventlog.read_state(str(_storage(repo)))["current"] == "REVIEWING"
    failed = [e for e in _events(repo, "GATE_FAILED") if e["gate"] == "floor_gate"]
    assert failed[-1]["transition"] == "REVIEWING->TESTING"
    return text


def test_a_review_written_with_no_windows_is_not_a_plan_edit(proj, flow):
    task_id = _reviewing(proj, flow)
    _write(proj, REVIEW, "RESULT: PASS\nClean.\n")

    _assert_passes_with_the_note(proj, task_id)


def test_a_plan_document_edited_with_no_windows_is_not_a_plan_edit(proj, flow):
    task_id = _reviewing(proj, flow)
    _write(proj, STORIES, "# Stories\n- one\n- two\n")

    _assert_passes_with_the_note(proj, task_id)


def test_the_no_windows_note_is_added_once_for_several_plan_files(proj, flow):
    task_id = _reviewing(proj, flow)
    _write(proj, REVIEW, "RESULT: PASS\nClean.\n")
    _write(proj, STORIES, "# Stories\n- one\n- two\n")

    _assert_passes_with_the_note(proj, task_id)


def test_a_deleted_test_is_still_blocked_with_no_windows(proj, flow):
    task_id = _reviewing(proj, flow)
    (proj / TESTS).unlink()

    text = _assert_blocked(proj, task_id, "test-delete: %s" % TESTS)

    assert "plan-edit" not in text


def test_a_file_no_role_may_write_is_a_plan_edit_with_no_windows(proj, flow):
    task_id = _reviewing(proj, flow)
    _write(proj, NESTED, "# Notes\n")

    _assert_blocked(proj, task_id, "plan-edit: %s" % NESTED)

    assert not _events(proj, "SPAWN_WINDOW")
    # Nothing was excused, so the note about plan files a role may write is not added.
    assert _notes(proj, NO_WINDOWS) == []


def test_unreadable_windows_excuse_a_plan_file_with_their_own_note(
    proj, flow, monkeypatch
):
    def broken(*_args, **_kwargs):
        raise RuntimeError("db is gone")

    task_id = _reviewing(proj, flow)
    monkeypatch.setattr(_proof, "windows_since", broken)
    _write(proj, REVIEW, "RESULT: PASS\nClean.\n")
    complete_task(get_db(), task_id)

    moved = _complete(proj)

    assert moved.get("next_state") == "TESTING", moved
    assert not _feedback_path(proj).exists()
    assert len(_notes(proj, UNREADABLE)) == 1, _events(proj, "FLOOR_CHECKED")
    assert _notes(proj, NO_WINDOWS) == []


def test_unreadable_windows_still_block_a_file_no_role_may_write(
    proj, flow, monkeypatch
):
    def broken(*_args, **_kwargs):
        raise RuntimeError("db is gone")

    task_id = _reviewing(proj, flow)
    monkeypatch.setattr(_proof, "windows_since", broken)
    _write(proj, NESTED, "# Notes\n")

    _assert_blocked(proj, task_id, "plan-edit: %s" % NESTED)

    assert _notes(proj, UNREADABLE) == []


def test_a_plan_edit_outside_any_window_is_blocked_once_a_window_exists(proj, flow):
    def build():
        _as(
            proj,
            flow,
            "builder",
            "BUILDING",
            lambda: _write(proj, "src/app.py", "x = 2\ny = 2\n"),
        )

    task_id = _reviewing(proj, flow, build)
    assert len(_events(proj, "SPAWN_WINDOW")) == 1
    _write(proj, STORIES, "# Stories\n- one\n- two\n")

    _assert_blocked(proj, task_id, "plan-edit: %s" % STORIES)

    assert _notes(proj, NO_WINDOWS) == []
