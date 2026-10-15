"""build-proof 03: POST /comms/tasks/floor-allow sets a task's floor allow list, humans only.

Task text on the board is written by agents, so an allow list there would let the planner
grant the builder an excuse. The route refuses any caller with a live run token (403), the
same rule ``/complete_stage`` applies to ``force_past_gate``.
"""

from __future__ import annotations

import json

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import (
    post_message,
    update_message_text,
)
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, revoke_run_tokens

# Isolation is handled by the _isolate_db autouse fixture in conftest.py.
ROUTE = "/comms/tasks/floor-allow"
FIRST = "Add the widget.\n\n```check\n$ python -m pytest tests/test_widget.py -q\n```\n"
SECOND = 'Add the widget.\n\n```check\n$ python -c "print(1)"\n```\n'


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _task(text: str = FIRST) -> str:
    return post_message(
        get_db(),
        board="feature",
        scope="feat",
        from_agent="planner",
        type="task",
        text=text,
    )


def _row(message_id: str) -> dict:
    row = (
        get_db()
        .execute(
            "SELECT text, claimed_text, floor_allow FROM comms_messages WHERE id=?",
            (message_id,),
        )
        .fetchone()
    )
    return dict(row)


def _token(run_id: str = "run-builder") -> str:
    return mint_run_token(
        get_db(), run_id, "builder", "feat", "/tmp/p", "feature", "feat"
    )


def test_a_caller_with_no_token_sets_the_allow_list(client) -> None:
    tid = _task()
    r = client.post(ROUTE, json={"message_id": tid, "allow": ["skip"]})
    assert r.status_code == 200, r.get_json()
    assert r.get_json() == {"ok": True, "allow": ["skip"]}
    assert json.loads(_row(tid)["floor_allow"]) == ["skip"]


def test_a_live_run_token_is_refused_and_nothing_is_stored(client) -> None:
    tid = _task()
    r = client.post(
        ROUTE,
        headers={"X-Pathly-Run-Token": _token()},
        json={"message_id": tid, "allow": ["skip"]},
    )
    assert r.status_code == 403
    assert "run" in r.get_json()["error"]
    assert _row(tid)["floor_allow"] is None


def test_a_revoked_token_is_treated_like_no_token(client) -> None:
    """The documented limit: the server cannot tell a human from a caller with no live token."""
    tid = _task()
    token = _token("run-gone")
    revoke_run_tokens(get_db(), "run-gone")
    r = client.post(
        ROUTE,
        headers={"X-Pathly-Run-Token": token},
        json={"message_id": tid, "allow": ["config"]},
    )
    assert r.status_code == 200
    assert json.loads(_row(tid)["floor_allow"]) == ["config"]


def test_an_unknown_category_is_a_400_naming_the_valid_ones(client) -> None:
    tid = _task()
    r = client.post(ROUTE, json={"message_id": tid, "allow": ["nope"]})
    assert r.status_code == 400
    error = r.get_json()["error"]
    assert "nope" in error
    for name in ("skip", "suppress", "plan-edit", "task-edit"):
        assert name in error
    assert _row(tid)["floor_allow"] is None


def test_a_missing_task_is_a_404(client) -> None:
    r = client.post(ROUTE, json={"message_id": "no-such-id", "allow": ["skip"]})
    assert r.status_code == 404


def test_a_message_that_is_not_a_task_is_a_400(client) -> None:
    note = post_message(
        get_db(), board="feature", scope="feat", from_agent="human", type="decision"
    )
    r = client.post(ROUTE, json={"message_id": note, "allow": ["skip"]})
    assert r.status_code == 400
    assert "task" in r.get_json()["error"]
    assert _row(note)["floor_allow"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"allow": ["skip"]},
        {"message_id": "", "allow": ["skip"]},
        {"message_id": "x"},
        {"message_id": "x", "allow": "skip"},
        {"message_id": "x", "allow": ["skip"], "refreeze": "false"},
    ],
)
def test_a_malformed_body_is_a_400(client, body) -> None:
    tid = _task()
    if body.get("message_id") == "x":
        body = {**body, "message_id": tid}
    r = client.post(ROUTE, json=body)
    assert r.status_code == 400
    assert _row(tid)["floor_allow"] is None


def test_refreeze_copies_the_live_text_into_the_frozen_copy(client) -> None:
    tid = _task()
    assert claim_task(get_db(), tid, run_id="sched-x#1")
    update_message_text(get_db(), tid, SECOND)  # a human corrects a broken check
    assert _row(tid)["claimed_text"] == FIRST

    r = client.post(
        ROUTE, json={"message_id": tid, "allow": ["skip"], "refreeze": True}
    )
    assert r.status_code == 200
    assert _row(tid)["claimed_text"] == SECOND


def test_without_refreeze_the_frozen_text_stays(client) -> None:
    tid = _task()
    assert claim_task(get_db(), tid, run_id="sched-x#1")
    update_message_text(get_db(), tid, SECOND)

    r = client.post(
        ROUTE, json={"message_id": tid, "allow": ["skip"], "refreeze": False}
    )
    assert r.status_code == 200
    assert _row(tid)["claimed_text"] == FIRST
