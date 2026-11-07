"""chief-autopilot-round-two 06: a loop task parks on its role question and runs again with the answer.

A goal-loop task's agent (``sched-<task>#N``) that posts a ``question`` to a role in
``consult_routes.CONSULT_ROLES`` is parked by the scheduler whatever it reported, answered or not
(``task_waits.asked_questions_by_run``): the attempt never saw the answer. ``fan_out._drain``
waits for the questions' consults (``supervisor/consult_wait.wait_for_consults``) while a route is
``queued`` or ``running``, then drains again, so the released task runs as ``sched-<task>#2`` in the
same run with ``## Answers to your questions`` in its prompt. A route that outlives the wait, and a
question handed to the person, end the run ``waiting_for_answer``.

The tests post the answer row directly and fake the route rows (``consult_routes.record_route``):
a direct ``post_message`` starts no consult (only ``POST /comms/post`` does).
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

WAITING = "waiting_for_answer"
ANSWER_HEADING = "## Answers to your questions"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _row(tid: str) -> dict:
    row = _conn().execute("SELECT * FROM comms_messages WHERE id=?", (tid,))
    return dict(row.fetchone())


def _task(scope: str, text: str, goal_id=None) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    conn = _conn()
    tid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        goal_id=goal_id,
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on='[]' WHERE id=?",
        (tid,),
    )
    conn.commit()
    return tid


def _ask(scope: str, run_id: str, text: str, to: str = "architect") -> str:
    """The task's agent posts a question, stamped with its spawn's run id."""
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        _conn(),
        board="feature",
        scope=scope,
        from_agent="builder",
        to_agent=to,
        type="question",
        text=text,
        author_run_id=run_id,
    )


def _route(qid: str, task_id: str, run_id: str, status: str) -> None:
    """Fake the router's route row for the question (ticket 04 records it on the post)."""
    from pathly_orchestrator.db.queries import consult_routes as cr

    decision = cr.Decision(
        kind="route",
        reason="",
        role="architect",
        task_id=task_id,
        goal_key=None,
        asking_run_id=run_id,
    )
    assert cr.record_route(_conn(), decision, qid, status=status)


def _consult_answers(scope: str, qid: str, text: str) -> None:
    """What a consult's delivery does: the route ends ``answered``, then the answer row."""
    from pathly_orchestrator.db.queries import consult_routes as cr
    from pathly_orchestrator.db.queries.comms import post_message

    cr.set_route_status(_conn(), qid, "answered")
    post_message(
        _conn(),
        board="feature",
        scope=scope,
        from_agent="architect",
        type="answer",
        text=text,
        reply_to=qid,
    )


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


class _Waits:
    """A spy on ``consult_wait.wait_for_consults``: each call's task ids, the asking task's status
    when the wait began, and how long it took; ``started`` is set on the first call."""

    def __init__(self, monkeypatch, watched: dict):
        from pathly_orchestrator.supervisor import consult_wait

        self.calls: list = []
        self.started = threading.Event()
        real = consult_wait.wait_for_consults

        def spy(task_ids, abort_check, timeout):
            status = _row(watched["tid"])["task_status"] if watched else None
            began = time.monotonic()
            self.started.set()
            out = real(task_ids, abort_check, timeout)
            self.calls.append(
                {
                    "tasks": list(task_ids),
                    "status": status,
                    "timeout": timeout,
                    "seconds": time.monotonic() - began,
                    "released": list(out),
                }
            )
            return out

        monkeypatch.setattr(consult_wait, "wait_for_consults", spy)


def _run_goal_loop(tmp_path, monkeypatch, topic: str, on_spawn):
    """Run a real goal-loop over one task with a fake spawn; ``on_spawn(task_id, run_id)`` is the
    agent. Returns (state, results, spawns as (run_id, prompt), task id)."""
    from pathly_orchestrator import fsm_http_client as fhc
    from pathly_orchestrator import supervisor
    from pathly_orchestrator.db.queries.app_settings import set_setting
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.fsm_ops import next_action
    from pathly_orchestrator.fsm_ops_complete import complete_stage

    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
    (root / ".gitignore").write_text("pathly/**/BOARD.json\nEVENTS.jsonl\n*.tmp\n")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    (root / "pathly" / "features" / topic).mkdir(parents=True)

    set_setting(_conn(), "code_context.backend", "off")
    monkeypatch.setattr(fhc, "next_action", next_action)
    monkeypatch.setattr(fhc, "complete_stage", complete_stage)

    goal_id = post_message(
        _conn(),
        board="feature",
        scope=topic,
        from_agent="architect",
        type="goal",
        text="Goal: a role answers the task",
    )
    tid = _task(topic, "ASKS: build the parser.", goal_id=goal_id)
    spawns: list = []

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **_):
        spawns.append((run_id, instructions))
        on_spawn(tid, run_id)
        return {"cost_usd": 0.0, "session_id": None}

    monkeypatch.setattr(supervisor, "_run_stage_via_terminal", fake_spawn)
    finished = threading.Event()
    results: dict = {}

    def on_done(run_id, result):
        results.update(result)
        finished.set()

    state = supervisor.start_run(
        topic=topic,
        flow="goal-loop",
        project_root=str(root),
        max_iterations=10,
        max_cost_usd=10.0,
        interactive=False,
        goal_id=goal_id,
        broadcast_fn=lambda t, p: None,
        on_done=on_done,
    )
    try:
        assert finished.wait(120), f"run did not finish: {state.status} {spawns}"
    finally:
        if not finished.is_set():
            supervisor.abort_run(topic)
            finished.wait(30)
        with supervisor._lock:
            supervisor._registry.pop(topic, None)
    return state, results, spawns, tid


def _fast_polls(monkeypatch, timeout: float) -> None:
    from pathly_orchestrator.supervisor import consult_wait

    monkeypatch.setattr(consult_wait, "POLL_INTERVAL", 0.05)
    monkeypatch.setattr(consult_wait, "WAIT_TIMEOUT", timeout)


# ── the drain waits for a running consult, then runs the task again with the answer ─────────


def test_the_drain_waits_for_the_consult_and_runs_the_task_again_with_the_answer(
    tmp_path, monkeypatch
):
    topic = "feat-role-q-wait"
    _fast_polls(monkeypatch, 60.0)
    watched: dict = {}
    waits = _Waits(monkeypatch, watched)
    asked: dict = {}
    answerers: list = []

    def answer_once_the_drain_waits():
        assert waits.started.wait(60), "the drain never waited for the consult"
        time.sleep(0.3)
        _consult_answers(topic, asked["qid"], "ANSWER-MARKER: use the existing queue")

    def on_spawn(tid, run_id):
        watched["tid"] = tid
        if run_id == f"sched-{tid}#1":
            asked["qid"] = _ask(topic, run_id, "QUESTION-MARKER: which queue?")
            _route(asked["qid"], tid, run_id, "running")
            t = threading.Thread(
                target=answer_once_the_drain_waits, name="asker-consult", daemon=True
            )
            answerers.append(t)
            t.start()

    try:
        state, results, spawns, tid = _run_goal_loop(
            tmp_path, monkeypatch, topic, on_spawn
        )
    finally:
        for t in answerers:
            t.join(30)

    # The asking attempt reported success but was parked, not completed, while the drain waited.
    assert waits.calls and waits.calls[0]["status"] == "blocked"
    assert waits.calls[0]["tasks"] == [tid]
    assert waits.calls[0]["released"] == [tid]
    # Run again in the same run, with the question and its answer in the prompt.
    assert [r for r, _ in spawns] == [f"sched-{tid}#1", f"sched-{tid}#2"]
    assert ANSWER_HEADING not in spawns[0][1]
    block = spawns[1][1][spawns[1][1].index(ANSWER_HEADING) :]
    assert "QUESTION-MARKER: which queue?" in block
    assert "ANSWER-MARKER: use the existing queue" in block
    row = _row(tid)
    assert row["task_status"] == "done"
    assert row["attempts"] - row["waits"] == 1
    assert state.status == "done", (state.status, state.error_kind, results)
    assert state.error_kind != WAITING
    assert results.get("error") != WAITING


def test_a_role_question_answered_before_the_attempt_ended_still_runs_it_again(
    tmp_path, monkeypatch
):
    topic = "feat-role-q-early"
    _fast_polls(monkeypatch, 60.0)
    asked: dict = {}

    def on_spawn(tid, run_id):
        if run_id == f"sched-{tid}#1":
            asked["qid"] = _ask(topic, run_id, "QUESTION-MARKER: which layer?")
            _route(asked["qid"], tid, run_id, "running")
            # The consult answers while the attempt still runs: the attempt never sees it.
            _consult_answers(topic, asked["qid"], "ANSWER-MARKER: the db layer")

    state, results, spawns, tid = _run_goal_loop(tmp_path, monkeypatch, topic, on_spawn)

    assert [r for r, _ in spawns] == [f"sched-{tid}#1", f"sched-{tid}#2"]
    block = spawns[1][1][spawns[1][1].index(ANSWER_HEADING) :]
    assert "QUESTION-MARKER: which layer?" in block
    assert "ANSWER-MARKER: the db layer" in block
    row = _row(tid)
    assert row["task_status"] == "done"
    assert row["attempts"] - row["waits"] == 1 and row["waits"] == 1
    assert json.loads(row["answered_questions"]) == [asked["qid"]]
    assert state.status == "done", (state.status, state.error_kind, results)


# ── what still ends the run waiting_for_answer ──────────────────────────────────────────────


def test_a_route_still_running_past_the_wait_timeout_ends_the_run_waiting(
    tmp_path, monkeypatch
):
    topic = "feat-role-q-timeout"
    _fast_polls(monkeypatch, 0.5)
    waits = _Waits(monkeypatch, {})

    def on_spawn(tid, run_id):
        if run_id == f"sched-{tid}#1":
            qid = _ask(topic, run_id, "Which queue?")
            _route(qid, tid, run_id, "running")

    state, results, spawns, tid = _run_goal_loop(tmp_path, monkeypatch, topic, on_spawn)

    assert [r for r, _ in spawns] == [f"sched-{tid}#1"]
    assert waits.calls and waits.calls[0]["timeout"] == 0.5
    assert waits.calls[0]["seconds"] >= 0.5 and waits.calls[0]["released"] == []
    assert _row(tid)["task_status"] == "blocked"
    assert state.status == "error" and state.error_kind == WAITING
    assert results["status"] == "error" and results["error"] == WAITING


def test_a_question_handed_to_the_person_ends_the_run_waiting_with_no_wait(
    tmp_path, monkeypatch
):
    from pathly_orchestrator.db.queries import consult_routes as cr

    topic = "feat-role-q-person"
    # A long timeout: a wait on a question the person holds would show in the seconds.
    _fast_polls(monkeypatch, 600.0)
    waits = _Waits(monkeypatch, {})
    asked: dict = {}

    def on_spawn(tid, run_id):
        if run_id == f"sched-{tid}#1":
            asked["qid"] = _ask(topic, run_id, "Which vendor?")
            _route(asked["qid"], tid, run_id, "running")
            assert cr.hand_to_person(
                _conn(), asked["qid"], "the person must choose", by="architect"
            )

    started = time.monotonic()
    state, results, spawns, tid = _run_goal_loop(tmp_path, monkeypatch, topic, on_spawn)

    assert time.monotonic() - started < 60
    assert all(c["seconds"] < 5 for c in waits.calls), waits.calls
    assert [r for r, _ in spawns] == [f"sched-{tid}#1"]
    row = _row(tid)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{asked['qid']}"
    assert state.status == "error" and state.error_kind == WAITING
    assert results["status"] == "error" and results["error"] == WAITING


def test_an_attempt_with_no_question_is_unchanged(tmp_path, monkeypatch):
    topic = "feat-role-q-none"
    _fast_polls(monkeypatch, 600.0)

    state, results, spawns, tid = _run_goal_loop(
        tmp_path, monkeypatch, topic, lambda tid, run_id: None
    )

    assert [r for r, _ in spawns] == [f"sched-{tid}#1"]
    row = _row(tid)
    assert row["task_status"] == "done"
    assert row["attempts"] == 1 and row["waits"] == 0
    assert state.status == "done", (state.status, state.error_kind, results)


# ── asked_questions_by_run ───────────────────────────────────────────────────────────────────


def test_asked_questions_by_run_lists_open_and_role_questions_once_oldest_first():
    from pathly_orchestrator.db.queries import consult_routes as cr
    from pathly_orchestrator.db.queries.task_waits import (
        asked_questions_by_run,
        open_questions_by_run,
    )

    scope = "feat-role-q-asked"
    run_id = "sched-asked#1"
    to_human = _ask(scope, run_id, "Q1 to the person", to="human")
    answered_role = _ask(scope, run_id, "Q2 to the architect", to="architect")
    _route(answered_role, "t-asked", run_id, "running")
    _consult_answers(scope, answered_role, "A2")
    handed = _ask(scope, run_id, "Q3 to the po", to="po")
    _route(handed, "t-asked", run_id, "running")
    assert cr.hand_to_person(_conn(), handed, "a person's call", by="po")
    unrouted = _ask(scope, run_id, "Q4 to the tester", to="Tester ")
    _ask(scope, run_id, "Q5 to an unknown role", to="wizard")
    _ask(scope, "sched-other#1", "Q6 from another run", to="architect")

    # The handed question is a question to the person now: open, and listed once.
    assert handed in open_questions_by_run(_conn(), run_id)
    assert asked_questions_by_run(_conn(), run_id) == [
        to_human,
        answered_role,
        handed,
        unrouted,
    ]
    assert asked_questions_by_run(_conn(), "") == []


# ── an agent that answers its own role question gets no free re-run ─────────────────────────


def test_a_role_question_the_asking_run_answered_itself_is_not_a_wait(
    tmp_path, monkeypatch
):
    from pathly_orchestrator.db.queries.comms import post_message

    topic = "feat-role-q-self"
    _fast_polls(monkeypatch, 5.0)

    def on_spawn(tid, run_id):
        qid = _ask(topic, run_id, f"Which queue, {run_id}?")
        # What POST /comms/post with the run's own token stamps: the asking run.
        post_message(
            _conn(),
            board="feature",
            scope=topic,
            from_agent="builder",
            type="answer",
            text="self",
            reply_to=qid,
            author_run_id=run_id,
        )

    state, results, spawns, tid = _run_goal_loop(tmp_path, monkeypatch, topic, on_spawn)

    assert [r for r, _ in spawns] == [f"sched-{tid}#1"]
    row = _row(tid)
    assert row["task_status"] == "done" and row["waits"] == 0
    assert state.status == "done", (state.status, state.error_kind, results)


def test_a_task_past_the_wait_ceiling_is_held_for_the_person(tmp_path, monkeypatch):
    from pathly_orchestrator.db.queries.app_settings import set_setting
    from pathly_orchestrator.db.queries.comms import answer_question
    from pathly_orchestrator.db.queries.task_waits import WAIT_MARGIN

    topic = "feat-role-q-ceiling"
    _fast_polls(monkeypatch, 5.0)
    set_setting(_conn(), "consult.max_per_task", "1")
    ceiling = 1 + WAIT_MARGIN

    def on_spawn(tid, run_id):
        # An answer through /comms/answer carries no run: it cannot be told from the person's.
        answer_question(
            _conn(), question_id=_ask(topic, run_id, run_id), answer_text="x"
        )

    state, results, spawns, tid = _run_goal_loop(tmp_path, monkeypatch, topic, on_spawn)

    assert len(spawns) == ceiling + 1, [r for r, _ in spawns]
    row = _row(tid)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"].startswith(f"{WAITING}:")
    assert row["waits"] == ceiling + 1 and row["attempts"] - row["waits"] == 0
    assert state.status == "error" and state.error_kind == WAITING
    assert results["error"] == WAITING


def test_an_answered_route_with_no_answer_row_is_waited_on_only_briefly(monkeypatch):
    from pathly_orchestrator.db.queries import consult_routes as cr
    from pathly_orchestrator.supervisor import consult_wait

    scope = "feat-role-q-gap"
    monkeypatch.setattr(consult_wait, "POLL_INTERVAL", 0.05)
    monkeypatch.setattr(consult_wait, "ANSWERED_GRACE", 0.3)
    tid = _task(scope, "Build it.")
    qid = _ask(scope, "sched-gap#1", "Which queue?")
    _route(qid, tid, "sched-gap#1", "running")
    cr.set_route_status(
        _conn(), qid, "answered"
    )  # the delivery crashed before the answer row
    _conn().execute(
        "UPDATE comms_messages SET task_status='blocked', fail_reason=? WHERE id=?",
        (f"{WAITING}:{qid}", tid),
    )
    _conn().commit()

    began = time.monotonic()
    assert consult_wait.wait_for_consults([tid], None, 60.0) == []
    assert 0.3 <= time.monotonic() - began < 5
