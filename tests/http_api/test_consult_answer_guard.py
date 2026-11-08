"""chief-autopilot-round-two 17: a consult run cannot post its own answer.

A ``type: answer`` post frees the tasks parked on its question the moment it is written, before
the router measures what the consult changed, so a consult delivers its answer in its completion
summary and Pathly posts it. ``consult_guard`` (a ``before_request``) answers 403 to a
``POST /comms/answer``, and to a ``POST /comms/post`` with ``"type": "answer"``, from a live run
token whose run id starts ``consult-``. Its other posts pass, and so does an answer from anyone
else. A revoked consult token is still ``run_token_guard``'s 401.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, revoke_run_tokens
from pathly_orchestrator.db.queries.task_waits import park_task

BOARD, SCOPE, ROOT = "feature", "feat-consult-guard", "/proj"
CONSULT_RUN = "consult-0123456789ab"
REFUSAL = "a consult answers in its completion summary; Pathly posts the answer"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _token(run_id: str, role: str) -> str:
    return mint_run_token(get_db(), run_id, role, SCOPE, ROOT, BOARD, SCOPE)


def _parked_question() -> tuple[str, str]:
    """A claimed task parked on a question addressed to the architect: (task id, question id)."""
    conn = get_db()
    tid = post_message(conn, BOARD, SCOPE, "planner", type="task", text="build it")
    run = f"sched-{tid}#1"
    assert claim_task(conn, tid, run)
    qid = post_message(
        conn,
        BOARD,
        SCOPE,
        "builder",
        to_agent="architect",
        type="question",
        text="which store?",
    )
    assert park_task(conn, tid, [qid])
    return tid, qid


def _answers(qid: str) -> list:
    return (
        get_db()
        .execute(
            "SELECT id FROM comms_messages WHERE type='answer' AND reply_to=?", (qid,)
        )
        .fetchall()
    )


def _task_state(tid: str) -> tuple[str, str | None]:
    row = (
        get_db()
        .execute(
            "SELECT task_status, fail_reason FROM comms_messages WHERE id=?", (tid,)
        )
        .fetchone()
    )
    return row["task_status"], row["fail_reason"]


def _post(client, token: str | None, qid: str | None, msg_type: str, to: str = "*"):
    body = {
        "feature": SCOPE,
        "from": "architect",
        "type": msg_type,
        "text": f"a {msg_type} post",
        "board": BOARD,
        "scope": SCOPE,
        "to": to,
    }
    if qid is not None:
        body["reply_to"] = qid
    headers = {"X-Pathly-Run-Token": token} if token else {}
    return client.post("/comms/post", json=body, headers=headers)


def _answer_route(client, token: str | None, qid: str):
    headers = {"X-Pathly-Run-Token": token} if token else {}
    return client.post(
        "/comms/answer",
        json={"question_id": qid, "answer": "use sqlite"},
        headers=headers,
    )


def test_consult_answer_post_is_refused_stores_nothing_frees_nothing(client):
    tid, qid = _parked_question()
    token = _token(CONSULT_RUN, "architect")

    resp = _post(client, token, qid, "answer")

    assert resp.status_code == 403
    assert resp.get_json() == {"error": REFUSAL}
    assert _answers(qid) == []
    assert _task_state(tid) == ("blocked", f"waiting_for_answer:{qid}")


def test_consult_answer_route_is_refused_stores_nothing_frees_nothing(client):
    tid, qid = _parked_question()
    token = _token(CONSULT_RUN, "architect")

    resp = _answer_route(client, token, qid)

    assert resp.status_code == 403
    assert resp.get_json() == {"error": REFUSAL}
    assert _answers(qid) == []
    assert _task_state(tid) == ("blocked", f"waiting_for_answer:{qid}")


@pytest.mark.parametrize("msg_type", ["status", "question"])
def test_consult_other_posts_pass(client, msg_type):
    token = _token(CONSULT_RUN, "architect")
    # A question to the person routes to nobody, so no consult starts from this test.
    resp = _post(client, token, None, msg_type, to="human")
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["ok"] is True


@pytest.mark.parametrize("who", ["builder", "tokenless"])
def test_answer_post_from_anyone_else_passes(client, who):
    tid, qid = _parked_question()
    token = _token("sched-other#1", "builder") if who == "builder" else None

    resp = _post(client, token, qid, "answer")

    assert resp.status_code == 200, resp.get_json()
    assert len(_answers(qid)) == 1
    assert _task_state(tid)[0] == "pending"


@pytest.mark.parametrize("who", ["builder", "tokenless"])
def test_answer_route_from_anyone_else_passes(client, who):
    tid, qid = _parked_question()
    token = _token("sched-other#1", "builder") if who == "builder" else None

    resp = _answer_route(client, token, qid)

    assert resp.status_code == 200, resp.get_json()
    assert len(_answers(qid)) == 1
    assert _task_state(tid)[0] == "pending"


def test_revoked_consult_token_is_refused_by_run_token_guard(client):
    tid, qid = _parked_question()
    token = _token(CONSULT_RUN, "architect")
    assert revoke_run_tokens(get_db(), CONSULT_RUN) == 1

    for resp in (
        _post(client, token, qid, "answer"),
        _answer_route(client, token, qid),
        _post(client, token, None, "status"),
    ):
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "unknown run token"}
    assert _answers(qid) == []
    assert _task_state(tid) == ("blocked", f"waiting_for_answer:{qid}")


def test_a_body_that_is_not_json_reaches_the_route(client):
    token = _token(CONSULT_RUN, "architect")
    resp = client.post(
        "/comms/post",
        data=b"not json",
        headers={"X-Pathly-Run-Token": token, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Missing or invalid JSON body"}
