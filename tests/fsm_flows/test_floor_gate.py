"""``floor_gate`` sends a build that weakened the bar back to the builder (build-proof 06).

The gate diffs the working tree against the run-wide ``proof_base`` (stamped by
``fsm_ops.next_action``, kept until DONE) and runs the floor scan over it, so a builder fix round
inside REVIEWING, TESTING, RETRO or after a goal-loop drain is judged at the next transition.
Every case drives the real ``next_action`` and ``complete_stage`` over the packaged flows in a
``git init`` project; setup is in ``review_packet_support``.
"""

from __future__ import annotations

from importlib.resources import files
from types import SimpleNamespace

import pytest
import yaml
from review_packet_support import (
    FEATURE,
    _args,
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
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task, complete_task
from pathly_orchestrator.db.queries.task_proof import set_floor_allow
from pathly_orchestrator.supervisor import spawn_window

TESTS = "tests/test_calc.py"
STORIES = FEATURE + "/USER_STORIES.md"
REVIEW = FEATURE + "/REVIEW.md"
CLEAN = "def test_calc():\n    assert 1 + 1 == 2\n"
SKIPPED = "import pytest\n\n\n@pytest.mark.skip\n" + CLEAN
FEEDBACK = "FLOOR_FAILURES.md"


@pytest.fixture
def proj(repo):
    """The shared project plus a committed test file and a committed plan document."""
    _write(repo, TESTS, CLEAN)
    _write(repo, STORIES, "# Stories\n- one\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "tests and stories")
    return repo


def _load(name: str) -> dict:
    text = (
        files("pathly_data")
        .joinpath("core/flows/%s.flow.yaml" % name)
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _complete(repo, name: str = "team-build", **extra) -> dict:
    return fsm_ops.complete_stage({**_args(repo), "flow": name, **extra})


def _as(repo, flow, role: str, state: str, work) -> None:
    """Run ``work()`` as a spawn of ``role`` in ``state``, recording its SPAWN_WINDOW."""
    ns = SimpleNamespace(
        project_root=str(repo),
        topic="demo",
        storage_path=str(_storage(repo)),
        current_state=state,
    )
    spawn_window.observe(ns, flow, role, "run-%s-%s" % (role, state), work)


def _edit(repo, rel: str, text: str):
    return lambda: _write(repo, rel, text)


def _feedback(repo) -> str:
    return (_storage(repo) / "feedback" / FEEDBACK).read_text(encoding="utf-8")


def _events(repo, kind: str) -> list[dict]:
    return [e for e in eventlog.read_events(str(_storage(repo))) if e["type"] == kind]


def _assert_floor_block(result: dict, repo) -> str:
    assert result.get("blocked") is True, result
    assert result["target_agent"] == "builder"
    assert result["file"] == FEEDBACK
    return _feedback(repo)


def _to(repo, flow, state: str) -> str:
    """Build cleanly, then advance through every gate up to ``state``. Returns the task id."""
    _enter_building(repo, flow)
    task_id = _claim()
    _as(repo, flow, "builder", "BUILDING", _edit(repo, "src/app.py", "x = 2\ny = 2\n"))
    for current, following in (
        ("BUILDING", "REVIEWING"),
        ("REVIEWING", "TESTING"),
        ("TESTING", "RETRO"),
    ):
        if current == "REVIEWING":
            _as(
                repo,
                flow,
                "reviewer",
                "REVIEWING",
                _edit(repo, REVIEW, "RESULT: PASS\nClean.\n"),
            )
            complete_task(get_db(), task_id)
        moved = _complete(repo)
        assert moved.get("next_state") == following, moved
        if following == state:
            break
    return task_id


# --- the packaged flows ------------------------------------------------------------------


def test_the_gate_is_registered():
    from pathly_orchestrator.fsm.gates import _CHECKS
    from pathly_orchestrator.fsm.gates.floor import check_floor_gate

    assert _CHECKS["floor_gate"] is check_floor_gate


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_team_flows_carry_the_gate_on_every_edge_out_of_a_stage(name):
    flow = _load(name)
    gate = {"type": "floor_gate", "on_fail": "FLOOR_FAILURES.md"}
    for edge in (
        "BUILDING->REVIEWING",
        "REVIEWING->TESTING",
        "TESTING->RETRO",
        "->DONE",
    ):
        assert gate in flow["gates"][edge], edge
    assert gate not in flow["gates"]["REVIEWING->BUILDING"]
    assert flow["feedback_routing"]["FLOOR_FAILURES"] == "builder"
    # New gates go before the last gate each edge already pins.
    assert flow["gates"]["BUILDING->REVIEWING"][-1]["type"] == "scope_gate"
    assert flow["gates"]["REVIEWING->TESTING"][-1]["type"] == "reviewer_unchanged"
    assert flow["gates"]["REVIEWING->TESTING"][0]["type"] == "verify_gate"
    assert [g["type"] for g in flow["gates"]["->DONE"]] == [
        "require_tasks_done",
        "floor_gate",
    ]


def test_goal_loop_carries_the_gate_after_the_command_gates():
    flow = _load("goal-loop")
    assert [g["type"] for g in flow["gates"]["DRAINING->DONE"]] == [
        "require_tasks_done",
        "command_gate",
        "command_gate",
        "floor_gate",
    ]
    assert flow["gates"]["DRAINING->DONE"][-1]["on_fail"] == "FLOOR_FAILURES.md"
    assert flow["feedback_routing"]["FLOOR_FAILURES"] == "builder"


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_exit_requirement_says_the_diff_is_scanned(name):
    from pathly_orchestrator.fsm_compose_responses import _exit_requirement

    text = _exit_requirement(_load(name), "BUILDING") or ""
    assert "weakened tests" in text
    assert "silenced checks" in text
    assert "plan edits" in text


# --- team-build ------------------------------------------------------------------------


def test_a_skip_blocks_building_and_passes_once_a_human_allows_it(proj, flow):
    _enter_building(proj, flow)
    task_id = _claim()
    _as(proj, flow, "builder", "BUILDING", _edit(proj, TESTS, SKIPPED))

    blocked = _complete(proj)

    text = _assert_floor_block(blocked, proj)
    assert text.startswith(
        "Floor guard: the diff weakens the bar instead of meeting it"
    )
    assert "skip: %s" % TESTS in text
    assert "POST /comms/tasks/floor-allow" in text
    assert "floor.enabled" in text
    assert eventlog.read_state(str(_storage(proj)))["current"] == "BUILDING"
    gate = [e for e in _events(proj, "GATE_FAILED") if e["gate"] == "floor_gate"]
    assert gate and gate[-1]["transition"] == "BUILDING->REVIEWING"
    assert _events(proj, "FLOOR_CHECKED"), "the floor check is recorded either way"

    assert set_floor_allow(get_db(), task_id, ["skip"])
    moved = _complete(proj, resolved_files=[FEEDBACK])

    assert moved.get("next_state") == "REVIEWING", moved
    assert len(_events(proj, "FLOOR_CHECKED")) == 2


def test_a_clean_build_passes_and_records_the_check(proj, flow):
    _enter_building(proj, flow)
    _claim()
    _as(proj, flow, "builder", "BUILDING", _edit(proj, "src/app.py", "x = 2\ny = 2\n"))

    moved = _complete(proj)

    assert moved.get("next_state") == "REVIEWING", moved
    assert _events(proj, "FLOOR_CHECKED")[-1]["warnings"] == []
    assert not [e for e in _events(proj, "GATE_FAILED") if e["gate"] == "floor_gate"]


def test_a_changed_task_text_is_a_task_edit_unless_a_human_allows_it(proj, flow):
    _enter_building(proj, flow)
    task_id = _claim()
    get_db().execute(
        "UPDATE comms_messages SET text=? WHERE id=?", ("Easier task.\n", task_id)
    )
    get_db().commit()

    text = _assert_floor_block(_complete(proj), proj)

    assert "task-edit: task %s" % task_id in text

    set_floor_allow(get_db(), task_id, ["task-edit"])
    assert _complete(proj, resolved_files=[FEEDBACK]).get("next_state") == "REVIEWING"


def test_a_plan_edit_blocks_unless_a_planner_window_explains_it(proj, flow):
    _enter_building(proj, flow)
    _claim()
    _as(proj, flow, "builder", "BUILDING", _edit(proj, STORIES, "# Stories\n- none\n"))

    text = _assert_floor_block(_complete(proj), proj)

    assert "plan-edit: %s" % STORIES in text


def test_a_plan_edit_by_a_planner_spawn_is_accepted(proj, flow):
    _enter_building(proj, flow)
    _claim()
    _as(proj, flow, "planner", "BUILDING", _edit(proj, STORIES, "# Stories\n- two\n"))
    _as(proj, flow, "builder", "BUILDING", _edit(proj, "src/app.py", "x = 2\ny = 2\n"))

    moved = _complete(proj)

    assert moved.get("next_state") == "REVIEWING", moved


def test_a_builder_edit_after_the_planner_is_still_a_plan_edit(proj, flow):
    _enter_building(proj, flow)
    _claim()
    _as(proj, flow, "planner", "BUILDING", _edit(proj, STORIES, "# Stories\n- two\n"))
    _as(proj, flow, "builder", "BUILDING", _edit(proj, STORIES, "# Stories\n- gone\n"))

    text = _assert_floor_block(_complete(proj), proj)

    assert "plan-edit: %s" % STORIES in text


def test_a_skip_added_in_reviewing_blocks_reviewing_to_testing(proj, flow):
    task_id = _to(proj, flow, "REVIEWING")
    _as(proj, flow, "reviewer", "REVIEWING", _edit(proj, REVIEW, "RESULT: PASS\n"))
    complete_task(get_db(), task_id)
    # A builder fix round inside REVIEWING weakens a test: the FSM is still in REVIEWING.
    _as(proj, flow, "builder", "REVIEWING", _edit(proj, TESTS, SKIPPED))

    text = _assert_floor_block(_complete(proj), proj)

    assert "skip: %s" % TESTS in text
    assert eventlog.read_state(str(_storage(proj)))["current"] == "REVIEWING"
    failed = [e for e in _events(proj, "GATE_FAILED") if e["gate"] == "floor_gate"]
    assert failed[-1]["transition"] == "REVIEWING->TESTING"


def test_a_skip_added_in_retro_blocks_retro_to_done(proj, flow):
    _to(proj, flow, "RETRO")
    assert eventlog.read_state(str(_storage(proj)))["current"] == "RETRO"
    _as(proj, flow, "builder", "RETRO", _edit(proj, TESTS, SKIPPED))

    text = _assert_floor_block(_complete(proj), proj)

    assert "skip: %s" % TESTS in text
    assert eventlog.read_state(str(_storage(proj)))["current"] == "RETRO"
    failed = [e for e in _events(proj, "GATE_FAILED") if e["gate"] == "floor_gate"]
    assert failed[-1]["transition"] == "RETRO->DONE"

    _as(proj, flow, "builder", "RETRO", _edit(proj, TESTS, CLEAN))
    assert _complete(proj, resolved_files=[FEEDBACK]) == {"done": True}


def test_a_claimed_tasks_allow_list_covers_the_whole_run(proj, flow):
    """The skip is made in BUILDING, so it is still in the diff at the next gate."""
    _enter_building(proj, flow)
    task_id = _claim()
    _as(proj, flow, "builder", "BUILDING", _edit(proj, TESTS, SKIPPED))
    set_floor_allow(get_db(), task_id, ["skip"])
    assert _complete(proj).get("next_state") == "REVIEWING"
    _as(proj, flow, "reviewer", "REVIEWING", _edit(proj, REVIEW, "RESULT: PASS\n"))
    complete_task(get_db(), task_id)

    moved = _complete(proj)

    assert moved.get("next_state") == "TESTING", moved


def test_floor_enabled_false_skips_the_gate(proj, flow):
    set_setting(get_db(), "floor.enabled", "false")
    _enter_building(proj, flow)
    _claim()
    _as(proj, flow, "builder", "BUILDING", _edit(proj, TESTS, SKIPPED))

    moved = _complete(proj)

    assert moved.get("next_state") == "REVIEWING", moved
    skipped = [e for e in _events(proj, "GATE_SKIPPED") if e["gate"] == "floor_gate"]
    assert skipped and skipped[-1]["reason"] == "floor_disabled"
    assert not _events(proj, "FLOOR_CHECKED")


def test_a_run_with_no_proof_base_skips_the_gate(proj, flow):
    _enter_building(proj, flow)
    _claim()
    state = eventlog.read_state(str(_storage(proj)))
    state.pop("proof_base")
    eventlog.write_state(str(_storage(proj)), state, flow)
    _as(proj, flow, "builder", "BUILDING", _edit(proj, TESTS, SKIPPED))

    moved = _complete(proj)

    assert moved.get("next_state") == "REVIEWING", moved
    skipped = [e for e in _events(proj, "GATE_SKIPPED") if e["gate"] == "floor_gate"]
    assert skipped and skipped[-1]["reason"] == "no_proof_base"


def test_a_base_without_a_tree_skips_the_gate(proj, flow):
    _enter_building(proj, flow)
    _claim()
    state = eventlog.read_state(str(_storage(proj)))
    state["proof_base"]["tree"] = None
    eventlog.write_state(str(_storage(proj)), state, flow)
    _as(proj, flow, "builder", "BUILDING", _edit(proj, TESTS, SKIPPED))

    moved = _complete(proj)

    assert moved.get("next_state") == "REVIEWING", moved
    skipped = [e for e in _events(proj, "GATE_SKIPPED") if e["gate"] == "floor_gate"]
    assert skipped and skipped[-1]["reason"] == "no_snapshot"


# --- goal-loop -------------------------------------------------------------------------


def _drained_goal_loop(repo) -> None:
    """A clean drain: DRAINING entered, one goal task claimed, edited and done."""
    goal_flow = _load("goal-loop")
    eventlog.write_state(str(_storage(repo)), {"current": "DRAINING"}, goal_flow)
    fsm_ops.next_action({**_args(repo), "flow": "goal-loop", "goal_id": "g1"})
    assert eventlog.read_state(str(_storage(repo)))["proof_base"]["tree"]
    conn = get_db()
    task_id = post_message(
        conn,
        board="feature",
        scope="demo",
        from_agent="planner",
        type="task",
        text="Make x two.\n",
        goal_id="g1",
    )
    assert claim_task(conn, task_id, "sched-%s#1" % task_id)
    _write(repo, "src/app.py", "x = 2\ny = 2\n")
    complete_task(conn, task_id)


def test_goal_loop_join_blocks_a_skip_a_fix_round_wrote(proj):
    _drained_goal_loop(proj)
    # A builder fix round after the drain (BUILD_FAILURES / TEST_FAILURES routed to builder).
    _write(proj, TESTS, SKIPPED)

    blocked = _complete(proj, "goal-loop", goal_id="g1")

    text = _assert_floor_block(blocked, proj)
    assert "skip: %s" % TESTS in text
    assert eventlog.read_state(str(_storage(proj)))["current"] == "DRAINING"

    _write(proj, TESTS, CLEAN)
    done = _complete(proj, "goal-loop", goal_id="g1", resolved_files=[FEEDBACK])

    assert done == {"done": True}


def test_goal_loop_join_passes_a_clean_drain(proj):
    _drained_goal_loop(proj)

    assert _complete(proj, "goal-loop", goal_id="g1") == {"done": True}
    assert _events(proj, "FLOOR_CHECKED")
