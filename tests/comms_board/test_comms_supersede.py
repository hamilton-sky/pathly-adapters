"""Tests for POST /comms/supersede and get_pending_decisions superseded_by filter.

Phase 1.4a — PR1: a superseded decision must not appear in the Governance
channel of the Communication Board (i.e. get_pending_decisions must exclude it).
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting an embeddable message never spawns a daemon
    thread. That thread calls get_db() and races the per-test DB reset (the
    module-global one-time-migration guard in db.connection), which otherwise
    causes intermittent 'no such table: comms_messages' flakes when these tests
    run alongside one another or other comms suites."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    """Flask test client. DB is isolated per-test by the autouse conftest fixture."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_decision(client, text: str = "Use SQLite") -> str:
    r = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "human",
            "type": "decision",
            "text": text,
            "board": "feature",
            "scope": "demo",
        },
    )
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


def test_comms_supersede_returns_ok(client):
    """POST /comms/supersede marks old decision as superseded and returns 200."""
    old_id = _post_decision(client, "Use PostgreSQL")
    new_id = _post_decision(client, "Use SQLite")

    r = client.post("/comms/supersede", json={"old_id": old_id, "new_id": new_id})
    assert r.status_code == 200
    assert json.loads(r.data)["ok"] is True


def test_comms_supersede_not_found(client):
    """Superseding a non-existent message returns 404."""
    new_id = _post_decision(client, "Use SQLite")
    r = client.post("/comms/supersede", json={"old_id": "no-such-id", "new_id": new_id})
    assert r.status_code == 404
    assert json.loads(r.data)["ok"] is False


def test_comms_supersede_already_superseded(client):
    """Superseding an already-superseded message returns 409."""
    old_id = _post_decision(client, "Use PostgreSQL")
    new_id = _post_decision(client, "Use SQLite")
    newer_id = _post_decision(client, "Use DuckDB")

    r1 = client.post("/comms/supersede", json={"old_id": old_id, "new_id": new_id})
    assert r1.status_code == 200

    r2 = client.post("/comms/supersede", json={"old_id": old_id, "new_id": newer_id})
    assert r2.status_code == 409
    assert json.loads(r2.data)["ok"] is False


def test_comms_supersede_validation(client):
    """Missing or blank required fields return 400."""
    assert client.post("/comms/supersede", json={}).status_code == 400
    assert client.post("/comms/supersede", json={"old_id": "x"}).status_code == 400
    assert client.post("/comms/supersede", json={"new_id": "x"}).status_code == 400
    assert (
        client.post(
            "/comms/supersede", json={"old_id": "  ", "new_id": "x"}
        ).status_code
        == 400
    )


# ---------------------------------------------------------------------------
# get_pending_decisions filter tests (via DB layer directly)
# ---------------------------------------------------------------------------


def test_comms_supersede_excluded_from_pending_decisions(client):
    """A superseded decision is excluded from get_pending_decisions()."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_pending_decisions

    old_id = _post_decision(client, "Use PostgreSQL")
    new_id = _post_decision(client, "Use SQLite")

    # Before superseding: both decisions are pending
    conn = get_db()
    before = get_pending_decisions(conn, boards=["feature"], scopes=["demo"])
    assert any(m["id"] == old_id for m in before)
    assert any(m["id"] == new_id for m in before)

    # Supersede old
    r = client.post("/comms/supersede", json={"old_id": old_id, "new_id": new_id})
    assert r.status_code == 200

    # After superseding: old decision must be absent
    conn2 = get_db()
    after = get_pending_decisions(conn2, boards=["feature"], scopes=["demo"])
    assert all(m["id"] != old_id for m in after), "superseded decision still appears"
    assert any(m["id"] == new_id for m in after), "new decision should still appear"


def test_comms_supersede_message_helper_directly():
    """supersede_message() returns correct status strings."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message, supersede_message

    conn = get_db()
    old_id = post_message(
        conn,
        board="feature",
        scope="test",
        from_agent="human",
        type="decision",
        text="old",
    )
    new_id = post_message(
        conn,
        board="feature",
        scope="test",
        from_agent="human",
        type="decision",
        text="new",
    )

    assert supersede_message(conn, old_id, new_id) == "ok"
    assert supersede_message(conn, old_id, new_id) == "already_superseded"
    assert supersede_message(conn, "no-such-id", new_id) == "not_found"
