"""``task_checks``: wiring, report shape, re-runs and fail-open (build-proof 07).

The main cases are in ``test_task_checks_gate.py``. These pin where the packaged flows carry the
gate, what the failure file looks like, when a proven claim is run again, and that a measurement
the gate cannot make skips it instead of wedging the run.
"""

from __future__ import annotations

import pytest
from task_checks_support import (
    FEEDBACK,
    GATE,
    PLAIN,
    _claim,
    _enter_building,
    _storage,
    blocked,
    claim_again,
    complete,
    counting,
    drained_goal_loop,
    eventlog,
    failed_gate,
    flow,
    green,
    join,
    load,
    proofs,
    red,
    repo,
    review_passes,
    set_text,
    skipped,
)

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms_tasks import complete_task
from pathly_orchestrator.db.queries.task_proof import set_floor_allow


def test_the_gate_is_registered():
    from pathly_orchestrator.fsm.gates import _CHECKS
    from pathly_orchestrator.fsm.gates.task_checks import check_task_checks

    assert _CHECKS["task_checks"] is check_task_checks


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_team_flows_carry_the_gate_at_the_joins(name):
    gates = load(name)["gates"]

    types = [g["type"] for g in gates["BUILDING->REVIEWING"]]
    assert types.index("task_checks") == types.index("floor_gate") + 1
    assert types[-1] == "scope_gate"
    types = [g["type"] for g in gates["REVIEWING->TESTING"]]
    assert types.index("task_checks") == types.index("floor_gate") + 1
    assert types[-1] == "reviewer_unchanged"
    assert types[0] == "verify_gate"
    assert [g["type"] for g in gates["->DONE"]] == [
        "require_tasks_done",
        "floor_gate",
        "task_checks",
    ]
    for edge in ("BUILDING->REVIEWING", "REVIEWING->TESTING", "->DONE"):
        assert GATE in gates[edge], edge
    for edge in ("TESTING->RETRO", "REVIEWING->BUILDING"):
        assert GATE not in gates[edge], edge
    assert load(name)["feedback_routing"]["TASK_CHECK_FAILURES"] == "builder"


def test_goal_loop_carries_the_gate_last():
    flow = load("goal-loop")

    assert [g["type"] for g in flow["gates"]["DRAINING->DONE"]] == [
        "require_tasks_done",
        "command_gate",
        "command_gate",
        "floor_gate",
        "task_checks",
    ]
    assert flow["gates"]["DRAINING->DONE"][-1] == GATE
    assert flow["feedback_routing"]["TASK_CHECK_FAILURES"] == "builder"


@pytest.mark.parametrize("name", ["team", "team-build"])
def test_the_exit_requirement_says_the_checks_are_run_by_the_supervisor(name):
    from pathly_orchestrator.fsm_compose_responses import _exit_requirement

    text = _exit_requirement(load(name), "BUILDING") or ""

    assert "check block" in text
    assert "run by the supervisor" in text
    assert "self-reported pass does not count" in text


def test_the_failure_has_one_section_per_failing_task(repo, flow):
    _enter_building(repo, flow)
    ids = [
        _claim(red("Red one.", "marker-one")),
        _claim(green("Green one.")),
        _claim(red("Red two.", "marker-two")),
    ]
    for task_id in ids:
        complete_task(get_db(), task_id)

    text = blocked(complete(repo), repo)

    assert text.count("\n## Task ") == 2
    assert "Red one." in text and "marker-one" in text
    assert "Red two." in text and "marker-two" in text
    assert "Green one." not in text and "green-marker" not in text
    assert [p["checks"] for p in proofs(repo, ids[1])] == ["passed"]
    assert failed_gate(repo)["count"] == 2


def test_a_failed_proof_is_run_again_at_the_next_attempt(repo, flow, tmp_path):
    log = tmp_path / "ran.log"
    _enter_building(repo, flow)
    task_id = _claim(counting("Stubborn task.", log, code=1))
    complete_task(get_db(), task_id)

    blocked(complete(repo), repo)
    blocked(complete(repo, resolved_files=[FEEDBACK]), repo)

    assert log.read_text() == "xx"
    assert [p["checks"] for p in proofs(repo, task_id)] == ["failed", "failed"]


def test_a_task_claimed_again_is_run_again(repo, flow, tmp_path):
    log = tmp_path / "ran.log"
    _enter_building(repo, flow)
    task_id = _claim(counting("Reopened task.", log))
    complete_task(get_db(), task_id)
    assert complete(repo).get("next_state") == "REVIEWING"
    assert log.read_text() == "x"

    # A human re-opens the task and a builder claims it again: a new claim to prove.
    claim_again(task_id)
    complete_task(get_db(), task_id)
    review_passes(repo, flow)

    assert complete(repo).get("next_state") == "TESTING"
    assert log.read_text() == "xx"
    assert len(proofs(repo, task_id)) == 2


def test_goal_loop_join_passes_when_every_task_is_proven_or_passes(repo):
    drained_goal_loop(repo, green(), PLAIN)

    assert join(repo) == {"done": True}


def test_goal_loop_join_runs_the_checks_again_after_a_human_refreezes_the_text(repo):
    [broken] = drained_goal_loop(repo, red())
    blocked(join(repo), repo)
    set_text(broken, green())
    set_floor_allow(get_db(), broken, [], refreeze=True)

    assert join(repo, resolved_files=[FEEDBACK]) == {"done": True}


def test_a_run_with_no_proof_base_skips_the_gate(repo, flow):
    _enter_building(repo, flow)
    task_id = _claim(red())
    complete_task(get_db(), task_id)
    state = eventlog.read_state(str(_storage(repo)))
    state.pop("proof_base")
    eventlog.write_state(str(_storage(repo)), state, flow)

    assert complete(repo).get("next_state") == "REVIEWING"

    assert skipped(repo) == ["no_proof_base"]
    assert not proofs(repo, task_id)


def test_unreadable_tasks_skip_the_gate(repo, flow, monkeypatch):
    from pathly_orchestrator.db.queries import task_proof

    def broken(*_args, **_kwargs):
        raise RuntimeError("db down")

    _enter_building(repo, flow)
    complete_task(get_db(), _claim(red()))
    monkeypatch.setattr(task_proof, "tasks_completed_since", broken)

    assert complete(repo).get("next_state") == "REVIEWING"

    assert skipped(repo) == ["tasks_unreadable"]


def test_a_base_without_a_readable_time_skips_the_gate(repo, flow):
    _enter_building(repo, flow)
    complete_task(get_db(), _claim(red()))
    state = eventlog.read_state(str(_storage(repo)))
    state["proof_base"]["started_at"] = "not a time"
    eventlog.write_state(str(_storage(repo)), state, flow)

    assert complete(repo).get("next_state") == "REVIEWING"

    assert skipped(repo) == ["tasks_unreadable"]
