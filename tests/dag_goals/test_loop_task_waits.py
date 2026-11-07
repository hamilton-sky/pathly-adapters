"""chief-autopilot 12: a loop task parks on its question in the scheduler and gets the answer.

A goal-loop task runs inside an FSM stage; its spawn's run id is ``sched-<task>#N``. When the
task's agent posted a question to ``human`` (``author_run_id`` is that run id) that is still open
when the spawn returns, the scheduler parks the task (``blocked``,
``fail_reason='waiting_for_answer:<ids>'``, ``waits + 1``) instead of completing it or retrying
it, whatever the spawn reported, and broadcasts ``task_waiting``. After an answer the task is
claimed again with a new run id and its prompt carries each question and its answer. Since
chief-autopilot-round-two 06 a question to a role (``architect``) parks the task too. A goal-loop
run with a parked task drains the other ready tasks, then ends ``error`` with
``waiting_for_answer`` instead of sending the join's ``INCOMPLETE_TASKS`` to a builder.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import pytest

SCOPE = "feat-loop-wait"
WAITING = "waiting_for_answer"
ANSWER_HEADING = "## Answers to your questions"


class _State:
    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "claude-sonnet-4-6"
    topic = SCOPE
    storage_path = ""


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _task(scope: str, text: str, goal_id=None, depends_on=None) -> str:
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
        "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
        (json.dumps(depends_on or []), tid),
    )
    conn.commit()
    return tid


def _row(tid: str) -> dict:
    row = _conn().execute("SELECT * FROM comms_messages WHERE id=?", (tid,))
    return dict(row.fetchone())


def _ask(scope: str, run_id: str, text: str, to: str = "human") -> str:
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


def _answer(scope: str, question_id: str, text: str) -> None:
    from pathly_orchestrator.db.queries.comms import post_message

    post_message(
        _conn(),
        board="feature",
        scope=scope,
        from_agent="human",
        type="answer",
        text=text,
        reply_to=question_id,
    )


def _drain(scope: str, spawn, events: list | None = None) -> dict:
    from pathly_orchestrator.supervisor.isolation import LaneIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    return scheduler_loop(
        _State(),
        board="feature",
        scope=scope,
        isolation=LaneIsolation(),
        spawn_fn=spawn,
        event_broadcast_fn=(
            (lambda s, payload: events.append(payload)) if events is not None else None
        ),
    )


def _escalations(scope: str) -> list:
    return (
        _conn()
        .execute(
            "SELECT id FROM comms_messages WHERE scope=? AND type='escalation'",
            (scope,),
        )
        .fetchall()
    )


# ── the scheduler parks a task whose spawn left an open question ────────────────────────────


def test_a_loop_task_that_asks_and_exits_successfully_is_parked_not_completed():
    scope = SCOPE + "-ok"
    tid = _task(scope, "Build the parser.")
    asked: dict = {}

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        asked["qid"] = _ask(scope, run_id, "Which date format?")
        asked["run_id"] = run_id
        return {"result": "ok"}

    events: list = []
    out = _drain(scope, spawn, events)

    row = _row(tid)
    assert asked["run_id"] == f"sched-{tid}#1"
    assert tid not in out["completed"] and tid not in out["failed"]
    assert out["waiting"] == [tid]
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{asked['qid']}"
    assert row["attempts"] == 1 and row["waits"] == 1
    assert row["claimed_by"] is None
    waiting = [e for e in events if e.get("event") == "task_waiting"]
    assert waiting and waiting[0]["task_id"] == tid
    assert waiting[0]["questions"] == [asked["qid"]]
    assert not [e for e in events if e.get("event") == "task_done"]


def test_a_loop_task_that_fails_with_an_open_question_is_parked_not_retried(
    monkeypatch,
):
    from pathly_orchestrator.db.queries.app_settings import set_setting

    scope = SCOPE + "-fail"
    tid = _task(scope, "Build the exporter.")
    # A limit of one: a counted attempt would escalate the task instead of parking it.
    set_setting(_conn(), "goal.task_max_attempts", "1")
    try:

        def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
            _ask(scope, run_id, "CSV or JSON?")
            return {"outcome": "failed", "error": "cannot decide the format"}

        out = _drain(scope, spawn)
    finally:
        set_setting(_conn(), "goal.task_max_attempts", "")

    row = _row(tid)
    assert out["waiting"] == [tid]
    assert out["failed"] == [] and out["blocked"] == []
    assert row["task_status"] == "blocked"
    assert row["fail_reason"].startswith(f"{WAITING}:")
    # No attempt counted: the claim's attempt is matched by a wait.
    assert row["attempts"] - row["waits"] == 0
    assert _escalations(scope) == []


def test_a_question_to_a_role_does_not_park_the_loop_task():
    # Round two (chief-autopilot-round-two 06) reverses round one: a question to a role parks
    # the task too, so the next attempt gets the role's answer. The name is round one's.
    scope = SCOPE + "-role"
    tid = _task(scope, "Build the router.")
    asked: dict = {}

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        asked["qid"] = _ask(scope, run_id, "Which layer owns this?", to="architect")
        return {"result": "ok"}

    out = _drain(scope, spawn)
    assert out["completed"] == []
    assert out["waiting"] == [tid]
    row = _row(tid)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{asked['qid']}"
    assert row["attempts"] == 1 and row["waits"] == 1


# ── the answer reaches the next attempt ─────────────────────────────────────────────────────


def test_an_answered_loop_task_is_claimed_again_with_a_new_run_id_and_the_answer():
    scope = SCOPE + "-resume"
    tid = _task(scope, "Build the importer.")
    seen: list = []

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        seen.append((run_id, instructions))
        if len(seen) == 1:
            _ask(scope, run_id, "QUESTION-MARKER: which encoding?")
        return {"result": "ok"}

    first = _drain(scope, spawn)
    assert first["waiting"] == [tid]
    qid = _row(tid)["fail_reason"].split(":", 1)[1]
    assert ANSWER_HEADING not in seen[0][1]

    _answer(scope, qid, "ANSWER-MARKER: utf-8")
    assert _row(tid)["task_status"] == "pending"

    second = _drain(scope, spawn)
    assert second["completed"] == [tid]
    run_id, prompt = seen[1]
    assert run_id == f"sched-{tid}#2"
    block = prompt[prompt.index(ANSWER_HEADING) :]
    assert "QUESTION-MARKER: which encoding?" in block
    assert "ANSWER-MARKER: utf-8" in block
    row = _row(tid)
    assert row["task_status"] == "done"
    assert row["attempts"] == 2 and row["waits"] == 1


# ── a task with no question behaves as before ───────────────────────────────────────────────


def test_a_loop_task_with_no_question_still_completes_or_retries():
    ok_scope = SCOPE + "-plain-ok"
    ok = _task(ok_scope, "Build the formatter.")
    out = _drain(ok_scope, lambda *a: {"result": "ok"})
    assert out["completed"] == [ok] and out["waiting"] == []
    assert _row(ok)["task_status"] == "done"

    bad_scope = SCOPE + "-plain-bad"
    bad = _task(bad_scope, "Build the linter.")
    calls: list = []

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        calls.append(run_id)
        return {"outcome": "failed", "error": "broken"}

    out = _drain(bad_scope, spawn)
    row = _row(bad)
    assert out["waiting"] == []
    # Retried within the default limit, then escalated: every attempt counted.
    assert calls[:2] == [f"sched-{bad}#1", f"sched-{bad}#2"]
    assert out["failed"] == [bad]
    assert row["task_status"] == "failed" and row["waits"] == 0
    assert row["attempts"] == len(calls)


# ── a goal-loop run with a parked task ends waiting_for_answer ──────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_a_goal_loop_run_with_a_parked_task_drains_the_rest_then_ends_waiting(
    tmp_path, monkeypatch
):
    from pathly_orchestrator import fsm_http_client as fhc
    from pathly_orchestrator import supervisor
    from pathly_orchestrator.db.queries.app_settings import set_setting
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.fsm_ops import next_action
    from pathly_orchestrator.fsm_ops_complete import complete_stage

    topic = "feat-loop-wait-run"
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
    (root / ".gitignore").write_text("pathly/**/BOARD.json\nEVENTS.jsonl\n")
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
        text="Goal: the run waits",
    )
    asks = _task(topic, "ASKS: build the parser.", goal_id=goal_id)
    other = _task(topic, "OTHER: build the printer.", goal_id=goal_id)
    behind = _task(topic, "BEHIND: use the parser.", goal_id=goal_id, depends_on=[asks])

    spawns: list = []

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **_):
        spawns.append(run_id)
        if run_id == f"sched-{asks}#1":
            _ask(topic, run_id, "Which grammar?")
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

    # The other ready task drained; the parked one waits; its dependent stays pending.
    assert _row(other)["task_status"] == "done"
    assert _row(asks)["task_status"] == "blocked"
    assert _row(asks)["fail_reason"].startswith(f"{WAITING}:")
    assert _row(behind)["task_status"] == "pending"
    # Only the two task spawns: no builder was sent INCOMPLETE_TASKS for the parked task.
    assert sorted(spawns) == sorted([f"sched-{asks}#1", f"sched-{other}#1"])

    assert state.status == "error"
    assert state.error_kind == WAITING
    assert results["status"] == "error" and results["error"] == WAITING
    history = (
        _conn()
        .execute("SELECT status FROM run_history WHERE run_id=?", (state.run_id,))
        .fetchone()
    )
    assert history is not None and history["status"] == "error"
