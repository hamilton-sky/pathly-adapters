"""A goal-loop task is proven after it reports success (build-proof 05).

`drain.drain_frontier` wraps the spawn with `supervisor/task_proof.wrap`. For a DAG task
(`sched-<id>#<n>`) it takes a working-tree snapshot before the spawn and after it returns, and when
the agent reported success it scans the diff with the floor guard, compares the task's text with
the copy frozen at the claim, and runs the task's check blocks. A finding turns the outcome into a
failure, which the existing `scheduler_loop` -> `task_retry` path retries with the real output.

These tests drive the real `drain_frontier` and the real scheduler over a `git init` project under
`tmp_path`, with a fake spawn that reports success. One test source line adds a skip marker to a
file in that temp repo, which is why the ticket carries `Floor: allow skip`. Setup is in
`task_proof_support`; the wrapper on its own is in `test_task_proof_window.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from task_proof_support import (
    PLAN,
    RED_TEXT,
    SAMPLE_TEST,
    SKIPPED_TEST,
    Agent,
    State,
    add_task,
    drain,
    make_repo,
    proofs,
    row,
    set_app_setting,
    set_text,
    write,
)

from tests._python import python_command

GREEN_TEXT = "Greet.\n\n```check\n$ %s\nprints green\n```\n" % python_command(
    "print('green')"
)


@pytest.fixture(autouse=True)
def _code_intel_off(_isolate_db):
    set_app_setting("code_context.backend", "off")


# ── The check block ──────────────────────────────────────────────────────────


def test_a_failing_check_is_retried_with_its_real_output_then_fails(tmp_path):
    from pathly_orchestrator.fsm.gates._proof_record import task_proven

    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "2")
    tid = add_task(RED_TEXT)
    agent = Agent(repo, cost=0.25)

    raw, tracker = drain(state, agent)

    prompts = agent.prompts[tid]
    assert len(prompts) == 2
    assert "got: exit 3" not in prompts[0]
    assert "got: exit 3" in prompts[1]
    assert "its output:\nred-marker" in prompts[1]
    final = row(tid)
    assert final["task_status"] == "failed" and tid in raw["failed"]
    assert "got: exit 3" in final["fail_reason"]
    assert [p["checks"] for p in proofs(state)] == ["failed", "failed"]
    assert not task_proven(state.storage_path, final)
    assert tracker.total == pytest.approx(0.5)


def test_a_clean_task_is_done_and_proven_with_or_without_a_check_block(tmp_path):
    from pathly_orchestrator.fsm.gates._proof_record import task_proven

    repo = make_repo(tmp_path)
    state = State(repo)
    plain = add_task("Greet.")
    checked = add_task(GREEN_TEXT)
    agent = Agent(repo, {plain: [write("src/app.py", "def greet():\n    return 1\n")]})

    raw, _ = drain(state, agent)

    assert sorted(raw["completed"]) == sorted([plain, checked])
    by_task = {p["task_id"]: p for p in proofs(state)}
    assert by_task[plain]["checks"] == "none" and by_task[plain]["floor"] == "clean"
    assert by_task[checked]["checks"] == "passed"
    for tid in (plain, checked):
        final = row(tid)
        assert final["task_status"] == "done"
        assert by_task[tid]["claimed_at"] == final["claimed_at"]
        assert by_task[tid]["run_id"] == "sched-%s#1" % tid
        assert task_proven(state.storage_path, final)


def test_an_unreadable_check_block_fails_the_attempt_and_quotes_the_error(tmp_path):
    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "2")
    tid = add_task("Greet.\n\n```check\nprints hello\n```\n")
    agent = Agent(repo)

    drain(state, agent)

    assert len(agent.prompts[tid]) == 2
    quoted = "'prints hello' comes before the first `$ <command>` line"
    assert quoted in agent.prompts[tid][1]
    assert {p["checks"] for p in proofs(state)} == {"error"}


def test_a_project_outside_git_still_runs_the_checks_and_records_floor_off(tmp_path):
    repo = make_repo(tmp_path, with_git=False)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "1")
    red = add_task(RED_TEXT)
    clean = add_task("Greet.")

    raw, _ = drain(state, Agent(repo, {clean: [write("src/app.py", "x = 1\n")]}))

    assert red in raw["failed"] and clean in raw["completed"]
    assert {p["floor"] for p in proofs(state)} == {"off"}


def test_the_whole_report_survives_into_the_retry_prompt_and_the_final_failure(
    tmp_path,
):
    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "2")
    noisy = "import sys; print('x' * 3000 + 'EN' + 'D-MARKER'); sys.exit(2)"
    tid = add_task(f"Greet.\n\n```check\n$ {python_command(noisy)}\n```\n")
    seen: dict = {}

    def second_attempt(repo: Path) -> None:
        seen["fail_reason"] = row(tid)["fail_reason"]

    agent = Agent(repo, {tid: [lambda repo: None, second_attempt]})

    drain(state, agent)

    assert 3000 < len(seen["fail_reason"]) <= 4000
    assert seen["fail_reason"].rstrip().endswith("END-MARKER")
    assert "END-MARKER" in agent.prompts[tid][1]
    assert row(tid)["fail_reason"].rstrip().endswith("END-MARKER")


# ── The floor guard ──────────────────────────────────────────────────────────


def test_a_task_that_adds_a_skip_is_retried_with_the_finding(tmp_path):
    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "2")
    tid = add_task("Greet.")
    seen: dict = {}

    def second_attempt(repo: Path) -> None:
        seen["fail_reason"] = row(tid)["fail_reason"]
        write("tests/test_sample.py", SAMPLE_TEST)(repo)

    steps = {tid: [write("tests/test_sample.py", SKIPPED_TEST), second_attempt]}
    agent = Agent(repo, steps)

    raw, _ = drain(state, agent)

    assert "skip: tests/test_sample.py" in seen["fail_reason"]
    assert "skip: tests/test_sample.py" in agent.prompts[tid][1]
    assert raw["completed"] == [tid]
    assert [p["floor"] for p in proofs(state)] == ["failed", "clean"]


def test_what_a_human_allowed_for_the_task_passes(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.task_proof import set_floor_allow

    repo = make_repo(tmp_path)
    state = State(repo)
    skipper = add_task("Greet.")
    editor = add_task("Greet the user.")
    set_floor_allow(get_db(), skipper, ["skip"])
    set_floor_allow(get_db(), editor, ["task-edit"])
    steps = {
        skipper: [write("tests/test_sample.py", SKIPPED_TEST)],
        editor: [lambda repo: set_text(editor, "Greet nobody.")],
    }
    agent = Agent(repo, steps)

    raw, _ = drain(state, agent)

    assert sorted(raw["completed"]) == sorted([skipper, editor])
    assert len(agent.prompts[skipper]) == len(agent.prompts[editor]) == 1
    assert {p["floor"] for p in proofs(state)} == {"clean"}


def test_with_the_floor_off_the_skip_passes(tmp_path):
    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("floor.enabled", "false")
    tid = add_task("Greet.")
    agent = Agent(repo, {tid: [write("tests/test_sample.py", SKIPPED_TEST)]})

    raw, _ = drain(state, agent)

    assert raw["completed"] == [tid]
    assert [p["floor"] for p in proofs(state)] == ["off"]


def test_a_task_that_edits_a_plan_file_is_retried_with_plan_edit(tmp_path):
    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "2")
    tid = add_task("Greet.")
    seen: dict = {}

    def first_attempt(repo: Path) -> None:
        write(PLAN, "# Plan\n\n- build something else\n")(repo)
        feedback = "pathly/features/proof-feat/goals/g1/feedback/NOTE.md"
        write(feedback, "a note for the planner\n")(repo)

    def second_attempt(repo: Path) -> None:
        seen["fail_reason"] = row(tid)["fail_reason"]

    drain(state, Agent(repo, {tid: [first_attempt, second_attempt]}))

    assert "plan-edit: %s" % PLAN in seen["fail_reason"]
    assert "NOTE.md" not in seen["fail_reason"]


# ── The task text ────────────────────────────────────────────────────────────


def test_a_task_that_edits_its_own_text_is_retried_with_task_edit(tmp_path):
    repo = make_repo(tmp_path)
    state = State(repo)
    set_app_setting("goal.task_max_attempts", "2")
    original = "Greet the user."
    tid = add_task(original)
    seen: dict = {}

    def second_attempt(repo: Path) -> None:
        seen["fail_reason"] = row(tid)["fail_reason"]
        set_text(tid, original)

    steps = {tid: [lambda repo: set_text(tid, "Greet nobody."), second_attempt]}
    agent = Agent(repo, steps)

    raw, _ = drain(state, agent)

    assert "task-edit" in seen["fail_reason"]
    assert "task-edit" in agent.prompts[tid][1]
    assert original in agent.prompts[tid][1]
    assert "Greet nobody." not in agent.prompts[tid][1]
    assert raw["completed"] == [tid]
