"""The scenarios of the build-proof acceptance test, each one a real run through ``start_run``.

Every ``run_*`` function makes a project, scripts the fake agent, drives the packaged
``team-build`` or ``goal-loop`` flow to the end and returns a :class:`Run`. The tests in
``test_build_proof_acceptance.py`` only assert on what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from build_proof_acceptance_support import (
    APP_V2,
    BUILDER_SUMMARY,
    SKIPPED_TEST,
    STORIES,
    TEST_APP,
    Harness,
    Projects,
    Spawn,
    add_task,
    appending,
    check_block,
    drive,
    make_harness,
    settings,
)

from pathly_orchestrator.db import get_db
from pathly_orchestrator.supervisor import RunnerState
from tests._python import python_command

RED_CHECK = python_command("import sys; print('red-marker'); sys.exit(3)")
FIXED_TEST = python_command(
    "import pathlib,sys; sys.exit(0 if pathlib.Path('src/fixed.txt').exists() else 1)"
)
EDITED_TASK = "Make the build green (an easier version)."
Script = Callable[[Harness, Spawn], Optional[str]]


@dataclass
class Run:
    h: Harness
    state: RunnerState
    tasks: dict[str, str] = field(default_factory=dict)


def team_build(h: Harness) -> None:
    """What ``team/build`` does: claim the ready tasks, edit, write VERIFY.md, complete them."""
    ids = h.claim()
    h.write("src/app.py", APP_V2)
    h.write("pathly/features/%s/VERIFY.md" % h.topic, "RESULT: PASS\n")
    h.finish(ids)


def run_team(
    projects: Projects,
    topic: str,
    script: Script,
    text: str,
    files: list[str],
    config: Optional[dict[str, str]] = None,
) -> Run:
    """A ``team-build`` run over one task that declares ``files``."""
    h = make_harness(projects, topic, script)
    task = add_task(topic, h.goal_id, text, files=files)
    with settings(config or {}):
        return Run(h, drive(projects, h, "team-build"), {"task": task})


def run_floor_team(projects: Projects) -> Run:
    """The builder skips a test; the floor gate sends it back; it removes the skip."""

    def script(h: Harness, s: Spawn):
        if s.kind == "stage" and s.state == "BUILDING":
            team_build(h)
            h.write("tests/test_app.py", SKIPPED_TEST)
        elif "FLOOR_FAILURES.md" in s.feedback:
            h.seen["floor"] = h.feedback_text("FLOOR_FAILURES.md")
            h.write("tests/test_app.py", TEST_APP)
        elif s.kind == "stage" and s.state == "REVIEWING":
            h.review_passes()

    return run_team(
        projects,
        "bp-floor-team",
        script,
        "Add answer() to src/app.py.",
        ["src/app.py", "tests/test_app.py"],
    )


def run_floor_loop(projects: Projects) -> Run:
    """A builder fix round after the drain turns the test command green with a skip."""

    def script(h: Harness, s: Spawn):
        if s.kind == "task":
            h.write("src/feature.py", "VALUE = 1\n")
        elif "TEST_FAILURES.md" in s.feedback:
            h.write("src/fixed.txt", "fixed\n")
            h.write("tests/test_app.py", SKIPPED_TEST)
        elif "FLOOR_FAILURES.md" in s.feedback:
            h.seen["floor"] = h.feedback_text("FLOOR_FAILURES.md")
            h.write("tests/test_app.py", TEST_APP)

    h = make_harness(projects, "bp-floor-loop", script)
    task = add_task(h.topic, h.goal_id, "Add the feature module.")
    with settings({"verify.test": FIXED_TEST}):
        return Run(h, drive(projects, h, "goal-loop"), {"task": task})


def run_red_check(projects: Projects) -> Run:
    """The fake reports success both times; the task's own check fails both times."""
    h = make_harness(projects, "bp-red-check", lambda h, s: None)
    task = add_task(
        h.topic, h.goal_id, "Make the build green." + check_block(RED_CHECK)
    )
    with settings({"goal.task_max_attempts": "2"}):
        return Run(h, drive(projects, h, "goal-loop"), {"task": task})


def run_task_edit(projects: Projects) -> Run:
    """Attempt 1 rewrites its own task (dropping the check); attempt 2 puts the text back."""
    original = "Make x two." + check_block(appending(projects.tmp_path / "edit.log"))

    def script(h: Harness, s: Spawn):
        if s.kind == "task":
            conn = get_db()
            text = EDITED_TASK if s.attempt == 1 else original
            conn.execute(
                "UPDATE comms_messages SET text=? WHERE id=?", (text, s.task_id)
            )
            conn.commit()

    h = make_harness(projects, "bp-task-edit", script)
    h.seen["original"] = original
    task = add_task(h.topic, h.goal_id, original)
    return Run(h, drive(projects, h, "goal-loop"), {"task": task})


def run_plan_edit(projects: Projects) -> Run:
    """The builder rewrites USER_STORIES.md while building; the floor gate calls it plan-edit."""
    stories = "pathly/features/bp-plan-edit/USER_STORIES.md"

    def script(h: Harness, s: Spawn):
        if s.kind == "stage" and s.state == "BUILDING":
            team_build(h)
            h.write(stories, "# Stories\n- adds nothing\n")
        elif "FLOOR_FAILURES.md" in s.feedback:
            h.seen["floor"] = h.feedback_text("FLOOR_FAILURES.md")
            h.write(stories, STORIES)
        elif s.kind == "stage" and s.state == "REVIEWING":
            h.review_passes()

    return run_team(
        projects, "bp-plan-edit", script, "Add answer() to src/app.py.", ["src/app.py"]
    )


def run_reviewer_edit(projects: Projects) -> Run:
    """The reviewer writes REVIEW.md (PASS) and also changes src/app.py."""

    def script(h: Harness, s: Spawn):
        if s.kind == "stage" and s.state == "BUILDING":
            team_build(h)
        elif s.kind == "stage" and s.state == "REVIEWING":
            h.review_passes()
            h.write("src/app.py", APP_V2 + "\n# reviewer was here\n")

    return run_team(
        projects,
        "bp-reviewer-edit",
        script,
        "Add answer() to src/app.py.",
        ["src/app.py"],
    )


def run_red_base(projects: Projects) -> Run:
    return run_team(
        projects,
        "bp-red-base",
        lambda h, s: None,
        "Add answer() to src/app.py.",
        ["src/app.py"],
        {"verify.build": python_command("raise SystemExit(1)")},
    )


def run_dependency(projects: Projects) -> Run:
    """Task B depends on task A; A reports A-RESULT-MARKER."""
    ids: dict[str, str] = {}

    def script(h: Harness, s: Spawn):
        if s.kind == "task":
            h.write("src/m%s.py" % s.task_id[:6], "VALUE = 1\n")
            return "A-RESULT-MARKER" if s.task_id == ids["a"] else "B is built"

    h = make_harness(projects, "bp-dependency", script)
    ids["a"] = add_task(h.topic, h.goal_id, "Task A: build the base module.")
    ids["b"] = add_task(
        h.topic, h.goal_id, "Task B: build on A.", depends_on=[ids["a"]]
    )
    return Run(h, drive(projects, h, "goal-loop"), ids)


def run_happy_team(projects: Projects, log: Path) -> Run:
    """One task with a passing check; the reviewer writes only REVIEW.md."""

    def script(h: Harness, s: Spawn):
        if s.kind == "stage" and s.state == "BUILDING":
            team_build(h)
            return BUILDER_SUMMARY
        if s.kind == "stage" and s.state == "REVIEWING":
            h.review_passes()

    text = "Add answer() to src/app.py. FROZEN-TASK-TEXT" + check_block(appending(log))
    return run_team(
        projects,
        "bp-happy-team",
        script,
        text,
        ["src/app.py"],
        {
            "verify.build": python_command("pass"),
            "verify.test": python_command("pass"),
        },
    )


def run_happy_loop(projects: Projects, log: Path) -> Run:
    """Two independent clean tasks, each with a passing check that appends to ``log``."""

    def script(h: Harness, s: Spawn):
        if s.kind == "task":
            h.write("src/m%s.py" % s.task_id[:6], "VALUE = 1\n")

    h = make_harness(projects, "bp-happy-loop", script)
    ids = {
        name: add_task(
            h.topic, h.goal_id, "Task %s." % name + check_block(appending(log))
        )
        for name in ("one", "two")
    }
    return Run(h, drive(projects, h, "goal-loop"), ids)
