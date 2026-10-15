"""Prove build-proof end to end (ticket 14): the brief's bar, against the real flows.

Each test is one item of the bar (or one flow of an item). A scenario starts the packaged
``team-build`` or ``goal-loop`` flow through ``supervisor.start_run`` in a real ``git init``
project, with one scripted fake agent in place of ``_run_stage_via_terminal`` and no model. The
scenarios are in ``build_proof_acceptance_runs.py``. The tests for items 1 and 2 keep their runs
(``keep``) so the test for the debug fragment (item 7) reads their prompts through ``kept``
instead of repeating them; it runs a scenario itself when its test is run alone.
"""

from __future__ import annotations

import re
from typing import Callable

from build_proof_acceptance_runs import (
    Run,
    run_dependency,
    run_floor_loop,
    run_floor_team,
    run_happy_loop,
    run_happy_team,
    run_plan_edit,
    run_red_base,
    run_red_check,
    run_reviewer_edit,
    run_task_edit,
)
from build_proof_acceptance_support import (
    BUILDER_SUMMARY,
    DEBUG_HEADING,
    board_posts,
    projects,
    task_row,
)

from pathly_orchestrator import eventlog
from pathly_orchestrator.proof import tree

__all__ = ["projects"]

RESULTS_HEADING = "## Results of the tasks this one depends on"
_RUNS: dict[str, Run] = {}


def keep(name: str, make: Callable[[], Run]) -> Run:
    """Run a scenario in this test and keep the run for item 7, which reads its spawns only."""
    _RUNS[name] = make()
    return _RUNS[name]


def kept(name: str, make: Callable[[], Run]) -> Run:
    """The run an earlier test kept, else a run of its own (the run's DB is gone: spawns only)."""
    return _RUNS[name] if name in _RUNS else make()


def gates_failed(run: Run) -> list[tuple[str, str]]:
    return [(e["gate"], e["transition"]) for e in run.h.events("GATE_FAILED")]


def assert_sent_back(spawn, h, name: str) -> None:
    """The spawn is a builder feedback spawn, made while the gate's feedback file is open.

    ``spawn.feedback`` is what the ``feedback/`` folder held when the supervisor spawned the
    agent. The builder's feedback prompt (``build_prompt_for_agent``) names that file in its
    ``## Feedback to resolve`` block and shows its text.
    """
    assert spawn.kind == "feedback"
    assert spawn.feedback == [name]
    assert spawn.instructions.startswith("# builder\n")
    assert "Storage path: %s\n" % h.storage in spawn.instructions
    assert "## Feedback to resolve" in spawn.instructions
    assert "%s/feedback/%s" % (h.storage.as_posix(), name) in spawn.instructions


def test_1_floor_gate_sends_a_skipping_builder_back_in_team_build(projects):
    run = keep("floor_team", lambda: run_floor_team(projects))
    h = run.h
    # Only the floor gate objects: the task declares every file the builder touched.
    assert gates_failed(run) == [("floor_gate", "BUILDING->REVIEWING")]
    assert [(s.kind, s.state) for s in h.spawns[:3]] == [
        ("stage", "BUILDING"),
        ("feedback", "BUILDING"),
        ("stage", "REVIEWING"),
    ]
    assert_sent_back(h.spawns[1], h, "FLOOR_FAILURES.md")
    assert "skip: tests/test_app.py: " in h.seen["floor"]
    assert run.state.status == "done"


def test_1_floor_gate_sends_a_skipping_builder_back_after_the_goal_drain(projects):
    run = keep("floor_loop", lambda: run_floor_loop(projects))
    h = run.h
    assert [(s.kind, s.feedback) for s in h.spawns] == [
        ("task", []),
        ("feedback", ["TEST_FAILURES.md"]),
        ("feedback", ["FLOOR_FAILURES.md"]),
    ]
    # The join's test command failed once; then it was green and only the floor gate objected.
    assert gates_failed(run) == [
        ("command_gate", "DRAINING->DONE"),
        ("floor_gate", "DRAINING->DONE"),
    ]
    assert (h.root / "src" / "fixed.txt").exists()
    assert_sent_back(h.spawns[2], h, "FLOOR_FAILURES.md")
    assert "skip: tests/test_app.py: " in h.seen["floor"]
    assert run.state.status == "done"


def test_2_failing_check_is_retried_with_its_output_then_fails(projects):
    run = keep("red_check", lambda: run_red_check(projects))
    h, task_id = run.h, run.tasks["task"]
    first, second = [s for s in h.spawns if s.kind == "task"]
    assert (first.task_id, first.attempt) == (task_id, 1)
    assert (second.task_id, second.attempt) == (task_id, 2)
    assert "got: exit 3" not in first.instructions
    retry = second.instructions.split("## Retry attempt 2", 1)[1]
    assert "got: exit 3" in retry
    assert "\nred-marker\n" in retry  # the command's real output
    row = task_row(task_id)
    assert row["task_status"] == "failed"
    assert "got: exit 3" in row["fail_reason"]
    escalations = board_posts(h.topic, "escalation")
    assert [e["goal_id"] for e in escalations] == [h.goal_id]
    assert "Task failed after 2 attempt(s)" in escalations[0]["text"]


def test_3_task_text_edit_is_caught_and_the_retry_shows_the_frozen_text(projects):
    run = run_task_edit(projects)
    h, task_id = run.h, run.tasks["task"]
    first, second = [s for s in h.spawns if s.kind == "task"]
    assert "task-edit: task" not in first.instructions
    assert "task-edit: task %s" % task_id in second.instructions
    # The retry shows the text frozen at the claim, not the one the agent wrote.
    assert "easier version" not in second.instructions
    assert "Make x two." in second.instructions
    proofs = [e for e in h.events("TASK_PROOF") if e["task_id"] == task_id]
    # The checks came from the frozen text, so they ran on attempt 1 although the live text
    # had lost its block; the floor verdict is what failed that attempt.
    assert [(p["checks"], p["floor"]) for p in proofs] == [
        ("passed", "failed"),
        ("passed", "clean"),
    ]
    assert (projects.tmp_path / "edit.log").read_text() == "xx"
    assert task_row(task_id)["claimed_text"] == h.seen["original"]
    assert run.state.status == "done"


def test_3_plan_edit_by_the_builder_is_caught(projects):
    run = run_plan_edit(projects)
    assert gates_failed(run) == [("floor_gate", "BUILDING->REVIEWING")]
    assert (
        "plan-edit: pathly/features/bp-plan-edit/USER_STORIES.md" in run.h.seen["floor"]
    )
    assert run.state.status == "done"


def test_4_reviewer_that_edits_a_tracked_file_fails_the_review(projects):
    run = run_reviewer_edit(projects)
    h = run.h
    assert (run.state.status, run.state.error_kind) == ("parked", "human_checkpoint")
    assert gates_failed(run) == [("reviewer_unchanged", "REVIEWING->TESTING")]
    assert [s.state for s in h.spawns] == ["BUILDING", "REVIEWING"]
    assert "src/app.py" in h.feedback_text("REVIEWER_CHANGED_FILES.md")
    assert (eventlog.read_state(str(h.storage)) or {})["current"] == "REVIEWING"
    escalations = board_posts(h.topic, "escalation")
    assert [(e["to_agent"], e["author_source"]) for e in escalations] == [
        ("human", "system")
    ]
    assert "REVIEWER_CHANGED_FILES.md" in escalations[0]["text"]


def test_5_red_base_blocks_the_run_before_any_spawn(projects):
    run = run_red_base(projects)
    h = run.h
    assert (run.state.status, run.state.error_kind) == ("parked", "base_red")
    assert len(h.spawns) == 0
    assert eventlog.read_state(str(h.storage)) is None
    assert h.events("SPAWN_WINDOW") == []
    escalations = board_posts(h.topic, "escalation")
    assert [e["to_agent"] for e in escalations] == ["human"]
    assert "The base is red" in escalations[0]["text"]


def test_6_dependent_task_prompt_carries_its_dependency_result(projects):
    run = run_dependency(projects)
    first, second = [s for s in run.h.spawns if s.kind == "task"]
    assert (first.task_id, second.task_id) == (run.tasks["a"], run.tasks["b"])
    assert RESULTS_HEADING not in first.instructions
    results = second.instructions.split(RESULTS_HEADING, 1)[1]
    assert "A-RESULT-MARKER" in results
    assert "Task A: build the base module." in results
    assert run.state.status == "done"


def test_7_debug_fragment_rides_on_retries_and_builder_feedback(projects):
    red = kept("red_check", lambda: run_red_check(projects))
    first, second = [s for s in red.h.spawns if s.kind == "task"]
    assert DEBUG_HEADING not in first.instructions
    assert DEBUG_HEADING in second.instructions
    floor = [
        kept("floor_team", lambda: run_floor_team(projects)),
        kept("floor_loop", lambda: run_floor_loop(projects)),
    ]
    fixes = [s for run in floor for s in run.h.spawns if s.kind == "feedback"]
    assert len(fixes) == 3
    assert all(DEBUG_HEADING in s.instructions for s in fixes)


def test_8_happy_path_team_build_reaches_done(projects, tmp_path):
    log = tmp_path / "team.log"
    run = run_happy_team(projects, log)
    h = run.h
    assert run.state.status == "done"
    assert gates_failed(run) == []
    assert [(s.kind, s.state) for s in h.spawns] == [
        ("stage", "BUILDING"),
        ("stage", "REVIEWING"),
        ("stage", "TESTING"),
        ("stage", "RETRO"),
    ]
    builder, reviewer, tester, retro = h.spawns
    assert len(re.findall(r"(?m)^## Review packet$", reviewer.instructions)) == 1
    packet = reviewer.instructions.split("\n## Review packet\n", 1)[1]
    task_part, diff_part = packet.split("### The diff", 1)
    assert "### The task" in task_part and "FROZEN-TASK-TEXT" in task_part
    assert "+def answer():" in diff_part
    assert BUILDER_SUMMARY not in reviewer.instructions
    assert [e["summary"] for e in h.events("AGENT_DONE")][0] == BUILDER_SUMMARY
    # The reviewer's own spawn changed REVIEW.md and nothing else.
    windows = [e for e in h.events("SPAWN_WINDOW") if e["role"] == "reviewer"]
    assert [tree.changes(str(h.root), w["before"], w["after"]) for w in windows] == [
        [("A", "pathly/features/bp-happy-team/REVIEW.md")]
    ]
    # A fresh session for the reviewer although the builder returned one; the tester resumes it.
    assert builder.session is None and builder.returned_session
    assert reviewer.session is None
    assert tester.session == reviewer.returned_session
    assert retro.session == tester.returned_session
    sessions = [
        (b["kind"], b["independent"]) for b in h.broadcasts if b["type"] == "SESSION"
    ]
    assert sessions == [
        ("opened", False),
        ("opened", True),
        ("continued", False),
        ("continued", False),
    ]
    # The checks ran once, at the first join; the later joins found the task proven.
    assert log.read_text() == "x"
    proofs = h.events("TASK_PROOF")
    assert [(p["run_id"], p["checks"]) for p in proofs] == [
        ("gate:BUILDING->REVIEWING", "passed")
    ]
    assert len(h.events("FLOOR_CHECKED")) == 4


def test_8_happy_path_goal_loop_reaches_done(projects, tmp_path):
    log = tmp_path / "loop.log"
    run = run_happy_loop(projects, log)
    h = run.h
    assert run.state.status == "done"
    assert gates_failed(run) == []
    assert [s.kind for s in h.spawns] == ["task", "task"]
    # The join: the floor gate scanned once and found nothing; task_checks ran nothing new.
    assert len(h.events("FLOOR_CHECKED")) == 1
    assert log.read_text() == "xx"
    proofs = h.events("TASK_PROOF")
    assert sorted(p["task_id"] for p in proofs) == sorted(run.tasks.values())
    assert all(p["run_id"].startswith("sched-") for p in proofs)
    assert all(p["checks"] == "passed" for p in proofs)
    assert all(task_row(t)["task_status"] == "done" for t in run.tasks.values())
