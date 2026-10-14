"""build-proof 10: the Review packet's supervisor notes, the runner-contract sentence, the skills.

The notes list each claimed task's latest ``TASK_PROOF`` and the warnings of the latest
``FLOOR_CHECKED`` since the build began. ``RUNNER_CONTRACT_BLOCK`` tells every headless stage not
to spawn another Pathly role for a feedback file, and ``team/review`` pastes the packet instead of
asking the reviewer to run anything. Setup is in ``review_packet_support``.
"""

from __future__ import annotations

import pytest
from _paths import SRC
from review_packet_support import (
    _args,
    _build,
    _packet,
    _section,
    _storage,
    _task_proof,
    flow,
    repo,
)

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.fsm_compose import RUNNER_CONTRACT_BLOCK

NO_CHECK = "no check block: review its acceptance by reading the code"
SKILLS = SRC / "pathly_data" / "core" / "skills"


# --- supervisor notes --------------------------------------------------------------------


def test_the_notes_say_none_recorded_when_nothing_was_recorded(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))

    notes = _section(_packet(repo), "Supervisor notes")

    assert "none recorded" in notes


@pytest.mark.parametrize(
    "checks, wanted",
    [
        ("passed", "checks passed"),
        ("failed", "checks failed"),
        ("none", NO_CHECK),
    ],
)
def test_the_notes_report_each_tasks_latest_check_result(repo, flow, checks, wanted):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    _task_proof(repo, task_id, checks)

    notes = _section(_packet(repo), "Supervisor notes")

    assert task_id[:8] in notes
    assert wanted in notes
    assert "none recorded" not in notes


def test_the_notes_use_the_latest_task_proof_of_a_task(repo, flow):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    _task_proof(repo, task_id, "failed")
    _task_proof(repo, task_id, "passed")

    notes = _section(_packet(repo), "Supervisor notes")

    assert "checks passed" in notes
    assert "checks failed" not in notes


def test_the_notes_ignore_a_task_proof_from_before_the_build(repo, flow):
    task_id = _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    _task_proof(repo, task_id, "failed", ts="2020-01-01T00:00:00Z")

    notes = _section(_packet(repo), "Supervisor notes")

    assert "checks failed" not in notes
    assert "none recorded" in notes


def test_the_notes_carry_the_warnings_of_the_latest_floor_check(repo, flow):
    _build(repo, flow)
    fsm_ops.complete_stage(_args(repo))
    eventlog.append_event(
        str(_storage(repo)),
        {"type": "FLOOR_CHECKED", "warnings": ["OLDER-WARNING"]},
    )
    eventlog.append_event(
        str(_storage(repo)),
        {"type": "FLOOR_CHECKED", "warnings": ["fewer assertions in tests/test_a.py"]},
    )

    notes = _section(_packet(repo), "Supervisor notes")

    assert "fewer assertions in tests/test_a.py" in notes
    assert "OLDER-WARNING" not in notes
    assert "none recorded" not in notes


# --- the runner contract and the skills --------------------------------------------------


def test_the_runner_contract_forbids_spawning_a_role_for_a_feedback_file():
    assert "{" not in RUNNER_CONTRACT_BLOCK and "}" not in RUNNER_CONTRACT_BLOCK
    for part in (
        "never spawn another Pathly role",
        "planner, architect, po, designer, builder",
        "to resolve a feedback file",
        "write the feedback file and stop",
        "the supervisor routes it",
    ):
        assert part in RUNNER_CONTRACT_BLOCK, part


def test_team_review_pastes_the_packet_and_never_asks_the_reviewer_to_run_anything():
    text = (SKILLS / "team/review.md").read_text(encoding="utf-8")

    assert "git diff HEAD~1 HEAD" not in text
    assert "git diff --staged" not in text
    assert "### The task" in text and "### The diff" in text
    assert "VERIFY.md" in text  # named only to say it is never passed on
    assert "Never pass" in text
