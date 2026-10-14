"""``scope_gate`` judges only what the builder may write (build-proof 08).

The declared scope is the backtick paths in the gate's ``scope_file`` (optional) plus the
``files`` of the board tasks claimed since ``build_baseline.started_at``. Exempt: what the
builder stage may write (``_proof.stage_writes(storage, "builder")``: feedback files,
``VERIFY.md``, the server's exports, ``*.tsbuildinfo``), the flow's
``scope_gate.exempt_prefixes``, and a path a ``SPAWN_WINDOW`` explains. The blanket
``pathly/features/`` and ``pathly/plans/`` exemption is gone, so a builder edit to its own plan
fails. Every case runs the real gate in a ``git init`` repo under ``tmp_path`` against the
isolated test DB.
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
LONG_AGO = "2020-01-01T00:00:00+00:00"


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
    _write(root, "lib/helper.py", "z = 3\n")
    _write(root, PLAN, "# Plan\n\n**File:** `lib/helper.py`\n")
    _write(root, STORIES, "# Stories\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _storage(repo: Path) -> Path:
    return repo / FEATURE


def _flow(scope_file: str | None = "IMPLEMENTATION_PLAN.md", exempt=()) -> dict:
    gate = {"type": "scope_gate", "on_fail": "SCOPE_VIOLATION.md"}
    if scope_file is not None:
        gate["scope_file"] = scope_file
    return {
        "flow": "scope-test",
        "states": ["BUILDING", "REVIEWING", "DONE"],
        "transitions": {"BUILDING": ["REVIEWING"], "REVIEWING": ["DONE"], "DONE": []},
        "feedback_routing": {"SCOPE_VIOLATION": "builder"},
        "scope_gate": {"exempt_prefixes": list(exempt)},
        "gates": {"BUILDING->REVIEWING": [gate]},
    }


def _start_build(repo: Path, flow: dict, preexisting=()) -> None:
    """Stamp ``build_baseline`` the way ``fsm_ops.next_action`` does on entering BUILDING."""
    baseline = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "preexisting_dirty": list(preexisting),
    }
    eventlog.write_state(
        str(_storage(repo)), {"current": "BUILDING", "build_baseline": baseline}, flow
    )


def _claimed_task(files, *, scope: str = "demo", goal_id=None) -> str:
    conn = get_db()
    task_id = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text="Do the work.",
        files=files,
        goal_id=goal_id,
    )
    assert claim_task(conn, task_id, "build")
    return task_id


def _build(repo: Path, files=("src/app.py",), preexisting=(), **flow_kw) -> dict:
    """A started build with one task claimed in it that declares ``files``."""
    flow = _flow(**flow_kw)
    _start_build(repo, flow, preexisting)
    _claimed_task(list(files) if files is not None else None)
    return flow


def _gate(repo: Path, flow: dict, **kw):
    kw.setdefault("feature_scope", "demo")
    return run_gates(flow, "BUILDING", "REVIEWING", _storage(repo), "demo", 1, **kw)


def _violation(repo: Path) -> str:
    return (_storage(repo) / "feedback" / "SCOPE_VIOLATION.md").read_text(
        encoding="utf-8"
    )


def _events(repo: Path, kind: str) -> list[dict]:
    return [e for e in eventlog.read_events(str(_storage(repo))) if e["type"] == kind]


def _failed(result) -> bool:
    return result == {
        "gate_failed": "scope_gate",
        "feedback_file": "SCOPE_VIOLATION.md",
    }


# ── the declared scope: claimed tasks' files ∪ the scope file's paths ────────


def test_a_change_inside_a_claimed_tasks_files_passes(repo):
    flow = _build(repo)
    _write(repo, "src/app.py")

    assert _gate(repo, flow) is None
    assert not (_storage(repo) / "feedback" / "SCOPE_VIOLATION.md").exists()


def test_a_change_outside_the_claimed_files_fails_naming_the_path(repo):
    flow = _build(repo)
    _write(repo, "src/app.py")
    _write(repo, "src/other.py")

    assert _failed(_gate(repo, flow))
    text = _violation(repo)
    assert "src/other.py" in text
    assert "src/app.py" not in text
    (event,) = _events(repo, "GATE_FAILED")
    assert event["gate"] == "scope_gate"


def test_the_scope_file_paths_and_the_task_files_are_one_union(repo):
    flow = _build(repo)
    _write(repo, "src/app.py")
    _write(repo, "lib/helper.py")  # named in IMPLEMENTATION_PLAN.md
    assert _gate(repo, flow) is None

    _write(repo, "src/other.py")
    assert _failed(_gate(repo, flow))
    assert "src/other.py" in _violation(repo)


def test_a_task_claimed_before_the_build_started_declares_nothing(repo):
    flow = _flow()
    _start_build(repo, flow)
    old = _claimed_task(["src/other.py"])
    conn = get_db()
    conn.execute("UPDATE comms_messages SET claimed_at=? WHERE id=?", (LONG_AGO, old))
    conn.commit()
    _claimed_task(["src/app.py"])
    _write(repo, "src/other.py")

    assert _failed(_gate(repo, flow))
    assert "src/other.py" in _violation(repo)


def test_a_goal_run_reads_the_goals_claimed_tasks(repo):
    flow = _flow()
    _start_build(repo, flow)
    _claimed_task(["src/app.py"], scope="elsewhere", goal_id="g1")
    _claimed_task(["src/other.py"], scope="elsewhere", goal_id="g2")
    _write(repo, "src/app.py")
    assert _gate(repo, flow, goal_id="g1") is None

    _write(repo, "src/other.py")
    assert _failed(_gate(repo, flow, goal_id="g1"))


# ── directories ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("entry", ["src/pkg", "src/pkg/"])
def test_a_declared_directory_covers_the_files_under_it(repo, entry):
    flow = _build(repo, [entry])
    _write(repo, "src/pkg/a.py")
    _write(repo, "src/pkg/sub/b.py")

    assert _gate(repo, flow) is None


def test_a_declared_directory_does_not_cover_a_sibling_sharing_its_prefix(repo):
    flow = _build(repo, ["src/pkg"])
    _write(repo, "src/pkg/a.py")
    _write(repo, "src/pkgextra.py")

    assert _failed(_gate(repo, flow))
    text = _violation(repo)
    assert "src/pkgextra.py" in text
    assert "src/pkg/a.py" not in text


def test_declared_files_in_a_new_untracked_directory_pass(repo):
    """git lists a new folder as one ``?? src/newpkg/`` line unless asked for every file."""
    flow = _build(repo, ["src/newpkg/a.py", "src/newpkg/b.py"])
    _write(repo, "src/newpkg/a.py")
    _write(repo, "src/newpkg/b.py")
    assert _gate(repo, flow) is None

    _write(repo, "src/newpkg/c.py")
    assert _failed(_gate(repo, flow))
    assert "src/newpkg/c.py" in _violation(repo)


def test_a_preexisting_untracked_directory_covers_the_files_under_it(repo):
    """``git status`` names an untracked folder as ``scratch/`` in the baseline."""
    _write(repo, "scratch/notes.txt", "mine\n")
    flow = _build(repo, preexisting=["scratch/"])
    _write(repo, "src/app.py")

    assert _gate(repo, flow) is None


# ── plan files: the builder may not write them unless a window explains it ───


def test_a_builder_edit_to_the_user_stories_fails(repo):
    flow = _build(repo)
    _write(repo, "src/app.py")
    _write(repo, STORIES, "# Stories\n\nRewritten by the builder.\n")

    assert _failed(_gate(repo, flow))
    assert STORIES in _violation(repo)


def _planner_window(repo: Path, before: str | None, after: str | None) -> None:
    eventlog.append_event(
        str(_storage(repo)),
        {
            "type": "SPAWN_WINDOW",
            "role": "planner",
            "run_id": "demo-fb1-1",
            "state": "BUILDING",
            "before": before,
            "after": after,
            "head_before": None,
            "head_after": None,
        },
        create_dir=False,
    )


def test_the_same_edit_explained_by_a_planner_window_passes(repo):
    flow = _build(repo)
    _write(repo, "src/app.py")
    before = tree.snapshot(repo)
    _write(repo, STORIES, "# Stories\n\nClarified by the planner.\n")
    after = tree.snapshot(repo)
    _planner_window(repo, before, after)

    assert _gate(repo, flow) is None


def test_a_builder_edit_after_the_planners_window_fails(repo):
    flow = _build(repo)
    before = tree.snapshot(repo)
    _write(repo, STORIES, "# Stories\n\nClarified by the planner.\n")
    after = tree.snapshot(repo)
    _planner_window(repo, before, after)
    _write(repo, STORIES, "# Stories\n\nThen rewritten by the builder.\n")

    assert _failed(_gate(repo, flow))
    assert STORIES in _violation(repo)


def test_the_scope_file_cannot_widen_the_scope_to_cover_its_own_edit(repo):
    flow = _build(repo)
    _write(repo, PLAN, "# Plan\n\n**File:** `lib/helper.py`\n**File:** `pathly/`\n")

    assert _failed(_gate(repo, flow))
    assert PLAN in _violation(repo)


def test_the_builders_feedback_files_and_verify_pass(repo):
    flow = _build(repo)
    _write(repo, "src/app.py")
    _write(repo, FEATURE + "/feedback/IMPL_QUESTIONS.md", "[REQ] which one?\n")
    _write(repo, FEATURE + "/VERIFY.md", "RESULT: PASS\n")

    assert _gate(repo, flow) is None


def test_tsbuildinfo_and_the_flows_exempt_prefixes_pass(repo):
    flow = _build(repo, exempt=["docs/"])
    _write(repo, "docs/guide.md")
    _write(repo, "studio/tsconfig.tsbuildinfo")

    assert _gate(repo, flow) is None


# ── skips and the failure text ───────────────────────────────────────────────


def test_no_scope_file_and_no_task_files_skips(repo):
    flow = _build(repo, None, scope_file=None)
    _write(repo, "src/other.py")

    assert _gate(repo, flow) is None
    assert [e["reason"] for e in _events(repo, "GATE_SKIPPED")] == ["no_declared_scope"]


def test_unreadable_spawn_windows_fail_open(repo, monkeypatch):
    def broken(*_a, **_k):
        raise RuntimeError("db is gone")

    monkeypatch.setattr(_proof, "windows_since", broken)
    flow = _build(repo)
    _write(repo, STORIES, "# Stories\n\nRewritten.\n")

    assert _gate(repo, flow) is None
    assert [e["reason"] for e in _events(repo, "GATE_SKIPPED")] == [
        "spawn_windows_unreadable"
    ]


def test_the_failure_names_at_most_twenty_paths_then_a_count(repo):
    flow = _build(repo)
    for i in range(25):
        _write(repo, "src/extra_%02d.py" % i)

    assert _failed(_gate(repo, flow))
    text = _violation(repo)
    named = [line for line in text.splitlines() if "src/extra_" in line]
    assert len(named) == 20
    assert "src/extra_00.py" in text
    assert "src/extra_20.py" not in text
    assert "5 more" in text


# ── the packaged team flows ──────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_team_flows_end_building_with_the_scope_gate(name):
    from pathly_orchestrator.fsm_compose_responses import _exit_requirement
    from pathly_orchestrator.fsm_ops import _load_flow

    flow = _load_flow(name)
    assert flow["gates"]["BUILDING->REVIEWING"][-1] == {
        "type": "scope_gate",
        "scope_file": "IMPLEMENTATION_PLAN.md",
        "on_fail": "SCOPE_VIOLATION.md",
    }
    assert flow["feedback_routing"]["SCOPE_VIOLATION"] == "builder"

    requirement = _exit_requirement(flow, "BUILDING")
    assert "`IMPLEMENTATION_PLAN.md`" in requirement
    assert "`files`" in requirement


def test_goal_loop_does_not_carry_the_scope_gate():
    from pathly_orchestrator.fsm_ops import _load_flow

    flow = _load_flow("goal-loop")
    types = {g["type"] for gates in flow["gates"].values() for g in gates or []}
    assert "scope_gate" not in types
