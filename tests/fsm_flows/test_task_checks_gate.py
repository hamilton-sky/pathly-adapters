"""``task_checks`` runs each completed task's check block at the joins (build-proof 07).

A team-flow builder claims a board task, does it and completes it itself, so the supervisor never
sees per-task success. The gate runs at every join a completion can precede: it takes the tasks
completed since the run-wide ``proof_base``, drops those whose newest ``TASK_PROOF`` already
proved their current claim, and runs the rest from the text frozen at the claim. Every case
drives the real ``next_action`` and ``complete_stage`` over the packaged flows in a ``git init``
project; setup is in ``task_checks_support`` and ``review_packet_support``.
"""

from __future__ import annotations

import pytest
from task_checks_support import (
    FEEDBACK,
    PLAIN,
    _claim,
    _enter_building,
    _storage,
    blocked,
    builder_edit,
    complete,
    counting,
    drained_goal_loop,
    eventlog,
    events,
    failed_gate,
    flow,
    green,
    join,
    proofs,
    red,
    repo,
    review_passes,
    set_text,
    to_retro,
)

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms_tasks import complete_task
from pathly_orchestrator.db.queries.task_proof import get_task, set_floor_allow
from pathly_orchestrator.fsm.gates._proof_record import record_task_proof
from pathly_orchestrator.proof.checks import ParseError, checks_in

MALFORMED = "Make x two.\n\n```check\nprints something\n```\n"


def test_a_failing_check_blocks_building_and_the_frozen_text_is_what_runs(repo, flow):
    _enter_building(repo, flow)
    task_id = _claim(red())
    builder_edit(repo, flow)
    complete_task(get_db(), task_id)

    text = blocked(complete(repo), repo)

    assert "got: exit 1" in text
    assert "red-marker" in text
    assert "wanted: exit 0" in text
    assert "text the task had when it was claimed" in text
    assert task_id in text
    assert eventlog.read_state(str(_storage(repo)))["current"] == "BUILDING"
    assert failed_gate(repo)["transition"] == "BUILDING->REVIEWING"
    [proof] = proofs(repo, task_id)
    assert (proof["checks"], proof["floor"]) == ("failed", "n/a")
    assert proof["run_id"] == "gate:BUILDING->REVIEWING"

    # The builder rewrites the live text to a passing check, and a human lets the edit through
    # the floor gate. The checks still run from the text frozen at the claim.
    set_text(task_id, green())
    set_floor_allow(get_db(), task_id, ["task-edit"])

    again = blocked(complete(repo, resolved_files=[FEEDBACK]), repo)

    assert "got: exit 1" in again
    assert [p["checks"] for p in proofs(repo, task_id)] == ["failed", "failed"]


def test_a_task_first_completed_in_reviewing_blocks_reviewing_to_testing(repo, flow):
    _enter_building(repo, flow)
    task_id = _claim(red())
    builder_edit(repo, flow)
    assert complete(repo).get("next_state") == "REVIEWING"
    assert not proofs(repo, task_id), "an unfinished task has nothing to run"
    review_passes(repo, flow)
    # The INCOMPLETE_TASKS fix round: the builder finishes the task while the FSM sits in REVIEWING.
    complete_task(get_db(), task_id)

    text = blocked(complete(repo), repo)

    assert "got: exit 1" in text
    assert eventlog.read_state(str(_storage(repo)))["current"] == "REVIEWING"
    assert failed_gate(repo)["transition"] == "REVIEWING->TESTING"
    assert [p["run_id"] for p in proofs(repo, task_id)] == ["gate:REVIEWING->TESTING"]


def test_a_task_completed_in_retro_blocks_retro_to_done(repo, flow):
    to_retro(repo, flow)
    late = _claim(red())
    complete_task(get_db(), late)

    text = blocked(complete(repo), repo)

    assert "got: exit 1" in text
    assert eventlog.read_state(str(_storage(repo)))["current"] == "RETRO"
    assert failed_gate(repo)["transition"] == "RETRO->DONE"

    # A human corrects the check: the live text is fixed and re-frozen. The failed proof is not a
    # proven claim, so the join runs the checks again, from the new text.
    set_text(late, green())
    set_floor_allow(get_db(), late, [], refreeze=True)

    assert complete(repo, resolved_files=[FEEDBACK]) == {"done": True}
    assert [p["checks"] for p in proofs(repo, late)] == ["failed", "passed"]


def test_a_passing_check_is_recorded_and_not_run_again_at_the_next_join(
    repo, flow, tmp_path
):
    log = tmp_path / "ran.log"
    _enter_building(repo, flow)
    task_id = _claim(counting("Counted task.", log))
    builder_edit(repo, flow)
    complete_task(get_db(), task_id)

    assert complete(repo).get("next_state") == "REVIEWING"
    assert log.read_text() == "x"
    review_passes(repo, flow)
    assert complete(repo).get("next_state") == "TESTING"

    assert log.read_text() == "x", "the second join ran the checks again"
    [proof] = proofs(repo, task_id)
    assert (proof["checks"], proof["floor"]) == ("passed", "n/a")
    assert proof["claimed_at"] == get_task(get_db(), task_id)["claimed_at"]


def test_goal_loop_join_skips_a_proven_task_and_runs_one_without_a_proof(
    repo, tmp_path
):
    proven_log = tmp_path / "proven.log"
    proven, fixed = drained_goal_loop(
        repo, counting("Proven in the drain.", proven_log, code=1), red("Fix round.")
    )
    # The drain proved the first task for its current claim; the second was completed by a fix round.
    record_task_proof(
        _storage(repo),
        get_task(get_db(), proven),
        "sched-%s#1" % proven,
        "passed",
        "clean",
    )

    text = blocked(join(repo), repo)

    assert "Fix round." in text and "red-marker" in text
    assert "Proven in the drain." not in text
    assert not proven_log.exists(), "a proven task's checks ran again"
    assert len(proofs(repo, proven)) == 1
    assert [p["checks"] for p in proofs(repo, fixed)] == ["failed"]
    assert proofs(repo, fixed)[0]["run_id"] == "gate:DRAINING->DONE"
    assert eventlog.read_state(str(_storage(repo)))["current"] == "DRAINING"


def test_a_task_without_a_block_passes_and_leaves_none(repo, flow):
    _enter_building(repo, flow)
    task_id = _claim(PLAIN)
    builder_edit(repo, flow)
    complete_task(get_db(), task_id)

    assert complete(repo).get("next_state") == "REVIEWING"

    [proof] = proofs(repo, task_id)
    assert (proof["checks"], proof["floor"]) == ("none", "n/a")
    assert proof["run_id"] == "gate:BUILDING->REVIEWING"
    assert not [e for e in events(repo, "GATE_FAILED") if e["gate"] == "task_checks"]


def test_a_malformed_block_fails_with_the_parsers_message(repo, flow):
    with pytest.raises(ParseError) as caught:
        checks_in(MALFORMED)
    _enter_building(repo, flow)
    task_id = _claim(MALFORMED)
    complete_task(get_db(), task_id)

    text = blocked(complete(repo), repo)

    assert str(caught.value) in text
    assert [p["checks"] for p in proofs(repo, task_id)] == ["error"]


def test_a_task_completed_before_the_run_began_is_not_run(repo, flow):
    old = _claim(red("Old task."))
    complete_task(get_db(), old)
    _enter_building(repo, flow)
    fresh = _claim(green())
    builder_edit(repo, flow)
    complete_task(get_db(), fresh)

    assert complete(repo).get("next_state") == "REVIEWING"

    assert not proofs(repo, old)
    assert [p["checks"] for p in proofs(repo, fresh)] == ["passed"]
