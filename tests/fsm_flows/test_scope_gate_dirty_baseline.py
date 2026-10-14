"""``scope_gate`` judges a path by its content, not by whether it was dirty at the baseline.

build-proof 08, review round 1. In a default headless ``team`` run nothing commits the plan
before BUILDING (``pathly.auto_commit`` is off), so ``git status`` names it, or all of
``pathly/``, in ``build_baseline.preexisting_dirty``. A builder edit to it must still fail: a
path dirty at the baseline counts as changed when its blob now differs from the first
``SPAWN_WINDOW``'s ``before`` tree since the build began. Also here: only a task posted before
the build began, and not by a builder, declares scope; and when the windows cannot be read, an
undeclared file no window could explain still fails. Every case runs the real gate in a
``git init`` repo under ``tmp_path`` against the isolated test DB.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pathly_orchestrator import eventlog
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.fsm import run_gates
from pathly_orchestrator.fsm.gates import _proof
from pathly_orchestrator.proof import tree

FEATURE = "pathly/features/demo"
STORIES = FEATURE + "/USER_STORIES.md"
PLAN = FEATURE + "/IMPLEMENTATION_PLAN.md"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return done.stdout


def _write(root: Path, rel: str, text: str = "changed\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Code committed; the plan written by PLANNING and never committed (the default run)."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _write(root, "src/app.py", "x = 1\n")
    _write(root, "src/other.py", "y = 2\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    _write(root, PLAN, "# Plan\n\n**File:** `src/app.py`\n")
    _write(root, STORIES, "# Stories\n")
    return root


def _storage(repo: Path) -> Path:
    return repo / FEATURE


def _flow() -> dict:
    gate = {
        "type": "scope_gate",
        "scope_file": "IMPLEMENTATION_PLAN.md",
        "on_fail": "SCOPE_VIOLATION.md",
    }
    return {
        "flow": "scope-test",
        "states": ["BUILDING", "REVIEWING", "DONE"],
        "transitions": {"BUILDING": ["REVIEWING"], "REVIEWING": ["DONE"], "DONE": []},
        "feedback_routing": {"SCOPE_VIOLATION": "builder"},
        "gates": {"BUILDING->REVIEWING": [gate]},
    }


def _start_build(repo: Path, flow: dict) -> list[str]:
    """Stamp ``build_baseline`` as ``fsm_ops.next_action`` does: ``git status`` lines as is."""
    status = _git(repo, "status", "--porcelain=v1")
    dirty = sorted({line[3:].strip() for line in status.splitlines() if line.strip()})
    baseline = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "preexisting_dirty": dirty,
    }
    eventlog.write_state(
        str(_storage(repo)), {"current": "BUILDING", "build_baseline": baseline}, flow
    )
    return dirty


def _post_task(files, author_role=None) -> str:
    return post_message(
        get_db(),
        board="feature",
        scope="demo",
        from_agent="planner",
        type="task",
        text="Do the work.",
        files=files,
        author_role=author_role,
        author_source="token" if author_role else None,
    )


def _claim(task_id: str) -> None:
    assert claim_task(get_db(), task_id, "build")


def _spawn(repo: Path, role: str, *edits: tuple[str, str | None]) -> None:
    """One recorded spawn: snapshot, the role's edits (``None`` deletes), snapshot, an event."""
    before = tree.snapshot(repo)
    for rel, text in edits:
        if text is None:
            (repo / rel).unlink()
        else:
            _write(repo, rel, text)
    after = tree.snapshot(repo)
    assert before and after
    eventlog.append_event(
        str(_storage(repo)),
        {
            "type": "SPAWN_WINDOW",
            "role": role,
            "run_id": "demo-%s-1" % role,
            "state": "BUILDING",
            "before": before,
            "after": after,
            "head_before": None,
            "head_after": None,
        },
        create_dir=False,
    )


def _planned_build(repo: Path) -> dict:
    """The planner's task posted in PLANNING, the build started, the builder claims it."""
    flow = _flow()
    task_id = _post_task(["src/app.py"])
    assert _start_build(repo, flow) == ["pathly/"]
    _claim(task_id)
    return flow


def _gate(repo: Path, flow: dict, **kw):
    kw.setdefault("feature_scope", "demo")
    return run_gates(flow, "BUILDING", "REVIEWING", _storage(repo), "demo", 1, **kw)


def _failed(result) -> bool:
    return result == {
        "gate_failed": "scope_gate",
        "feedback_file": "SCOPE_VIOLATION.md",
    }


def _violation(repo: Path) -> str:
    return (_storage(repo) / "feedback" / "SCOPE_VIOLATION.md").read_text(
        encoding="utf-8"
    )


def _skips(repo: Path) -> list[str]:
    events = eventlog.read_events(str(_storage(repo)))
    return [e["reason"] for e in events if e["type"] == "GATE_SKIPPED"]


# ── an uncommitted plan is judged by its content ─────────────────────────────


def test_a_builder_edit_to_an_uncommitted_plan_file_fails(repo):
    flow = _planned_build(repo)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"), (STORIES, "# Rewritten\n"))

    assert _failed(_gate(repo, flow))
    text = _violation(repo)
    assert STORIES in text
    assert "src/app.py" not in text
    assert PLAN not in text


def test_a_builder_cannot_widen_an_uncommitted_scope_file(repo):
    flow = _planned_build(repo)
    widened = "# Plan\n\n**File:** `src/app.py`\n**File:** `src/`\n"
    _spawn(repo, "builder", (PLAN, widened), ("src/other.py", "y = 3\n"))

    assert _failed(_gate(repo, flow))
    assert PLAN in _violation(repo)


def test_an_uncommitted_plan_the_build_left_alone_passes(repo):
    flow = _planned_build(repo)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"))

    assert _gate(repo, flow) is None
    assert _skips(repo) == []


def test_a_planner_window_explains_its_edit_to_an_uncommitted_plan(repo):
    flow = _planned_build(repo)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"))
    _spawn(repo, "planner", (STORIES, "# Stories\n\nClarified.\n"))

    assert _gate(repo, flow) is None


def test_a_builder_edit_after_the_planner_on_an_uncommitted_plan_fails(repo):
    flow = _planned_build(repo)
    _spawn(repo, "planner", (STORIES, "# Stories\n\nClarified.\n"))
    _spawn(repo, "builder", (STORIES, "# Stories\n\nRewritten by the builder.\n"))

    assert _failed(_gate(repo, flow))
    assert STORIES in _violation(repo)


def test_an_edit_after_the_first_window_began_counts_outside_any_window(repo):
    flow = _planned_build(repo)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"))
    _write(repo, STORIES, "# Written after the window closed\n")

    assert _failed(_gate(repo, flow))
    assert STORIES in _violation(repo)


def test_a_builder_deleting_an_uncommitted_plan_file_fails(repo):
    """An untracked file that is gone is in no ``git status`` line, only in the tree diff."""
    flow = _planned_build(repo)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"), (STORIES, None))
    assert STORIES not in _git(
        repo, "status", "--porcelain=v1", "--untracked-files=all"
    )

    assert _failed(_gate(repo, flow))
    assert STORIES in _violation(repo)


def test_a_committed_plan_modified_before_the_build_is_judged_by_content(repo):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "plan")
    _write(repo, STORIES, "# Stories\n\nEdited in PLANNING, not committed.\n")
    flow = _flow()
    task_id = _post_task(["src/app.py"])
    assert _start_build(repo, flow) == [STORIES]
    _claim(task_id)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"))
    assert _gate(repo, flow) is None

    _spawn(repo, "builder", (STORIES, "# Stories\n\nThen the builder.\n"))
    assert _failed(_gate(repo, flow))
    assert STORIES in _violation(repo)


# ── which claimed tasks declare scope ────────────────────────────────────────


def test_a_task_posted_after_the_build_began_declares_nothing(repo):
    flow = _planned_build(repo)
    late = _post_task(["src/other.py"])
    _claim(late)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"), ("src/other.py", "y = 3\n"))

    assert _failed(_gate(repo, flow))
    text = _violation(repo)
    assert "src/other.py" in text
    assert "src/app.py" not in text


def test_a_task_a_builder_posted_declares_nothing(repo):
    flow = _flow()
    planned = _post_task(["src/app.py"])
    by_builder = _post_task(["src/other.py"], author_role="builder")
    _start_build(repo, flow)
    _claim(planned)
    _claim(by_builder)
    _spawn(repo, "builder", ("src/app.py", "x = 2\n"), ("src/other.py", "y = 3\n"))

    assert _failed(_gate(repo, flow))
    assert "src/other.py" in _violation(repo)


# ── unreadable windows ───────────────────────────────────────────────────────


def test_unreadable_windows_still_fail_a_file_no_window_could_explain(
    repo, monkeypatch
):
    def broken(*_a, **_k):
        raise RuntimeError("db is gone")

    flow = _planned_build(repo)
    monkeypatch.setattr(_proof, "windows_since", broken)
    _write(repo, "src/other.py", "y = 3\n")
    _write(repo, STORIES, "# Rewritten\n")

    assert _failed(_gate(repo, flow))
    text = _violation(repo)
    assert "src/other.py" in text
    assert STORIES not in text
    assert _skips(repo) == []
