"""chief-autopilot-round-two 07: a single run's unfinished task parks on its role question.

A board/single run whose drain-dag agent claimed a task, posted a ``question`` to a role (with the
spawn's run token) and ended with the task still ``in_progress`` parks the task on that question
(``task_waits.asked_questions_by_run`` + ``park_and_recheck``): ``blocked``,
``waiting_for_answer:<id>``, and the run fails ``waiting_for_answer``. When the answer is already
on the board as the run ends, the park is released at once: the task is ``pending`` with
``answered_questions``, one wait counted, and the run's error is ``answer_ready``. A role answer
posted later frees a parked task and its ready row carries the question and answer. A task the
agent completed after asking stays ``done``.

No spawn host is registered here, so the posted role question starts no consult
(``consult_router.on_question`` answers ``no_host``); the tests answer it themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathly_orchestrator.supervisor.registry import get_run
from pathly_orchestrator.supervisor.state import RunnerState

SCOPE = "feat-single-ask"
DRAIN_DAG_CLAIM = {"run_id": "$GOAL_ID-single"}
WAITING = "waiting_for_answer"
ANSWER_READY = "answer_ready"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _no_consult(monkeypatch):
    """A role question must never start a real consult here."""
    import pathly_orchestrator.supervisor.consult_router as _router

    monkeypatch.setattr(
        _router, "start_consult", lambda *a, **k: {"started": False, "reason": "test"}
    )


@pytest.fixture(autouse=True)
def _no_reconciliation_window(monkeypatch):
    """The billing window waits for a PTY result that no real process sends here."""
    import pathly_orchestrator.supervisor.terminal as _terminal
    from pathly_orchestrator.supervisor.registry import drop_run

    monkeypatch.setattr(
        _terminal, "_reconciliation_window", lambda run, *a, **k: drop_run(run.run_id)
    )


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _state(tmp_path: Path) -> RunnerState:
    storage = tmp_path / "pathly" / "features" / SCOPE
    storage.mkdir(parents=True, exist_ok=True)
    state = RunnerState(
        topic=SCOPE,
        flow="board-run",
        project_root=str(tmp_path),
        model="m",
        timeout=60,
        run_id="unused",
        current_state="builder",
        board_scope=SCOPE,
    )
    state.executor_owned_telemetry = True
    state.interactive = False
    state.storage_path = str(storage)
    return state


def _task(text: str = "Build X. Files: a. Done when: b.") -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    conn = _conn()
    tid = post_message(
        conn, board="feature", scope=SCOPE, from_agent="planner", type="task", text=text
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on='[]' WHERE id=?",
        (tid,),
    )
    conn.commit()
    return tid


def _row(tid: str) -> dict:
    row = (
        _conn()
        .execute(
            "SELECT task_status, claimed_by, attempts, waits, fail_reason, "
            "answered_questions FROM comms_messages WHERE id=?",
            (tid,),
        )
        .fetchone()
    )
    return dict(row)


def _answer(client, question_id: str, text: str, frm: str = "architect") -> None:
    r = client.post(
        "/comms/post",
        json={
            "feature": SCOPE,
            "board": "feature",
            "scope": SCOPE,
            "from": frm,
            "type": "answer",
            "text": text,
            "reply_to": question_id,
        },
    )
    assert r.status_code == 200, r.data


def _spawn(
    client,
    tmp_path: Path,
    run_id: str,
    tid: str,
    *,
    ask: str = "Which store, SQLite or files? I will use SQLite.",
    answer_before_end: str | None = None,
    finish_task: bool = False,
) -> dict:
    """One board spawn: its agent claims ``tid`` with drain-dag's body and its run token, asks
    the architect, optionally sees the answer posted (as the consult would) or completes the
    task, then ends without an ``AGENT_DONE`` of its own."""
    from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal

    seen: dict = {}

    def broadcast(_topic, payload):
        if payload.get("type") != "TERMINAL_SPAWN":
            return
        headers = {"X-Pathly-Run-Token": payload["run_token"]}
        r = client.post(
            "/comms/tasks/claim",
            json={"message_id": tid, **DRAIN_DAG_CLAIM},
            headers=headers,
        )
        seen["claim"] = r.get_json()
        r = client.post(
            "/comms/post",
            json={
                "feature": SCOPE,
                "board": "feature",
                "scope": SCOPE,
                "from": "builder",
                "to": "architect",
                "type": "question",
                "text": ask,
            },
            headers=headers,
        )
        assert r.status_code == 200, r.data
        seen["question"] = r.get_json()["message_id"]
        if answer_before_end:
            _answer(client, seen["question"], answer_before_end)
        if finish_task:
            r = client.post(
                "/comms/tasks/complete",
                json={"message_id": tid, "feature": SCOPE},
                headers=headers,
            )
            assert r.status_code == 200, r.data
        run = get_run(run_id)
        assert run is not None
        run.mark_started()
        run.mark_pty_result({"result": {}, "exit_code": 0})

    seen["result"] = _run_stage_via_terminal(
        _state(tmp_path), "drain the dag", "claude", "m", run_id, broadcast
    )
    return seen


def _detail(client, run_id: str) -> dict:
    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200, r.data
    return r.get_json()["run"]


def _ready(client) -> dict:
    r = client.get(f"/comms/tasks?ready=true&feature={SCOPE}&scope={SCOPE}")
    assert r.status_code == 200, r.data
    return {t["id"]: t for t in r.get_json()}


def _run_id(n: int) -> str:
    return f"{n:08d}-bbbb-4bbb-8bbb-{n:012d}"


def test_an_unfinished_task_that_asked_a_role_parks_and_the_run_waits(
    client, tmp_path
):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid)
    assert seen["claim"]["claimed"] is True
    qid = seen["question"]

    assert seen["result"]["outcome"] == "failed"
    assert seen["result"]["error"] == WAITING
    row = _row(tid)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{qid}"
    assert row["waits"] == 1

    run = _detail(client, _run_id(1))
    assert run["outcome"] == "failed"
    assert run["error"] == WAITING


def test_an_answer_already_posted_releases_the_task_and_the_run_is_answer_ready(
    client, tmp_path
):
    tid = _task()
    seen = _spawn(
        client, tmp_path, _run_id(1), tid, answer_before_end="Files: one per goal."
    )
    qid = seen["question"]

    assert seen["result"]["outcome"] == "failed"
    assert seen["result"]["error"] == ANSWER_READY
    row = _row(tid)
    assert row["task_status"] == "pending"
    assert row["claimed_by"] is None
    assert row["fail_reason"] is None
    assert json.loads(row["answered_questions"]) == [qid]
    assert row["waits"] == 1
    assert row["attempts"] - row["waits"] == 0

    run = _detail(client, _run_id(1))
    assert run["outcome"] == "failed"
    assert run["error"] == ANSWER_READY


def test_a_role_answer_posted_later_frees_the_task_with_its_answer(client, tmp_path):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid, ask="SQLite or files?")
    assert _row(tid)["task_status"] == "blocked"

    _answer(client, seen["question"], "SQLite, the board's own DB.")
    row = _row(tid)
    assert row["task_status"] == "pending"
    assert not (row["fail_reason"] or "").startswith(WAITING)
    assert _ready(client)[tid]["answered_questions"] == [
        {"question": "SQLite or files?", "answer": "SQLite, the board's own DB."}
    ]


def test_a_task_completed_after_asking_stays_done(client, tmp_path):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid, finish_task=True)
    assert seen["result"].get("outcome") != "failed"
    row = _row(tid)
    assert row["task_status"] == "done"
    assert row["waits"] == 0
    assert _detail(client, _run_id(1))["status"] == "done"
