"""chief-agent 10 (review round 1): a human escalation, from the chief's side.

A chief closes a human-addressed escalation only through ``/comms/acknowledge``, with a cite of a
human message typed after it (``test_chief_cited_answers.py``), and only as ``chief``: the
``agent`` it sends is stored on the row, so the board must not read as if the person closed the
gate. The other answer routes stay shut to it: ``/comms/answer`` on an escalation is the human
gate's 403 even with a good cite.
"""

from __future__ import annotations

import pytest
from chief_cite_support import (
    AS_CHIEF,
    Session,
    acknowledged_by,
    answer_rows,
    citations,
    later,
    post_row,
)
from chief_gate_support import _gated, _passed, app, client, project


def _typed_after_an_escalation(project):
    chief = Session("operator", project)
    escalation = post_row("escalation", to_agent="human")
    later()
    return chief, escalation, chief.type("go ahead with the migration")


def _acknowledge(client, who, escalation, **extra):
    body = {"message_id": escalation, **extra}
    return client.post("/comms/acknowledge", json=body, headers=who.headers)


def test_a_chief_closes_a_human_escalation_as_chief_and_the_row_says_so(
    client, project
):
    chief, escalation, typed = _typed_after_an_escalation(project)

    resp = _acknowledge(client, chief, escalation, agent="chief", cite=typed)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert acknowledged_by(escalation) == ["chief"]
    assert len(citations()) == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"agent": "human"},
        {"agent": "Human"},
        {"agent": "Chief"},
        {"agent": "chief "},
        {"agent": ""},
        {"agent": 7},
        {"agent": None},
        {},
    ],
    ids=["human", "Human", "Chief", "chief-space", "empty", "number", "null", "absent"],
)
def test_a_chief_cannot_close_a_human_escalation_as_anyone_else(client, project, extra):
    chief, escalation, typed = _typed_after_an_escalation(project)

    resp = _acknowledge(client, chief, escalation, cite=typed, **extra)

    assert _gated(resp)
    assert resp.get_json()["action"] == "answer"
    assert resp.get_json()["error"] == AS_CHIEF
    assert acknowledged_by(escalation) == []
    assert citations() == []

    # Nothing was spent: the same message closes it once the chief says who it is.
    again = _acknowledge(client, chief, escalation, agent="chief", cite=typed)

    assert again.status_code == 200, again.get_data(as_text=True)
    assert acknowledged_by(escalation) == ["chief"]


def test_the_answer_route_does_not_close_a_human_escalation_for_a_chief(
    client, project
):
    chief, escalation, typed = _typed_after_an_escalation(project)

    resp = client.post(
        "/comms/answer",
        json={"question_id": escalation, "cite": typed},
        headers=chief.headers,
    )

    assert _passed(resp)  # the chief gate accepted the citation; the human gate refuses
    assert resp.status_code == 403
    assert "only a human closes" in resp.get_json()["error"]
    assert answer_rows(escalation) == []
    assert acknowledged_by(escalation) == []
