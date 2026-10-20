"""chief-agent 10: the edges of the cite rule.

The Done-when cases are in ``test_chief_cited_answers.py``. These pin what a reviewer would ask
next: values of ``cite`` that are not a message number, the boundary of "at or after", a body only
one reader understands, a topic of another project or one that asks nothing, a codex chief, the
limit the rule documents (it binds the user's words, not the user's intent), and the two helpers
the routes read through.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from chief_cite_support import (
    CITE_ONLY,
    NOT_CITED,
    NOT_OWN,
    Session,
    answer_rows,
    ask,
    citations,
    db,
    idle,
    post_row,
)
from chief_gate_support import (
    _gated,
    _passed,
    _send,
    app,
    client,
    other_project,
    project,
)


def _agent_answer(client, who, **body):
    return client.post("/runner/agent-answer", json=body, headers=who.headers)


def _comms_answer(client, who, **body):
    return client.post("/comms/answer", json=body, headers=who.headers)


# --- what `cite` may be ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda n: str(n),
        lambda n: float(n),
        lambda n: [n],
        lambda n: {"id": n},
        lambda n: None,
        lambda n: -n,
        lambda n: n + 1000,
    ],
    ids=["string", "float", "list", "object", "null", "negative", "unknown"],
)
def test_cite_is_a_message_number_and_nothing_else(client, project, ask, make):
    chief = Session("operator", project)
    asker = ask("t-1")
    typed = chief.type("use CSV")

    resp = _agent_answer(client, chief, topic="t-1", cite=make(typed))

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_CITED
    assert asker.still_waiting()
    assert citations() == []


def test_true_is_not_message_number_one(client, project, ask):
    chief = Session("operator", project)
    db().execute(
        "UPDATE chief_human_messages SET kind = 'human' WHERE id = ?",
        (chief.style_id,),
    )
    db().commit()
    assert chief.style_id == 1
    asker = ask("t-1")

    refused = _agent_answer(client, chief, topic="t-1", cite=True)

    assert _gated(refused)
    assert refused.get_json()["error"] == NOT_CITED
    assert asker.still_waiting()


# --- "at or after" ---------------------------------------------------------------------------


@pytest.mark.parametrize("shift,accepted", [(0.0, True), (-0.001, False)])
def test_a_message_stamped_with_the_asking_time_counts_and_one_just_before_does_not(
    client, project, ask, shift, accepted
):
    chief = Session("operator", project)
    asker = ask("t-1")
    typed = chief.type("use CSV")
    asked_at = asker.state._agent_question["asked_at"]
    db().execute(
        "UPDATE chief_human_messages SET ts = ? WHERE id = ?", (asked_at + shift, typed)
    )
    db().commit()

    resp = _agent_answer(client, chief, topic="t-1", cite=typed)

    assert (resp.status_code == 200) is accepted, resp.get_data(as_text=True)
    assert _gated(resp) is not accepted


@pytest.mark.parametrize("shift,accepted", [(0.0, True), (-0.001, False)])
def test_the_same_boundary_holds_against_a_board_question(
    client, project, shift, accepted
):
    chief = Session("operator", project)
    question = post_row("question")
    typed = chief.type("use CSV")
    asked = (
        db()
        .execute("SELECT ts FROM comms_messages WHERE id = ?", (question,))
        .fetchone()
    )
    db().execute(
        "UPDATE chief_human_messages SET ts = ? WHERE id = ?",
        (datetime.fromisoformat(asked["ts"]).timestamp() + shift, typed),
    )
    db().commit()

    resp = _comms_answer(client, chief, question_id=question, cite=typed)

    assert (resp.status_code == 200) is accepted, resp.get_data(as_text=True)
    assert answer_rows(question) == (["use CSV"] if accepted else [])


def test_a_board_question_whose_time_cannot_be_read_cannot_be_answered(client, project):
    chief = Session("operator", project)
    question = post_row("question")
    typed = chief.type("use CSV")
    db().execute("UPDATE comms_messages SET ts = 'garbage' WHERE id = ?", (question,))
    db().commit()

    resp = _comms_answer(client, chief, question_id=question, cite=typed)

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_CITED
    assert answer_rows(question) == []


# --- a body only one reader understands --------------------------------------------------------


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32-le"])
def test_an_encoded_body_is_cited_like_a_plain_one(client, project, ask, encoding):
    chief = Session("operator", project)
    asker = ask("t-1")
    typed = chief.type("use CSV")

    resp = _send(
        client,
        "/runner/agent-answer",
        {"topic": "t-1", "cite": typed},
        encoding,
        chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert asker.answer() == "use CSV"
    assert len(citations()) == 1


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32-be"])
@pytest.mark.parametrize(
    "path,target",
    [("/runner/agent-answer", "topic"), ("/comms/answer", "question_id")],
)
def test_words_hidden_in_an_encoded_body_are_refused(
    client, project, ask, path, target, encoding
):
    chief = Session("operator", project)
    asker = ask("t-1")
    typed = chief.type("use CSV")
    body = {target: "t-1", "answer": "CSV", "cite": typed}

    resp = _send(client, path, body, encoding, chief.headers)

    assert _gated(resp)
    assert resp.get_json()["error"] == CITE_ONLY
    assert asker.still_waiting()
    assert citations() == []


def test_an_option_is_not_a_key_the_agent_answer_route_takes(client, project, ask):
    chief = Session("operator", project)
    asker = ask("t-1")

    resp = _agent_answer(
        client, chief, topic="t-1", cite=chief.type("use CSV"), option_id="a"
    )

    assert _gated(resp)
    assert "option_id" in resp.get_json()["error"]
    assert asker.still_waiting()
    assert citations() == []


def test_readings_of_the_body_that_disagree_are_refused(app, project, ask):
    """No input makes the gate's two readings of a body differ today, so this calls the rule
    with two readings, as it would be called if one did: it cites nothing unless they agree on
    the message and on what it answers.
    """
    from pathly_orchestrator.http_server.chief_cite import cite_refusal

    chief = Session("operator", project)
    row = db().execute("SELECT * FROM chief_sessions WHERE run_id = ?", (chief.run_id,))
    session = dict(row.fetchone())
    ask("t-1")
    ask("t-2")
    first, second = chief.type("use CSV"), chief.type("use JSON")
    here = {"topic": "t-1", "cite": first}

    with app.test_request_context("/runner/agent-answer", method="POST"):
        for other in (
            {"topic": "t-1", "cite": second},
            {"topic": "t-2", "cite": first},
            {"cite": first},
        ):
            refusal = cite_refusal("/runner/agent-answer", session, db(), [here, other])
            assert refusal == NOT_CITED
        assert citations() == []
        assert (
            cite_refusal("/runner/agent-answer", session, db(), [here, dict(here)])
            is None
        )
    assert len(citations()) == 1


def test_every_answer_route_names_what_its_answer_is_for():
    from pathly_orchestrator.http_server.chief_cite import TARGET_KEYS
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS

    answers = {
        rule for (rule, _), action in ROUTE_ACTIONS.items() if action == "answer"
    }

    # An acknowledgement is an answer only for a human escalation (chief_routes refines it).
    assert answers | {"/comms/acknowledge"} == set(TARGET_KEYS)


# --- which run, which project ----------------------------------------------------------------


def test_a_topic_of_another_project_cannot_be_answered(
    client, project, other_project, ask
):
    chief = Session("operator", project)
    asker = ask("t-1", root=other_project)
    typed = chief.type("use CSV")

    resp = _agent_answer(client, chief, topic="t-1", cite=typed)

    assert _gated(resp)
    assert resp.get_json()["error"] == NOT_OWN
    assert asker.still_waiting()
    assert citations() == []


def test_a_topic_that_asks_nothing_is_left_to_the_route(client, project, idle):
    chief = Session("operator", project)
    idle("t-idle")
    typed = chief.type("use CSV")

    waiting_for_nothing = _agent_answer(client, chief, topic="t-idle", cite=typed)
    unknown = _agent_answer(client, chief, topic="t-none", cite=chief.type("again"))

    assert _passed(waiting_for_nothing)
    assert waiting_for_nothing.status_code == 409
    assert "not awaiting" in waiting_for_nothing.get_json()["error"]
    assert _passed(unknown)
    assert unknown.status_code == 404


@pytest.mark.parametrize("topic", ["", "   ", None, 7])
def test_a_call_the_route_rejects_for_its_target_spends_no_citation(
    client, project, topic
):
    chief = Session("operator", project)
    typed = chief.type("use CSV")

    resp = _agent_answer(client, chief, topic=topic, cite=typed)

    assert _passed(resp)
    assert resp.status_code == 400
    assert citations() == []


# --- codex ---------------------------------------------------------------------------------------


def test_a_codex_chief_has_nothing_to_cite_and_is_told_so(client, project, ask):
    chief = Session("operator", project, engine="codex")
    asker = ask("t-1")

    resp = _agent_answer(client, chief, topic="t-1", cite=chief.style_id)

    assert _gated(resp)
    assert "codex" in resp.get_json()["error"]
    assert resp.get_json()["error"].startswith(NOT_CITED)
    assert asker.still_waiting()
    assert citations() == []


# --- the limit the rule documents ------------------------------------------------------------


def test_a_chief_can_still_cite_an_unrelated_later_message(client, project, ask):
    """The rule binds the user's real words to the question the chief picked, not the user's
    intent: the agent gets the unrelated remark word for word. The user reading the board is
    what catches it (spec § Risks).
    """
    chief = Session("operator", project)
    asker = ask("t-1")
    chatter = chief.type("what is the weather like?")

    resp = _agent_answer(client, chief, topic="t-1", cite=chatter)

    assert resp.status_code == 200
    assert asker.answer() == "what is the weather like?"


# --- the two helpers the routes read through ---------------------------------------------------


def test_answer_text_is_the_cited_text_for_a_chief_and_the_body_for_anyone_else(app):
    from flask import g

    from pathly_orchestrator.http_server.chief_cite import answer_text

    with app.test_request_context("/runner/agent-answer", method="POST"):
        assert answer_text({"answer": "from the body"}) == "from the body"
        assert answer_text({}) == ""
        g.chief_cited_text = "what the person typed"
        assert answer_text({"answer": "from the body"}) == "what the person typed"
        assert answer_text({}) == "what the person typed"


def test_the_human_gate_opens_for_the_one_message_the_gate_cited(app, project):
    from flask import g, request

    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        refuse_agent_on_human_gate,
    )

    chief = Session("operator", project)
    escalation, other = (post_row("escalation", to_agent="human") for _ in range(2))

    with app.test_request_context(
        "/comms/acknowledge", method="POST", headers=chief.headers
    ):
        assert refuse_agent_on_human_gate(db(), request, escalation)[1] == 403
        g.chief_cited_gate = other
        assert refuse_agent_on_human_gate(db(), request, escalation)[1] == 403
        g.chief_cited_gate = escalation
        assert refuse_agent_on_human_gate(db(), request, escalation) is None
