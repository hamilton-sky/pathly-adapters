"""chief-autopilot-round-two 05: round one's gaps around a parked task are closed.

* An answer written after ``open_questions_by_run`` read the run's questions and before the task
  was parked used to leave the task parked on an answered question: ``park_and_recheck`` parks,
  then frees the task when every question is answered now (single and loop paths), so it is
  ``pending`` again with ``answered_questions`` and one more ``waits``.
* A ``park_task`` that parks nothing (the task is no longer ``in_progress``) logs a warning that
  names the task, its status and the questions.
* A loop attempt that asked and reported success is not proven: no ``TASK_PROOF``, no check run.
* A goal-loop run that parks a task broadcasts no "continuing to the next stage" warning and writes
  ``RUN_OUTCOME`` (failed, ``waiting_for_answer``), which ``GET /runs/<id>`` reads.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from pathlib import Path

import pytest
from _paths import PYTHON

SCOPE = "feat-park-gaps"
WAITING = "waiting_for_answer"
ANSWER_HEADING = "## Answers to your questions"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


class _State:
    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "m"
    topic = SCOPE
    storage_path = ""


def _conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


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


def _row(tid: str) -> dict:
    found = _conn().execute("SELECT * FROM comms_messages WHERE id=?", (tid,))
    return dict(found.fetchone())


def _ask(scope: str, run_id: str, text: str) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        _conn(),
        board="feature",
        scope=scope,
        from_agent="builder",
        to_agent="human",
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


def _answer_right_after_the_read(monkeypatch, scope: str, text: str) -> list:
    """Make ``open_questions_by_run`` answer every question it returns, right after reading
    them: the answer lands before the park, when no blocked task exists to free."""
    from pathly_orchestrator.db.queries import task_waits

    real = task_waits.open_questions_by_run
    answered: list = []

    def racing(conn, run_id):
        ids = real(conn, run_id)
        for qid in ids:
            _answer(scope, qid, text)
            answered.append(qid)
        return ids

    monkeypatch.setattr(task_waits, "open_questions_by_run", racing)
    return answered


def _drain(scope: str, spawn, abort_check=None) -> dict:
    from pathly_orchestrator.supervisor.isolation import LaneIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    return scheduler_loop(
        _State(),
        board="feature",
        scope=scope,
        isolation=LaneIsolation(),
        spawn_fn=spawn,
        abort_check=abort_check,
    )


# ── the park and answer race ─────────────────────────────────────────────────────────────────


def test_single_an_answer_between_the_read_and_the_park_leaves_the_task_pending(
    tmp_path, monkeypatch
):
    from pathly_orchestrator.db.queries.comms_tasks import claim_task
    from pathly_orchestrator.supervisor.run_task_outcome import settle_run_tasks
    from pathly_orchestrator.supervisor.state import RunnerState

    scope = SCOPE + "-single"
    run_id = "single-race-run"
    tid = _task(scope, "Build the parser.")
    assert claim_task(_conn(), tid, run_id=run_id)
    qid = _ask(scope, run_id, "Which date format?")
    answered = _answer_right_after_the_read(monkeypatch, scope, "ISO 8601.")

    storage = tmp_path / "pathly" / "features" / scope
    storage.mkdir(parents=True)
    state = RunnerState(
        topic=scope,
        flow="board-run",
        project_root=str(tmp_path),
        model="m",
        timeout=60,
        run_id=run_id,
        current_state="builder",
        board_scope=scope,
    )
    state.executor_owned_telemetry = True
    state.storage_path = str(storage)

    error = settle_run_tasks(state, run_id, storage, None, always_record=True)

    assert answered == [qid]
    row = _row(tid)
    assert error == WAITING
    assert row["task_status"] == "pending"
    assert row["fail_reason"] is None
    assert json.loads(row["answered_questions"]) == [qid]
    assert row["waits"] == 1


def test_loop_an_answer_between_the_read_and_the_park_leaves_the_task_pending(
    monkeypatch,
):
    scope = SCOPE + "-loop"
    tid = _task(scope, "Build the exporter.")
    spawns: list = []

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        spawns.append(run_id)
        _ask(scope, run_id, "CSV or JSON?")
        return {"result": "ok"}

    answered = _answer_right_after_the_read(monkeypatch, scope, "CSV.")
    # Stop the drain once the first attempt is handled, before the frontier is read again.
    out = _drain(scope, spawn, abort_check=lambda: bool(spawns))

    row = _row(tid)
    assert spawns == [f"sched-{tid}#1"]
    assert len(answered) == 1
    # A released task counts as a wait: not completed, no attempt spent.
    assert out["waiting"] == [tid] and out["completed"] == [] and out["failed"] == []
    assert row["task_status"] == "pending"
    assert row["fail_reason"] is None
    assert json.loads(row["answered_questions"]) == answered
    assert row["waits"] == 1 and row["attempts"] == 1


def test_loop_a_released_task_runs_again_in_the_drain_and_no_longer_waits(
    monkeypatch,
):
    from pathly_orchestrator.supervisor.task_wait_outcome import (
        note_run_waits,
        take_run_waits,
    )

    scope = SCOPE + "-loop-again"
    tid = _task(scope, "Build the importer.")
    seen: list = []

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        seen.append((run_id, instructions))
        if len(seen) == 1:
            _ask(scope, run_id, "QUESTION-MARKER: which encoding?")
        return {"result": "ok"}

    _answer_right_after_the_read(monkeypatch, scope, "ANSWER-MARKER: utf-8")
    out = _drain(scope, spawn)

    assert [r for r, _ in seen] == [f"sched-{tid}#1", f"sched-{tid}#2"]
    assert "ANSWER-MARKER: utf-8" in seen[1][1][seen[1][1].index(ANSWER_HEADING) :]
    assert out["completed"] == [tid]
    row = _row(tid)
    assert row["task_status"] == "done" and row["waits"] == 1
    # The run records only the tasks that still wait, so it does not end waiting_for_answer.
    state = _State()
    note_run_waits(state, out["waiting"])
    assert take_run_waits(state) == []


# ── park_task returning False ─────────────────────────────────────────────────────────────────


def test_a_park_that_parks_nothing_logs_a_warning_naming_the_task(caplog):
    from pathly_orchestrator.supervisor.task_wait_outcome import park_if_asked

    scope = SCOPE + "-noop"
    tid = _task(
        scope, "Build the printer."
    )  # pending: park_task finds no in_progress row
    qid = _ask(scope, f"sched-{tid}#1", "Which font?")

    with caplog.at_level(logging.WARNING, logger="pathly.task_wait_outcome"):
        parked = park_if_asked(_conn(), tid, {tid: 0}, {tid: "x"}, None, scope)

    assert parked is False
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(tid in m and "pending" in m and qid in m for m in warnings), warnings
    assert _row(tid)["task_status"] == "pending"


# ── task_proof skips an asking attempt ────────────────────────────────────────────────────────


def test_a_loop_attempt_that_asked_and_succeeded_is_not_proven(tmp_path):
    from task_proof_support import (
        SCOPE as PROOF_SCOPE,
        Agent,
        State,
        add_task,
        drain,
        make_repo,
        proofs,
        row,
        set_app_setting,
    )

    set_app_setting("code_context.backend", "off")
    repo = make_repo(tmp_path)
    marker = tmp_path / "check-ran.txt"
    text = (
        "Greet.\n\n```check\n"
        f"$ {PYTHON} -c \"open({str(marker)!r}, 'w').write('ran')\"\n"
        "```\n"
    )
    tid = add_task(text)
    state = State(repo)

    class _Asks(Agent):
        def __call__(self, state, instructions, adapter, model, run_id, broadcast_fn):
            _ask(PROOF_SCOPE, run_id, "Which greeting?")
            return super().__call__(
                state, instructions, adapter, model, run_id, broadcast_fn
            )

    raw, _ = drain(state, _Asks(repo))

    assert raw["waiting"] == [tid]
    assert row(tid)["task_status"] == "blocked"
    assert proofs(state) == []
    assert not marker.exists()


# ── a goal-loop run that parks ────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _run_a_goal_loop_that_parks(tmp_path, monkeypatch, topic: str):
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
        text="Goal: the run parks",
    )
    asks = _task(topic, "ASKS: build the parser.", goal_id=goal_id)

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **_):
        if run_id == f"sched-{asks}#1":
            _ask(topic, run_id, "Which grammar?")
        return {"cost_usd": 0.0, "session_id": None}

    monkeypatch.setattr(supervisor, "_run_stage_via_terminal", fake_spawn)
    finished = threading.Event()
    payloads: list = []

    def on_done(run_id, result):
        finished.set()

    state = supervisor.start_run(
        topic=topic,
        flow="goal-loop",
        project_root=str(root),
        max_iterations=10,
        max_cost_usd=10.0,
        interactive=False,
        goal_id=goal_id,
        broadcast_fn=lambda t, p: payloads.append(p),
        on_done=on_done,
    )
    try:
        assert finished.wait(120), f"run did not finish: {state.status}"
    finally:
        if not finished.is_set():
            supervisor.abort_run(topic)
            finished.wait(30)
        with supervisor._lock:
            supervisor._registry.pop(topic, None)
    assert _row(asks)["task_status"] == "blocked"
    assert state.error_kind == WAITING
    return state, payloads


def test_a_goal_loop_run_that_parks_broadcasts_no_continuing_warning(
    tmp_path, monkeypatch
):
    _, payloads = _run_a_goal_loop_that_parks(
        tmp_path, monkeypatch, "feat-park-gaps-warn"
    )
    warnings = [p for p in payloads if p.get("type") == "RUNNER_WARNING"]
    assert not [
        p for p in warnings if "continuing to the next stage" in p.get("message", "")
    ], warnings


def test_get_runs_of_a_parked_goal_loop_run_shows_waiting_for_answer(
    tmp_path, monkeypatch
):
    from pathly_orchestrator.http_server import app

    state, _ = _run_a_goal_loop_that_parks(
        tmp_path, monkeypatch, "feat-park-gaps-outcome"
    )
    app.config["TESTING"] = True
    with app.test_client() as client:
        r = client.get(f"/runs/{state.run_id}")
    assert r.status_code == 200, r.data
    run = r.get_json()["run"]
    assert run["outcome"] == "failed"
    assert run["error"] == WAITING


# ── review round 1: an attempt left unproven because it asked never completes unproven ──────


def _proof_setup(tmp_path, exit_code: int):
    from task_proof_support import State, add_task, make_repo, set_app_setting

    set_app_setting("code_context.backend", "off")
    repo = make_repo(tmp_path)
    marker = tmp_path / "check-ran.txt"
    text = (
        "Greet.\n\n```check\n"
        f"$ {PYTHON} -c \"open({str(marker)!r}, 'a').write('ran'); "
        f'raise SystemExit({exit_code})"\n'
        "```\n"
    )
    return repo, marker, add_task(text), State(repo)


def test_an_asking_attempt_that_marked_its_own_task_done_is_proven(tmp_path):
    from task_proof_support import SCOPE as PROOF_SCOPE, Agent, drain, proofs

    from pathly_orchestrator.db.queries.comms import complete_task

    repo, marker, tid, state = _proof_setup(tmp_path, exit_code=1)

    class _AsksAndCompletes(Agent):
        def __call__(self, state, instructions, adapter, model, run_id, broadcast_fn):
            _ask(PROOF_SCOPE, run_id, "Which greeting?")
            complete_task(_conn(), tid)  # what POST /comms/tasks/status does
            return super().__call__(
                state, instructions, adapter, model, run_id, broadcast_fn
            )

    raw, _ = drain(state, _AsksAndCompletes(repo))

    # It could not be parked, so it was proven: the failing check sent it to the retry path.
    assert tid not in raw["completed"]
    assert tid in raw["failed"]
    assert marker.exists()
    assert proofs(state) and all(p["task_id"] == tid for p in proofs(state))


def test_an_answer_between_the_proof_read_and_the_park_releases_the_task(
    tmp_path, monkeypatch
):
    from task_proof_support import SCOPE as PROOF_SCOPE, Agent, drain, proofs

    from pathly_orchestrator.db.queries import task_waits

    repo, marker, tid, state = _proof_setup(tmp_path, exit_code=0)
    real = task_waits.open_questions_by_run
    reads: list = []

    def answered_right_after(conn, run_id):
        ids = real(conn, run_id)
        reads.append((run_id, ids))
        for qid in ids:
            _answer(PROOF_SCOPE, qid, "ANSWER-MARKER: hello")
        return ids

    monkeypatch.setattr(task_waits, "open_questions_by_run", answered_right_after)
    spawns: list = []

    class _AsksOnce(Agent):
        def __call__(self, state, instructions, adapter, model, run_id, broadcast_fn):
            spawns.append((run_id, instructions))
            if len(spawns) == 1:
                _ask(PROOF_SCOPE, run_id, "Which greeting?")
            return super().__call__(
                state, instructions, adapter, model, run_id, broadcast_fn
            )

    raw, _ = drain(state, _AsksOnce(repo))

    # The asking attempt waited (released at once, its answer in the next prompt) and the task
    # completed only after the next attempt was proven.
    assert [r for r, _ in spawns] == [f"sched-{tid}#1", f"sched-{tid}#2"]
    assert "ANSWER-MARKER: hello" in spawns[1][1]
    assert raw["completed"] == [tid]
    found = proofs(state)
    assert [p["run_id"] for p in found] == [f"sched-{tid}#2"], found
    assert marker.read_text() == "ran"
    assert _row(tid)["waits"] == 1


def test_park_and_recheck_reports_a_park_whose_recheck_fails(monkeypatch):
    from pathly_orchestrator.db.queries import task_waits
    from pathly_orchestrator.db.queries.comms_tasks import claim_task

    scope = SCOPE + "-recheck"
    tid = _task(scope, "Build the linker.")
    assert claim_task(_conn(), tid, run_id="r1")
    qid = _ask(scope, "r1", "Static or dynamic?")
    _answer(scope, qid, "Static.")

    def locked(conn, question_id):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(task_waits, "release_waiting_tasks", locked)
    assert task_waits.park_and_recheck(_conn(), tid, [qid]) == "parked"
    assert _row(tid)["task_status"] == "blocked"


def test_park_and_recheck_reports_a_release_the_answer_won(monkeypatch):
    from pathly_orchestrator.db.queries import task_waits
    from pathly_orchestrator.db.queries.comms_tasks import claim_task

    scope = SCOPE + "-won"
    tid = _task(scope, "Build the loader.")
    assert claim_task(_conn(), tid, run_id="r2")
    qid = _ask(scope, "r2", "Lazy or eager?")
    _answer(scope, qid, "Lazy.")
    real = task_waits.release_waiting_tasks

    def answer_released_it_first(conn, question_id):
        real(conn, question_id)  # the answer's own release_on_answer
        return []

    monkeypatch.setattr(task_waits, "release_waiting_tasks", answer_released_it_first)
    assert task_waits.park_and_recheck(_conn(), tid, [qid]) == "released"
    assert _row(tid)["task_status"] == "pending"


# ── review round 1: a released task that ran again and failed is not a wait ──────────────────


def test_a_drain_whose_waiting_task_ran_again_and_failed_is_not_a_wait():
    from pathly_orchestrator.supervisor.fan_out import _merge_drain_result
    from pathly_orchestrator.supervisor.task_wait_outcome import waits_for_answer

    scope = SCOPE + "-rerun"
    escalated = _task(scope, "Build the reporter.")
    parked = _task(scope, "Build the formatter.")
    conn = _conn()
    conn.execute(
        "UPDATE comms_messages SET task_status='blocked', fail_reason='retries exhausted' "
        "WHERE id=?",
        (escalated,),
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='blocked', fail_reason=? WHERE id=?",
        (f"{WAITING}:q1", parked),
    )
    conn.commit()

    rerun = {"failed": [escalated], "waiting": [escalated]}
    assert not waits_for_answer(_merge_drain_result(rerun, 0.0))
    still = {"failed": [escalated], "waiting": [escalated, parked]}
    assert waits_for_answer(_merge_drain_result(still, 0.0))
