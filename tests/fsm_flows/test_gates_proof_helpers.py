"""The shared helpers of the proof gates (``fsm/gates/_proof.py``, build-proof 04).

What each stage role may write (``stage_writes``), where a run's plan lives (``board_home``),
the ``SPAWN_WINDOW`` events since a stamp (``windows_since``), whether a window explains a
change (``explained``) and the ``floor.enabled`` switch. ``explained`` runs against a real
``git init`` repo under ``tmp_path``: it compares blobs git stored in snapshot trees.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pathly_orchestrator import eventlog
from pathly_orchestrator.fsm.gates import _proof
from pathly_orchestrator.proof import tree

PLAN = "pathly/features/demo/IMPLEMENTATION_PLAN.md"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
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
    _write(root, PLAN, "# Plan\n")
    _write(root, "pathly/features/demo/USER_STORIES.md", "# Stories\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _storage(root: Path) -> Path:
    return root / "pathly" / "features" / "demo"


# ── board_home ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "storage, home",
    [
        ("pathly/features/demo", "pathly/features/demo/"),
        ("pathly/features/demo/goals/add-export", "pathly/features/demo/"),
        ("pathly/project/goals/add-export", "pathly/project/goals/add-export/"),
        ("pathly/project", "pathly/project/"),
        ("pathly/plans/legacy", "pathly/plans/legacy/"),
    ],
)
def test_board_home(tmp_path, storage, home):
    assert _proof.board_home(tmp_path / "repo" / storage) == home
    assert _proof.board_home(str(tmp_path / "repo" / storage)) == home


# ── stage_writes ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "role, verify, review, plan, feedback",
    [
        ("builder", True, False, False, True),
        ("reviewer", False, True, False, True),
        ("planner", True, True, True, True),
    ],
)
def test_stage_writes_for_the_storage_files(
    tmp_path, role, verify, review, plan, feedback
):
    may = _proof.stage_writes(_storage(tmp_path / "repo"), role)
    assert may("pathly/features/demo/VERIFY.md") is verify
    assert may("pathly/features/demo/REVIEW.md") is review
    assert may(PLAN) is plan
    assert may("pathly/features/demo/feedback/X.md") is feedback


@pytest.mark.parametrize(
    "role", ["po", "planner", "architect", "designer", "retro", "Planner"]
)
def test_upstream_roles_may_write_the_plan_documents_only(tmp_path, role):
    may = _proof.stage_writes(_storage(tmp_path / "repo"), role)
    assert may(PLAN) is True
    assert may("pathly/features/demo/ARCHITECTURE_PROPOSAL.md") is True
    assert may("pathly/features/demo/notes/deep.md") is False
    assert may("pathly/features/other/IMPLEMENTATION_PLAN.md") is False
    assert may("src/app.py") is False


@pytest.mark.parametrize("role", ["builder", "reviewer", "tester", "", None])
def test_other_roles_may_not_write_the_plan(tmp_path, role):
    may = _proof.stage_writes(_storage(tmp_path / "repo"), role)
    assert may(PLAN) is False
    assert may("pathly/features/demo/USER_STORIES.md") is False
    assert may("src/app.py") is False
    # A file named like the feedback dir is not inside it.
    assert may("pathly/features/demo/feedback") is False


@pytest.mark.parametrize("role", ["builder", "reviewer", "tester", "planner", "", None])
def test_every_role_may_write_feedback_exports_and_tsbuildinfo(tmp_path, role):
    may = _proof.stage_writes(_storage(tmp_path / "repo"), role)
    assert may("pathly/features/demo/feedback/REVIEW_FAILURES.md") is True
    assert may("pathly/features/demo/feedback/nested/X.md") is True
    assert may("pathly/features/demo/STATE.json") is True
    assert may("pathly/features/other/EVENTS.jsonl") is True
    assert may("pathly/project/BOARD.json") is True
    assert may("studio/tsconfig.node.tsbuildinfo") is True
    assert may("src/STATE.json") is False
    assert may("pathly/features/other/feedback/X.md") is False


def test_a_goal_run_writes_its_own_dir_and_the_board_home(tmp_path):
    storage = tmp_path / "repo" / "pathly" / "features" / "demo" / "goals" / "g1"
    planner = _proof.stage_writes(storage, "planner")
    builder = _proof.stage_writes(storage, "builder")

    assert planner(PLAN) is True
    assert planner("pathly/features/demo/goals/g1/IMPLEMENTATION_PLAN.md") is True
    assert planner("pathly/features/demo/goals/other/PLAN.md") is False
    assert builder(PLAN) is False
    assert builder("pathly/features/demo/goals/g1/VERIFY.md") is True
    assert builder("pathly/features/demo/VERIFY.md") is False
    assert builder("pathly/features/demo/goals/g1/feedback/X.md") is True
    assert builder("pathly/features/demo/feedback/X.md") is False


# ── explained ────────────────────────────────────────────────────────────────


def _window(role: str, before: str, after: str) -> dict:
    return {"type": "SPAWN_WINDOW", "role": role, "before": before, "after": after}


def test_a_plan_file_left_as_a_planner_window_left_it_is_explained(repo):
    storage = _storage(repo)
    before = tree.snapshot(repo)
    _write(repo, PLAN, "# Plan\n\nAnswered by the planner.\n")
    after = tree.snapshot(repo)
    windows = [_window("planner", before, after)]

    now = tree.snapshot(repo)
    assert _proof.explained(repo, PLAN, now, windows, storage) is True

    _write(repo, PLAN, "# Plan\n\nRewritten by the builder.\n")
    later = tree.snapshot(repo)
    assert _proof.explained(repo, PLAN, later, windows, storage) is False


def test_a_window_whose_role_may_not_write_the_path_explains_nothing(repo):
    storage = _storage(repo)
    before = tree.snapshot(repo)
    _write(repo, PLAN, "# Plan\n\nEdited by the builder.\n")
    after = tree.snapshot(repo)

    now = tree.snapshot(repo)
    assert (
        _proof.explained(repo, PLAN, now, [_window("builder", before, after)], storage)
        is False
    )


def test_a_planner_window_that_left_the_file_alone_does_not_excuse_an_earlier_edit(
    repo,
):
    """The builder edits the plan, then a planner window runs without touching it."""
    storage = _storage(repo)
    _write(repo, PLAN, "# Plan\n\nEdited by the builder first.\n")
    before = tree.snapshot(repo)
    _write(repo, "pathly/features/demo/ARCHITECTURE_PROPOSAL.md", "# Arch\n")
    after = tree.snapshot(repo)

    now = tree.snapshot(repo)
    windows = [_window("planner", before, after)]
    assert _proof.explained(repo, PLAN, now, windows, storage) is False
    assert (
        _proof.explained(
            repo, "pathly/features/demo/ARCHITECTURE_PROPOSAL.md", now, windows, storage
        )
        is True
    )


def test_a_deletion_matches_a_deletion(repo):
    storage = _storage(repo)
    stories = "pathly/features/demo/USER_STORIES.md"
    before = tree.snapshot(repo)
    (repo / stories).unlink()
    after = tree.snapshot(repo)
    windows = [_window("po", before, after)]

    now = tree.snapshot(repo)
    assert _proof.explained(repo, stories, now, windows, storage) is True

    _write(repo, stories, "# Stories, back again\n")
    restored = tree.snapshot(repo)
    assert _proof.explained(repo, stories, restored, windows, storage) is False


def test_no_tree_or_no_window_explains_nothing(repo):
    storage = _storage(repo)
    before = tree.snapshot(repo)
    _write(repo, PLAN, "# Plan v2\n")
    after = tree.snapshot(repo)
    windows = [_window("planner", before, after)]

    assert _proof.explained(repo, PLAN, None, windows, storage) is False
    assert _proof.explained(repo, PLAN, after, [], storage) is False
    assert (
        _proof.explained(repo, PLAN, after, [_window("planner", None, after)], storage)
        is False
    )


# ── windows_since ────────────────────────────────────────────────────────────


def _append(storage: Path, event: dict) -> None:
    eventlog.append_event(str(storage), event, create_dir=False)


def test_windows_since_compares_parsed_times_oldest_first(tmp_path):
    storage = _storage(tmp_path / "repo")
    # 12:00:00.25 UTC, written as isoformat() with a +02:00 offset: as strings, "...T12:00:01Z"
    # sorts BEFORE "...T14:00:00.250000+02:00", so a string compare would drop it.
    since = datetime(
        2026, 10, 14, 14, 0, 0, 250000, tzinfo=timezone(timedelta(hours=2))
    ).isoformat()
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "planner", "ts": "2026-10-14T11:59:59Z"},
    )
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "builder", "ts": "2026-10-14T12:00:00Z"},
    )
    _append(
        storage,
        {"type": "GATE_PASSED", "gate": "command_gate", "ts": "2026-10-14T12:00:01Z"},
    )
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "reviewer", "ts": "2026-10-14T12:00:02Z"},
    )
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "builder", "ts": "2026-10-14T12:00:01Z"},
    )

    kept = _proof.windows_since(storage, since)

    # The event `ts` has whole seconds, so a window stamped in since's own second is kept;
    # one a second or more earlier is dropped.
    assert [(w["role"], w["ts"]) for w in kept] == [
        ("builder", "2026-10-14T12:00:00Z"),
        ("builder", "2026-10-14T12:00:01Z"),
        ("reviewer", "2026-10-14T12:00:02Z"),
    ]
    assert all(w["type"] == "SPAWN_WINDOW" for w in kept)


def test_windows_since_filters_by_role_and_keeps_all_without_since(tmp_path):
    storage = _storage(tmp_path / "repo")
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "planner", "ts": "2026-10-14T11:00:00Z"},
    )
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "reviewer", "ts": "2026-10-14T12:00:00Z"},
    )
    _append(
        storage,
        {"type": "SPAWN_WINDOW", "role": "builder", "ts": "2026-10-14T13:00:00Z"},
    )

    assert [w["role"] for w in _proof.windows_since(storage)] == [
        "planner",
        "reviewer",
        "builder",
    ]
    assert [w["role"] for w in _proof.windows_since(storage, roles=["reviewer"])] == [
        "reviewer"
    ]
    assert [w["role"] for w in _proof.windows_since(storage, roles="builder")] == [
        "builder"
    ]
    assert (
        _proof.windows_since(storage, "2026-10-14T12:30:00+00:00", roles={"planner"})
        == []
    )


def test_windows_since_rejects_a_since_that_is_not_a_time(tmp_path):
    with pytest.raises(ValueError, match="since"):
        _proof.windows_since(_storage(tmp_path / "repo"), "yesterday")


# ── floor_enabled ────────────────────────────────────────────────────────────


def _set(value: str) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "floor.enabled", value)


def test_floor_enabled_when_the_setting_is_unset():
    assert _proof.floor_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "off", "False", " OFF "])
def test_floor_disabled_by_false_zero_or_off(value):
    _set(value)
    assert _proof.floor_enabled() is False


@pytest.mark.parametrize("value", ["true", "1", "on", "yes"])
def test_floor_enabled_by_anything_else(value):
    _set(value)
    assert _proof.floor_enabled() is True
