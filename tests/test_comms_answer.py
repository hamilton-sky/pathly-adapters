"""Tests for POST /comms/answer — the chosen option + answered status must persist.

Regression: the board's 5s fallback poll re-fetches the board via GET /comms and
replaces the local copy. The chosen option id never round-tripped (answer_question
accepted option_id but dropped it, and set status='resolved' which the question card
doesn't treat as answered), so the poll reverted the selection ~5s after a click.
The fix persists answer_option and marks the question 'answered'.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting a message never spawns a daemon thread that
    races the per-test DB reset (mirrors test_comms_supersede)."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    """Flask test client. DB is isolated per-test by the autouse conftest fixture."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def spy(monkeypatch):
    """Spy on the comms SSE broadcast as imported into messages_crud — the answer
    route calls _broadcast_comms(scope, payload) through that module-bound name."""
    import pathly_orchestrator.http_server.blueprints.comms.messages_crud as mc

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(mc, "_broadcast_comms", lambda scope, payload: events.append((scope, payload)))
    return events


def _post_question(client, text: str = "Which storage engine?") -> str:
    r = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "human",
            "type": "question",
            "text": text,
            "board": "feature",
            "scope": "demo",
        },
    )
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


def _get_board(client) -> list[dict]:
    r = client.get("/comms?feature=demo&board=feature&scope=demo")
    assert r.status_code == 200
    return json.loads(r.data)


def test_answer_persists_option_and_status(client):
    """After answering, GET /comms returns the question with the chosen option id
    and status='answered' — so a board reload restores the selection."""
    qid = _post_question(client)

    # Before answering: pending, no chosen option.
    before = next(m for m in _get_board(client) if m["id"] == qid)
    assert before["status"] == "pending"
    assert before.get("answer_option") is None

    r = client.post(
        "/comms/answer",
        json={
            "question_id": qid,
            "answer": "Use `Reserve metadata`. Keep it simple.",
            "option_id": "b",
        },
    )
    assert r.status_code == 200
    assert json.loads(r.data)["ok"] is True

    # After answering: the chosen option id + answered status round-trip through GET.
    after = next(m for m in _get_board(client) if m["id"] == qid)
    assert after["status"] == "answered"
    assert after["answer_option"] == "b"


def test_answer_broadcasts_comms_update_on_the_question_scope(client, spy):
    """Answering emits a COMMS_UPDATE to the question's scope so every open board
    reloads at once (instant cross-client sync), not only after the 5s poll."""
    qid = _post_question(client)
    # The post route broadcasts through messages_write's own binding (not spied), so
    # `spy` holds only what the answer route emits.
    r = client.post(
        "/comms/answer",
        json={"question_id": qid, "answer": "Use `Minimal schema`.", "option_id": "a"},
    )
    assert r.status_code == 200

    updates = [(sc, p) for (sc, p) in spy if p.get("type") == "COMMS_UPDATE"]
    assert len(updates) == 1, f"expected one COMMS_UPDATE from the answer, got {spy}"
    scope, payload = updates[0]
    assert scope == "demo"
    assert payload["scope"] == "demo"
    assert payload["message_id"] == qid


def test_answer_without_option_id_still_marks_answered(client):
    """A free-form answer (no option_id) still flips the question to 'answered'
    and leaves answer_option NULL — the status alone drives the footer state."""
    qid = _post_question(client)

    r = client.post(
        "/comms/answer",
        json={"question_id": qid, "answer": "Do the simplest thing."},
    )
    assert r.status_code == 200

    after = next(m for m in _get_board(client) if m["id"] == qid)
    assert after["status"] == "answered"
    assert after.get("answer_option") is None
