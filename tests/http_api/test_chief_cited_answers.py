"""chief-agent 10: a chief answers an agent only by citing a human message of its session.

Every case runs the real thing: a registered ``RunnerState`` with ``_await_agent_question``
waiting in a thread (or a real ``question`` row on the board), the chief gate, and the route. A
chief token's answer carries ``cite`` and nothing else; the gate checks the cited ``chief_human_
messages`` row (kind ``human``, this session, typed after the question was asked), records it as
cited once, and Pathly relays that message's own text. Callers without a chief token are
unchanged. The edge cases (odd ``cite`` values, encodings, other projects, codex) are in
``test_chief_cited_edges.py``.
"""

from __future__ import annotations

import time

import pytest
from chief_cite_support import (
    ALREADY,
    CITE_ONLY,
    NOT_CITED,
    TEXT,
    Session,
    acknowledged_by,
    answer_rows,
    ask,
    builder_headers,
    citations,
    db,
    later,
    post_row,
)
from chief_gate_support import _gated, _passed, app, client, other_project, project

TWO = [
    {"question": "CSV or JSON?", "options": [{"label": "CSV"}, {"label": "JSON"}]},
    {"question": "With a header row?", "options": [{"label": "yes"}]},
]


def _agent_answer(client, who, **body):
    return client.post("/runner/agent-answer", json=body, headers=who.headers)


# --- the question is kept on the run's state ------------------------------------------------


def test_while_it_waits_the_state_holds_the_question(ask):
    before = time.time()

    asker = ask("t-1", TWO)

    held = asker.state._agent_question
    assert held["question"] == "CSV or JSON?"
    assert held["options"] == [{"label": "CSV"}, {"label": "JSON"}]
    assert [q["question"] for q in held["questions"]] == [
        "CSV or JSON?",
        "With a header row?",
    ]
    assert before <= held["asked_at"] <= time.time()
    broadcast = asker.events[0]
    assert broadcast["type"] == "AGENT_QUESTION"
    assert broadcast["question"] == "CSV or JSON?"
    assert broadcast["options"] == held["options"]


@pytest.mark.parametrize("how", ["answered", "aborted"])
def test_the_question_is_cleared_on_every_exit(ask, how):
    from pathly_orchestrator.supervisor import supply_agent_answer

    asker = ask("t-1", TWO)
    assert asker.state._agent_question is not None

    if how == "answered":
        supply_agent_answer("t-1", "CSV")
    else:
        asker.state._abort_flag = True

    assert asker.answer() == ("CSV" if how == "answered" else None)
    assert asker.state._agent_question is None
    assert asker.state._awaiting_agent_answer is False


# --- /runner/agent-answer -------------------------------------------------------------------


def test_an_answer_without_cite_is_refused_and_the_question_stays_pending(
    client, project, ask
):
    chief = Session("operator", project)
    chief.type("use CSV")
    asker = ask("t-1")

    resp = _agent_answer(client, chief, topic="t-1")

    assert _gated(resp)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == NOT_CITED
    assert asker.still_waiting()
    assert citations() == []


@pytest.mark.parametrize(
    "which", ["style prompt", "relayed", "other session", "before the question"]
)
def test_a_message_that_cannot_be_cited_is_refused(
    client, project, other_project, ask, which
):
    chief = Session("operator", project)
    elsewhere = Session("operator", other_project)
    earlier = chief.type("use CSV, said before the question")
    later()
    asker = ask("t-1")
    cite = {
        "style prompt": chief.style_id,
        "relayed": chief.type("use CSV", relayed=True),
        "other session": elsewhere.type("use CSV"),
        "before the question": earlier,
    }[which]

    resp = _agent_answer(client, chief, topic="t-1", cite=cite)

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_CITED
    assert asker.still_waiting()
    assert citations() == []


def test_a_cite_with_words_of_the_chiefs_own_is_refused(client, project, ask):
    chief = Session("operator", project)
    asker = ask("t-1")
    typed = chief.type("use CSV")

    resp = _agent_answer(client, chief, topic="t-1", cite=typed, answer="CSV")

    assert _gated(resp)
    assert resp.get_json()["error"] == CITE_ONLY
    assert asker.still_waiting()
    assert citations() == []


def test_citing_a_message_typed_after_the_question_relays_its_text(
    client, project, ask
):
    chief = Session("operator", project)
    asker = ask("t-1", TWO)
    typed = chief.type(TEXT)

    resp = _agent_answer(client, chief, topic="t-1", cite=typed)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json() == {"status": "accepted", "topic": "t-1"}
    assert asker.answer() == TEXT
    assert asker.state._agent_question is None
    assert citations() == [
        {
            "run_id": chief.run_id,
            "message_id": typed,
            "route": "/runner/agent-answer",
            "target": "t-1",
        }
    ]


def test_a_message_answers_one_question_only(client, project, ask):
    chief = Session("operator", project)
    first, second = ask("t-1"), ask("t-2")
    typed = chief.type("use CSV")

    ok = _agent_answer(client, chief, topic="t-1", cite=typed)
    again = _agent_answer(client, chief, topic="t-2", cite=typed)

    assert ok.status_code == 200
    assert first.answer() == "use CSV"
    assert _gated(again)
    assert again.get_json()["error"] == ALREADY
    assert second.still_waiting()
    assert len(citations()) == 1


def test_a_message_older_than_the_next_question_cannot_answer_it(client, project, ask):
    chief = Session("operator", project)
    first = ask("t-1")
    typed = chief.type("use CSV")
    assert _agent_answer(client, chief, topic="t-1", cite=typed).status_code == 200
    assert first.answer() == "use CSV"
    later()
    second = ask("t-2")

    resp = _agent_answer(client, chief, topic="t-2", cite=typed)

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_CITED
    assert second.still_waiting()


# --- /comms/answer --------------------------------------------------------------------------


def _comms_answer(client, who, **body):
    return client.post("/comms/answer", json=body, headers=who.headers)


def test_a_board_answer_without_cite_is_refused(client, project):
    chief = Session("operator", project)
    chief.type("use CSV")
    question = post_row("question", options=[{"id": "a", "label": "A"}])

    resp = _comms_answer(client, chief, question_id=question)

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_CITED
    assert answer_rows(question) == []
    assert citations() == []


@pytest.mark.parametrize(
    "which", ["style prompt", "relayed", "other session", "before the question"]
)
def test_a_board_answer_cannot_cite_what_cannot_be_cited(
    client, project, other_project, which
):
    chief = Session("operator", project)
    elsewhere = Session("operator", other_project)
    earlier = chief.type("use CSV, said before the question")
    later()
    question = post_row("question")
    later()
    cite = {
        "style prompt": chief.style_id,
        "relayed": chief.type("use CSV", relayed=True),
        "other session": elsewhere.type("use CSV"),
        "before the question": earlier,
    }[which]

    resp = _comms_answer(client, chief, question_id=question, cite=cite)

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_CITED
    assert answer_rows(question) == []
    assert citations() == []


@pytest.mark.parametrize("own", [{"answer": "A"}, {"option_id": "a"}])
def test_a_board_answer_with_words_or_an_option_of_the_chiefs_own_is_refused(
    client, project, own
):
    chief = Session("operator", project)
    question = post_row("question", options=[{"id": "a", "label": "A"}])
    typed = chief.type("A")

    resp = _comms_answer(client, chief, question_id=question, cite=typed, **own)

    assert _gated(resp)
    assert resp.get_json()["error"] == CITE_ONLY
    assert answer_rows(question) == []
    assert citations() == []


def test_a_board_answer_stores_the_cited_text(client, project):
    chief = Session("operator", project)
    question = post_row("question", options=[{"id": "a", "label": "A"}])
    later()
    typed = chief.type(TEXT)

    resp = _comms_answer(client, chief, question_id=question, cite=typed)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert answer_rows(question) == [TEXT]
    assert citations() == [
        {
            "run_id": chief.run_id,
            "message_id": typed,
            "route": "/comms/answer",
            "target": question,
        }
    ]


def test_a_board_answer_cites_a_message_once(client, project):
    chief = Session("operator", project)
    first, second = post_row("question"), post_row("question")
    later()
    typed = chief.type("use CSV")

    ok = _comms_answer(client, chief, question_id=first, cite=typed)
    again = _comms_answer(client, chief, question_id=second, cite=typed)

    assert ok.status_code == 200
    assert _gated(again)
    assert again.get_json()["error"] == ALREADY
    assert answer_rows(second) == []


# --- a human escalation is closed only by a cited message ------------------------------------


def _acknowledge(client, who, escalation, **extra):
    body = {"message_id": escalation, "agent": "chief", **extra}
    return client.post("/comms/acknowledge", json=body, headers=who.headers)


def test_an_operator_acknowledges_a_human_escalation_with_a_cite_typed_after_it(
    client, project
):
    chief = Session("operator", project)
    escalation = post_row("escalation", to_agent="human")
    later()
    typed = chief.type("go ahead with the migration")

    resp = _acknowledge(client, chief, escalation, cite=typed)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert "chief" in acknowledged_by(escalation)
    assert citations() == [
        {
            "run_id": chief.run_id,
            "message_id": typed,
            "route": "/comms/acknowledge",
            "target": escalation,
        }
    ]


def test_a_human_escalation_stays_open_without_a_cite_or_with_an_older_one(
    client, project
):
    chief = Session("operator", project)
    earlier = chief.type("said before the escalation")
    later()
    escalation = post_row("escalation", to_agent="human")

    for extra in ({}, {"cite": earlier}):
        resp = _acknowledge(client, chief, escalation, **extra)
        assert _gated(resp)
        assert resp.get_json()["error"] == NOT_CITED

    assert acknowledged_by(escalation) == []
    assert citations() == []


def test_a_builder_token_still_cannot_close_a_human_escalation(client, project):
    chief = Session("operator", project)
    escalation = post_row("escalation", to_agent="human")
    later()
    typed = chief.type("go ahead")
    headers = builder_headers(project)

    resp = client.post(
        "/comms/acknowledge",
        json={"message_id": escalation, "agent": "builder", "cite": typed},
        headers=headers,
    )

    assert _passed(resp)
    assert resp.status_code == 403
    assert "only a human closes" in resp.get_json()["error"]
    assert acknowledged_by(escalation) == []
    assert citations() == []


# --- everyone else is unchanged ---------------------------------------------------------------


@pytest.mark.parametrize("caller", ["no token", "builder token"])
def test_callers_without_a_chief_token_get_the_answer_they_sent(
    client, project, ask, caller
):
    headers = {} if caller == "no token" else builder_headers(project)
    asker = ask("t-1")
    question = post_row("question")

    agent = client.post(
        "/runner/agent-answer", json={"topic": "t-1", "answer": "yes"}, headers=headers
    )
    board = client.post(
        "/comms/answer",
        json={"question_id": question, "answer": "A", "option_id": "a"},
        headers=headers,
    )

    assert agent.status_code == 200, agent.get_data(as_text=True)
    assert asker.answer() == "yes"
    assert board.status_code == 200, board.get_data(as_text=True)
    assert answer_rows(question) == ["A"]
    assert citations() == []
    assert db().execute("SELECT COUNT(*) FROM chief_human_messages").fetchone()[0] == 0
