"""``task_checks``: one runner, one clip, the right action line, one event read (build-proof 07).

The goal-loop drain's task proof and the join gate must mean the same thing by "this task's
checks passed", so they share one runner (``proof.checks.run_task_checks``) and one head-and-tail
clip (``proof.command.clip_to``). A block that cannot be read is a failure no builder can fix, so
its feedback sends the builder to a human instead of to the code. And the gate reads the event log
once per run, not once per completed task.
"""

from __future__ import annotations

import json
import sys

import pytest
from task_checks_support import (
    GATE,
    PLAIN,
    _claim,
    _enter_building,
    _storage,
    blocked,
    complete,
    counting,
    eventlog,
    flow,
    proofs,
    red,
    repo,
)

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms_tasks import complete_task
from pathly_orchestrator.fsm.gates import task_checks
from pathly_orchestrator.proof import checks, command
from pathly_orchestrator.proof.checks import ParseError, checks_in
from pathly_orchestrator.supervisor import task_proof

MALFORMED = "Make x two.\n\n```check\nprints something\n```\n"


def _block(code: str) -> str:
    """Task text with one check block that runs ``code`` in this interpreter."""
    return "Do it.\n\n```check\n$ %s\n```\n" % json.dumps([sys.executable, "-c", code])


# -- one copy ----------------------------------------------------------------


def test_the_gate_and_the_drain_proof_share_one_runner_and_one_clip():
    assert task_checks.run_task_checks is checks.run_task_checks
    assert task_proof.run_task_checks is checks.run_task_checks
    assert task_checks.clip_to is command.clip_to
    assert task_proof.clip_to is command.clip_to


def test_run_task_checks_passes_a_green_block(tmp_path):
    task = {"id": "t1", "claimed_text": _block("print('ok')"), "text": "other"}

    assert checks.run_task_checks(task, tmp_path, 30) == ("passed", "")


def test_run_task_checks_fails_a_red_block_with_the_report(tmp_path):
    task = {"id": "t1", "claimed_text": _block("raise SystemExit(3)")}

    result, report = checks.run_task_checks(task, tmp_path, 30)

    assert result == "failed"
    assert "got: exit 3" in report


def test_run_task_checks_runs_the_frozen_text_not_the_live_one(tmp_path):
    task = {
        "id": "t1",
        "claimed_text": _block("raise SystemExit(1)"),
        "text": _block("print('edited to pass')"),
    }

    assert checks.run_task_checks(task, tmp_path, 30)[0] == "failed"


def test_run_task_checks_falls_back_to_the_live_text_for_an_old_claim(tmp_path):
    task = {"id": "t1", "claimed_text": None, "text": _block("raise SystemExit(1)")}

    assert checks.run_task_checks(task, tmp_path, 30)[0] == "failed"


def test_run_task_checks_leaves_none_for_text_without_a_block(tmp_path):
    assert checks.run_task_checks({"id": "t1", "text": PLAIN}, tmp_path, 30) == (
        "none",
        "",
    )


def test_run_task_checks_quotes_the_parsers_message_for_an_unreadable_block(tmp_path):
    with pytest.raises(ParseError) as caught:
        checks_in(MALFORMED)

    result, report = checks.run_task_checks(
        {"id": "t1", "claimed_text": MALFORMED}, tmp_path, 30
    )

    assert result == "error"
    assert report == ("The check block in this task cannot be read: %s" % caught.value)


def test_clip_to_leaves_short_text_alone():
    assert command.clip_to("short", 50) == "short"


def test_clip_to_keeps_the_head_and_the_tail_in_the_limit():
    text = "H" * 50 + "M" * 100 + "T" * 50

    clipped = command.clip_to(text, 60)

    assert len(clipped) == 60
    assert clipped.startswith("H") and clipped.endswith("T")
    assert "(clipped)" in clipped
    assert clipped.count("T") > clipped.count("H"), "the summary is at the end"


def test_clip_to_survives_a_limit_smaller_than_its_marker():
    assert "(clipped)" in command.clip_to("x" * 100, 5)


# -- the action line ---------------------------------------------------------


def _complete_all(*texts: str) -> list[str]:
    ids = [_claim(text) for text in texts]
    for task_id in ids:
        complete_task(get_db(), task_id)
    return ids


def test_a_failing_check_tells_the_builder_to_fix_the_code(repo, flow):
    _enter_building(repo, flow)
    _complete_all(red())

    text = blocked(complete(repo), repo)

    assert "fixing the code" in text
    assert "HUMAN_QUESTIONS.md" not in text


def test_an_unreadable_block_sends_the_builder_to_a_human(repo, flow):
    _enter_building(repo, flow)
    [task_id] = _complete_all(MALFORMED)

    text = blocked(complete(repo), repo)

    assert "HUMAN_QUESTIONS.md" in text
    assert "refreeze" in text
    assert "fixing the code" not in text
    assert task_id in text


def test_one_of_each_gets_both_action_lines(repo, flow):
    _enter_building(repo, flow)
    _complete_all(red(), MALFORMED)

    text = blocked(complete(repo), repo)

    assert "fixing the code" in text
    assert "HUMAN_QUESTIONS.md" in text


# -- one event read per gate run --------------------------------------------


def _run_gate(repo) -> dict | None:
    return task_checks.check_task_checks(
        GATE,
        _storage(repo),
        "BUILDING",
        "REVIEWING",
        board="feature",
        feature_scope="demo",
    )


def test_the_event_log_is_read_once_per_gate_run_not_once_per_task(
    repo, flow, monkeypatch
):
    _enter_building(repo, flow)
    ids = _complete_all(PLAIN, PLAIN, PLAIN)
    reads = []
    real = eventlog.read_events

    def counted(*args, **kwargs):
        reads.append(args)
        return real(*args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(eventlog, "read_events", counted)
        result = _run_gate(repo)

    assert result is None
    assert len(reads) == 1, "read the event log %d times for 3 tasks" % len(reads)
    assert [len(proofs(repo, task_id)) for task_id in ids] == [1, 1, 1]


def test_unreadable_events_run_the_checks_again(repo, flow, monkeypatch, tmp_path):
    log = tmp_path / "ran.log"
    _enter_building(repo, flow)
    [task_id] = _complete_all(counting("Counted task.", log))

    def broken(*_args, **_kwargs):
        raise RuntimeError("event log down")

    with monkeypatch.context() as patched:
        patched.setattr(eventlog, "read_events", broken)
        result = _run_gate(repo)

    assert result is None
    assert log.read_text() == "x"
    assert [p["checks"] for p in proofs(repo, task_id)] == ["passed"]
