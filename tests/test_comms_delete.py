"""Tests for POST /comms/delete — retract a message only while unread by an agent."""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    """Flask test client. DB is isolated per-test by the autouse conftest fixture."""
    from pathly_orchestrator.http_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(client, text: str = "hello") -> str:
    r = client.post("/comms/post", json={
        "feature": "demo", "from": "human", "type": "nudge", "text": text,
    })
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


def _set_read_by(message_id: str, readers: list[str]) -> None:
    from pathly_orchestrator.db.connection import get_db
    conn = get_db()
    conn.execute(
        "UPDATE comms_messages SET read_by=? WHERE id=?",
        (json.dumps(readers), message_id),
    )
    conn.commit()


def test_delete_unread_message(client):
    """An unread message can be retracted and disappears from the board."""
    mid = _post(client)
    r = client.post("/comms/delete", json={"message_id": mid})
    assert r.status_code == 200
    assert json.loads(r.data)["ok"] is True

    g = client.get("/comms?feature=demo&board=feature&scope=demo")
    assert g.status_code == 200
    assert all(m["id"] != mid for m in json.loads(g.data))


def test_delete_refused_after_agent_read(client):
    """Once an agent appears in read_by, the message is locked (409)."""
    mid = _post(client)
    _set_read_by(mid, ["builder"])
    r = client.post("/comms/delete", json={"message_id": mid})
    assert r.status_code == 409
    assert json.loads(r.data)["ok"] is False


def test_delete_human_read_does_not_lock(client):
    """A human reading their own message does not lock it."""
    mid = _post(client)
    _set_read_by(mid, ["human", "you"])
    r = client.post("/comms/delete", json={"message_id": mid})
    assert r.status_code == 200


def test_delete_not_found(client):
    r = client.post("/comms/delete", json={"message_id": "does-not-exist"})
    assert r.status_code == 404


def test_delete_requires_message_id(client):
    assert client.post("/comms/delete", json={}).status_code == 400
    assert client.post("/comms/delete", json={"message_id": "  "}).status_code == 400
