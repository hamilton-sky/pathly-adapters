"""Pins for three checks of the chief gate that a changed line used to pass unnoticed.

Each test below fails when one line of the gate is changed in a scratch copy:

* ``chief_gate._cite_refusal`` applies the cite rule when ANY reading of the body is an answer
  (``any(`` made ``all(``);
* ``chief_bind._in_project`` reads an empty or missing board as the feature board, as the routes
  do (``board or "feature"`` made ``board``);
* ``chief_bind._placed_run`` looks a run up in the registry in any status (``statuses=None``
  dropped).
"""

from __future__ import annotations

import pytest
from chief_bind_support import (
    DEMO,
    _boards_are_free,
    acknowledge,
    feature_dir,
    feature_row,
    is_refused,
    run_call,
    shown,
)
from chief_cite_support import NOT_CITED, acknowledged_by, db
from chief_gate_support import (
    _chief,
    _gated,
    _passed,
    app,
    client,
    other_project,
    project,
)


def _two_readings(monkeypatch, *readings: dict) -> None:
    """Make the gate see these readings of the body. The real ``_bodies`` cannot produce two that
    differ, so this is the only way to reach the rule that decides on all of them."""
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.chief_gate._bodies", lambda: list(readings)
    )


# --- the cite rule applies when any reading is an answer ----------------------------------


def test_the_cite_rule_applies_when_only_one_reading_of_the_body_is_an_answer(
    client, project, monkeypatch
):
    """``/comms/acknowledge`` is an answer only for an escalation addressed to ``human``. With one
    reading that names such an escalation and one that names an ordinary row, the call is an
    answer: it must cite a human message, and it cites none."""
    chief = _chief("operator", project)
    feature_dir(project)
    ordinary = feature_row(DEMO, "decision")
    human_gate = feature_row(DEMO, "escalation", to_agent="human")
    ours = {"message_id": ordinary, "agent": "chief"}
    theirs = {"message_id": human_gate, "agent": "chief"}

    _two_readings(monkeypatch, ours, theirs)
    resp = client.post("/comms/acknowledge", json=ours, headers=chief.headers)

    assert _gated(resp), shown(resp)
    assert (
        resp.get_json()["error"] == NOT_CITED and resp.get_json()["action"] == "answer"
    )
    assert acknowledged_by(human_gate) == [] and acknowledged_by(ordinary) == []


def test_two_readings_that_are_not_answers_leave_the_acknowledgement_to_the_route(
    client, project, monkeypatch
):
    """The control: with no human escalation in either reading the cite rule has nothing to
    judge, and the route acknowledges the row."""
    chief = _chief("operator", project)
    feature_dir(project)
    first = feature_row(DEMO, "decision")
    second = feature_row(DEMO, "decision")
    one = {"message_id": first, "agent": "chief"}
    two = {"message_id": second, "agent": "chief"}

    _two_readings(monkeypatch, one, two)
    resp = client.post("/comms/acknowledge", json=one, headers=chief.headers)

    assert resp.status_code == 200 and _passed(resp), shown(resp)
    assert acknowledged_by(first) == ["chief"]


# --- an empty or missing board is the feature board ---------------------------------------


def _board_blank(message_id: str) -> str:
    db().execute("UPDATE comms_messages SET board = '' WHERE id = ?", (message_id,))
    db().commit()
    return message_id


def test_a_row_with_an_empty_board_is_a_feature_row_of_the_project_that_has_the_feature(
    client, project
):
    chief = _chief("operator", project)
    feature_dir(project)
    ours = _board_blank(feature_row(DEMO))

    resp = acknowledge(client, chief, ours)

    assert _passed(resp) and resp.status_code == 200, shown(resp)
    assert acknowledged_by(ours) == ["chief"]


def test_a_row_with_an_empty_board_is_refused_for_a_feature_the_project_does_not_have(
    client, project
):
    chief = _chief("operator", project)
    feature_dir(project)
    theirs = _board_blank(feature_row("elsewhere"))

    resp = acknowledge(client, chief, theirs)

    assert is_refused(resp), shown(resp)
    assert acknowledged_by(theirs) == []


@pytest.mark.parametrize("board", [None, ""])
def test_a_missing_board_is_read_as_the_feature_board(project, board):
    """A column that is NOT NULL cannot hold None, so this asks the function directly."""
    from pathly_orchestrator.http_server.chief_bind import _in_project

    feature_dir(project)

    assert _in_project(board, DEMO, str(project)) is True
    assert _in_project(board, "elsewhere", str(project)) is False
    assert _in_project(board, DEMO, None) is False


# --- a registry entry in any status places a run ------------------------------------------


@pytest.fixture()
def finished(project):
    """``finished("topic", root)`` registers a run that has ended (no history row, not active);
    taken out again after the test."""
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.state import RunnerState

    topics: list[str] = []

    def register(topic: str, root, status: str = "completed") -> str:
        state = RunnerState(
            topic=topic,
            flow="team",
            project_root=str(root),
            model="m",
            timeout=60,
            run_id="run-" + topic,
            status=status,
        )
        with registry._lock:
            registry._registry[topic] = state
        topics.append(topic)
        return state.run_id

    yield register
    with registry._lock:
        for topic in topics:
            registry._registry.pop(topic, None)


@pytest.mark.parametrize("status", ["completed", "failed", "aborted"])
def test_a_finished_run_only_the_registry_knows_is_placed_by_its_entry(
    client, project, other_project, finished, status
):
    from pathly_orchestrator.http_server.blueprints.control._helpers import (
        ACTIVE_STATUSES,
    )

    chief = _chief("operator", project)
    ours = finished("ours", project, status)
    theirs = finished("theirs", other_project, status)
    assert status not in ACTIVE_STATUSES

    allowed = run_call(client, chief, project, ours, "retry")
    refused = run_call(client, chief, project, theirs, "retry")

    assert _passed(allowed), shown(allowed)
    assert is_refused(refused), shown(refused)
