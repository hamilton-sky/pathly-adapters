"""chief-autopilot 06: a single run's task parks on its open question and is freed by any answer.

A board/single run whose agent claimed a task, posted a board ``question`` to ``human`` (with the
spawn's run token, so the question carries the run as ``author_run_id``) and ended with the task
still ``in_progress``:

* parks the task: ``task_status='blocked'``, ``fail_reason='waiting_for_answer:<ids>'`` and one
  more ``waits`` (``attempts`` only grows, and the attempt limit counts ``attempts - waits``);
* fails the run with ``error: waiting_for_answer`` (not ``task_unfinished``).

An answer through ``/comms/answer`` or a ``type: answer`` post with ``reply_to`` frees the task
(back to ``pending``) once every question it waits for is answered, and the ready-tasks row then
carries ``answered_questions: [{question, answer}]``. A question to a role parks a task too
(round two 07), a dependent of a parked task is never deadlocked, and an answer after the task was deleted is
stored and changes nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathly_orchestrator.supervisor.registry import get_run
from pathly_orchestrator.supervisor.state import RunnerState

SCOPE = "feat-wait"
DRAIN_DAG_CLAIM = {"run_id": "$GOAL_ID-single"}
WAITING = "waiting_for_answer"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


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
        model="claude-sonnet-4-6",
        timeout=60,
        run_id="unused",
        current_state="builder",
        board_scope=SCOPE,
    )
    state.executor_owned_telemetry = True
    state.interactive = False
    state.storage_path = str(storage)
    return state


def _task(text: str = "Build X. Files: a. Done when: b.", deps=None) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    conn = _conn()
    tid = post_message(
        conn, board="feature", scope=SCOPE, from_agent="planner", type="task", text=text
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
        (json.dumps(deps or []), tid),
    )
    conn.commit()
    return tid


def _row(tid: str) -> dict:
    row = (
        _conn()
        .execute(
            "SELECT task_status, claimed_by, attempts, waits, fail_reason "
            "FROM comms_messages WHERE id=?",
            (tid,),
        )
        .fetchone()
    )
    return dict(row)


def _spawn(
    client,
    tmp_path: Path,
    run_id: str,
    tid: str,
    *,
    questions: tuple = (),
    finish_task: bool = False,
) -> dict:
    """Run one board spawn. Its agent claims ``tid`` with drain-dag's literal body and its run
    token, posts each ``(to, text)`` question with that token, optionally marks the task done,
    then ends without an ``AGENT_DONE`` of its own."""
    from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal

    state = _state(tmp_path)
    seen: dict = {"questions": []}

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
        for to, text in questions:
            r = client.post(
                "/comms/post",
                json={
                    "feature": SCOPE,
                    "board": "feature",
                    "scope": SCOPE,
                    "from": "builder",
                    "to": to,
                    "type": "question",
                    "text": text,
                },
                headers=headers,
            )
            assert r.status_code == 200, r.data
            seen["questions"].append(r.get_json()["message_id"])
        if finish_task:
            conn = _conn()
            conn.execute(
                "UPDATE comms_messages SET task_status='done' WHERE id=?", (tid,)
            )
            conn.commit()
        run = get_run(run_id)
        assert run is not None
        run.mark_started()
        run.mark_pty_result({"result": {}, "exit_code": 0})

    seen["result"] = _run_stage_via_terminal(
        state, "drain the dag", "claude", "m", run_id, broadcast
    )
    return seen


def _answer_via_route(client, question_id: str, text: str = "Use plan B."):
    r = client.post("/comms/answer", json={"question_id": question_id, "answer": text})
    assert r.status_code == 200, r.data


def _answer_via_post(client, question_id: str, text: str = "Use plan B."):
    r = client.post(
        "/comms/post",
        json={
            "feature": SCOPE,
            "board": "feature",
            "scope": SCOPE,
            "from": "human",
            "type": "answer",
            "text": text,
            "reply_to": question_id,
        },
    )
    assert r.status_code == 200, r.data


def _detail(client, run_id: str) -> dict:
    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200, r.data
    return r.get_json()["run"]


def _escalations() -> int:
    row = (
        _conn()
        .execute(
            "SELECT COUNT(*) n FROM comms_messages WHERE type='escalation' AND scope=?",
            (SCOPE,),
        )
        .fetchone()
    )
    return int(row["n"])


def _run_id(n: int) -> str:
    return f"{n:08d}-aaaa-4aaa-8aaa-{n:012d}"


def test_a_run_that_asked_parks_its_task_and_fails_waiting(client, tmp_path):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid, questions=(("human", "A or B?"),))
    assert seen["claim"]["claimed"] is True
    qid = seen["questions"][0]

    assert seen["result"]["outcome"] == "failed"
    assert seen["result"]["error"] == WAITING
    row = _row(tid)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{qid}"
    assert row["attempts"] == 1
    assert row["waits"] == 1

    run = _detail(client, _run_id(1))
    assert run["status"] == "error"
    assert run["outcome"] == "failed"
    assert run["error"] == WAITING


def test_three_waits_spend_no_retry(client, tmp_path):
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(_conn(), "goal.task_max_attempts", "2")
    tid = _task()
    for n in range(1, 4):
        seen = _spawn(
            client, tmp_path, _run_id(n), tid, questions=(("human", f"Q{n}?"),)
        )
        assert _row(tid)["task_status"] == "blocked"
        _answer_via_route(client, seen["questions"][0])
        assert _row(tid)["task_status"] == "pending"

    row = _row(tid)
    assert row["attempts"] == 3
    assert row["waits"] == 3
    # The fourth run asks nothing and leaves the task unfinished: one claim counted, under 2.
    _spawn(client, tmp_path, _run_id(4), tid)
    row = _row(tid)
    assert row["attempts"] - row["waits"] == 1
    assert row["task_status"] == "pending"
    assert row["fail_reason"] == "task_unfinished"
    assert _escalations() == 0


def test_the_loop_retry_limit_counts_attempts_minus_waits(client):
    from pathly_orchestrator.supervisor.task_retry import resolve_task_failure

    conn = _conn()
    tid = _task()
    conn.execute(
        "UPDATE comms_messages SET task_status='in_progress', attempts=4, waits=3 "
        "WHERE id=?",
        (tid,),
    )
    conn.commit()
    decision, _ = resolve_task_failure(
        conn,
        tid,
        4,
        "boom",
        board="feature",
        scope=SCOPE,
        goal_id=None,
        text="Build X.",
        lane="L",
        max_attempts=2,
    )
    assert decision == "retried"
    assert _escalations() == 0


def test_a_question_to_a_role_does_not_park(client, tmp_path):
    """Round two (07) changed this: a question to a role now parks the unfinished task."""
    tid = _task()
    seen = _spawn(
        client, tmp_path, _run_id(1), tid, questions=(("architect", "Which store?"),)
    )
    qid = seen["questions"][0]
    assert seen["result"]["error"] == WAITING
    row = _row(tid)
    assert row["task_status"] == "blocked"
    assert row["fail_reason"] == f"{WAITING}:{qid}"
    assert row["waits"] == 1


@pytest.mark.parametrize("answer", [_answer_via_route, _answer_via_post])
def test_any_answer_frees_the_task(client, tmp_path, answer):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid, questions=(("human", "A or B?"),))
    answer(client, seen["questions"][0])
    row = _row(tid)
    assert row["task_status"] == "pending"
    assert row["claimed_by"] is None
    assert not (row["fail_reason"] or "").startswith(WAITING)


def test_with_two_questions_it_waits_for_both(client, tmp_path):
    tid = _task()
    seen = _spawn(
        client,
        tmp_path,
        _run_id(1),
        tid,
        questions=(("human", "A or B?"), ("*", "Which port?")),
    )
    q1, q2 = seen["questions"]
    assert _row(tid)["fail_reason"] == f"{WAITING}:{q1},{q2}"

    _answer_via_post(client, q1)
    assert _row(tid)["task_status"] == "blocked"
    _answer_via_route(client, q2, "8080")
    assert _row(tid)["task_status"] == "pending"


def test_a_dependent_of_the_parked_task_is_not_deadlocked(client, tmp_path):
    from pathly_orchestrator.supervisor.task_retry import detect_deadlocks

    tid = _task()
    child = _task("Build Y after X.", deps=[tid])
    grandchild = _task("Build Z after Y.", deps=[child])
    _spawn(client, tmp_path, _run_id(1), tid, questions=(("human", "A or B?"),))
    assert _row(tid)["task_status"] == "blocked"

    assert detect_deadlocks(_conn(), "feature", SCOPE) == []
    assert _row(child)["task_status"] == "pending"
    assert _row(grandchild)["task_status"] == "pending"


def test_the_ready_row_of_the_freed_task_carries_question_and_answer(client, tmp_path):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid, questions=(("human", "A or B?"),))
    _answer_via_route(client, seen["questions"][0], "B, the cheaper one.")

    r = client.get(f"/comms/tasks?ready=true&feature={SCOPE}&scope={SCOPE}")
    assert r.status_code == 200, r.data
    rows = {t["id"]: t for t in r.get_json()}
    assert rows[tid]["answered_questions"] == [
        {"question": "A or B?", "answer": "B, the cheaper one."}
    ]


def test_answering_after_the_task_was_deleted_stores_the_answer(client, tmp_path):
    tid = _task()
    seen = _spawn(client, tmp_path, _run_id(1), tid, questions=(("human", "A or B?"),))
    qid = seen["questions"][0]
    conn = _conn()
    conn.execute(
        "UPDATE comms_messages SET deleted_at='2026-01-01T00:00:00Z' WHERE id=?",
        (tid,),
    )
    conn.commit()

    _answer_via_route(client, qid)
    answers = conn.execute(
        "SELECT COUNT(*) n FROM comms_messages WHERE type='answer' AND reply_to=?",
        (qid,),
    ).fetchone()
    assert answers["n"] == 1
    assert _row(tid)["task_status"] == "blocked"


def test_a_run_with_an_open_question_whose_task_is_done_keeps_success(client, tmp_path):
    tid = _task()
    seen = _spawn(
        client,
        tmp_path,
        _run_id(1),
        tid,
        questions=(("human", "FYI?"),),
        finish_task=True,
    )
    assert seen["result"].get("outcome") != "failed"
    assert _row(tid)["task_status"] == "done"
    assert _detail(client, _run_id(1))["status"] == "done"
