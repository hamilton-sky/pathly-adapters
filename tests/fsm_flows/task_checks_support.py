"""Shared setup for the build-proof 07 tests (``test_task_checks_*.py``).

Task texts with check blocks, helpers that drive a ``team-build`` run through the joins the way
the supervisor does, and a goal-loop run whose tasks the drain has already completed. The
``git init`` project and the flow fixture come from ``review_packet_support``.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from _paths import PYTHON

import yaml
from review_packet_support import (
    FEATURE,
    _args,
    _as,
    _claim,
    _enter_building,
    _storage,
    _write,
    flow,
    repo,
)

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task, complete_task

__all__ = ["flow", "repo"]

FEEDBACK = "TASK_CHECK_FAILURES.md"
REVIEW = FEATURE + "/REVIEW.md"
PLAIN = "Make x two.\n"
GATE = {"type": "task_checks", "on_fail": FEEDBACK}


def text_with(title: str, command: str) -> str:
    return "%s\n\n```check\n$ %s\n```\n" % (title, command)


def red(title: str = "Red task.", marker: str = "red-marker") -> str:
    return text_with(
        title, PYTHON + " -c \"import sys; print('%s'); sys.exit(1)\"" % marker
    )


def green(title: str = "Green task.") -> str:
    return text_with(title, PYTHON + " -c \"print('green-marker')\"")


def counting(title: str, log: Path, code: int = 0) -> str:
    """A check that appends one character to ``log`` (outside the repo) and exits ``code``."""
    command = PYTHON + " -c \"import sys; open('%s', 'a').write('x'); sys.exit(%d)\""
    return text_with(title, command % (log.as_posix(), code))


def load(name: str) -> dict:
    text = (
        files("pathly_data")
        .joinpath("core/flows/%s.flow.yaml" % name)
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def complete(repo, **extra) -> dict:
    return fsm_ops.complete_stage({**_args(repo), **extra})


def events(repo, kind: str) -> list[dict]:
    return [e for e in eventlog.read_events(str(_storage(repo))) if e["type"] == kind]


def proofs(repo, task_id: str) -> list[dict]:
    return [e for e in events(repo, "TASK_PROOF") if e["task_id"] == task_id]


def blocked(result: dict, repo) -> str:
    """Assert the gate sent the builder back and return the feedback file it wrote."""
    assert result.get("blocked") is True, result
    assert result["target_agent"] == "builder"
    assert result["file"] == FEEDBACK
    return (_storage(repo) / "feedback" / FEEDBACK).read_text(encoding="utf-8")


def failed_gate(repo) -> dict:
    failed = [e for e in events(repo, "GATE_FAILED") if e["gate"] == "task_checks"]
    assert failed, "task_checks never failed"
    return failed[-1]


def skipped(repo) -> list[str]:
    return [
        e["reason"] for e in events(repo, "GATE_SKIPPED") if e["gate"] == "task_checks"
    ]


def builder_edit(repo, flow, state: str = "BUILDING") -> None:
    _as(
        repo,
        flow,
        "builder",
        state,
        lambda: _write(repo, "src/app.py", "x = 2\ny = 2\n"),
    )


def review_passes(repo, flow) -> None:
    _as(
        repo,
        flow,
        "reviewer",
        "REVIEWING",
        lambda: _write(repo, REVIEW, "RESULT: PASS\nClean.\n"),
    )


def set_text(task_id: str, text: str) -> None:
    get_db().execute("UPDATE comms_messages SET text=? WHERE id=?", (text, task_id))
    get_db().commit()


def claim_again(task_id: str) -> None:
    """A human re-opens a done task and a builder claims it again (a new ``claimed_at``)."""
    get_db().execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id=?", (task_id,)
    )
    get_db().commit()
    assert claim_task(get_db(), task_id, "build")


def to_retro(repo, flow) -> None:
    """One clean task (no check block) built, reviewed and tested: the run is in RETRO."""
    _enter_building(repo, flow)
    task_id = _claim(PLAIN)
    builder_edit(repo, flow)
    assert complete(repo).get("next_state") == "REVIEWING"
    review_passes(repo, flow)
    complete_task(get_db(), task_id)
    assert complete(repo).get("next_state") == "TESTING"
    assert complete(repo).get("next_state") == "RETRO"


def drained_goal_loop(repo, *texts: str) -> list[str]:
    """DRAINING entered, then one goal task per text claimed (as the drain does) and done."""
    eventlog.write_state(
        str(_storage(repo)), {"current": "DRAINING"}, load("goal-loop")
    )
    fsm_ops.next_action({**_args(repo), "flow": "goal-loop", "goal_id": "g1"})
    conn = get_db()
    ids = []
    for text in texts:
        task_id = post_message(
            conn,
            board="feature",
            scope="demo",
            from_agent="planner",
            type="task",
            text=text,
            goal_id="g1",
        )
        assert claim_task(conn, task_id, "sched-%s#1" % task_id)
        complete_task(conn, task_id)
        ids.append(task_id)
    return ids


def join(repo, **extra) -> dict:
    return complete(repo, flow="goal-loop", goal_id="g1", **extra)
