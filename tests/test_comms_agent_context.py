"""Tests for POST /comms/agent-context (BLOCK C1 — BOARD-INFO mode).

Verifies:
- Happy path: board context returned with mode=board-info, has_flow=False,
  decisions/escalations populated, board_context contains decision text.
- 400 when scope is missing.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Prevent embed_async from spawning daemon threads that race the test DB."""
    import pathly_orchestrator.runner.embeddings as _emb_mod
    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_msg(client, *, msg_type: str, text: str, board: str = "feature",
              scope: str = "f1") -> str:
    r = client.post("/comms/post", json={
        "feature": scope,
        "from": "human",
        "type": msg_type,
        "text": text,
        "board": board,
        "scope": scope,
    })
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def test_agent_context_board_info_mode(client):
    """POST /comms/agent-context returns mode=board-info and has_flow=False."""
    # Post a decision, an escalation, and a status message on (feature, f1).
    _post_msg(client, msg_type="decision", text="Use PostgreSQL not SQLite")
    _post_msg(client, msg_type="escalation", text="Need human sign-off on auth")
    _post_msg(client, msg_type="status", text="Build phase complete")

    r = client.post("/comms/agent-context", json={"board": "feature", "scope": "f1"})
    assert r.status_code == 200
    payload = json.loads(r.data)

    assert payload["mode"] == "board-info"
    assert payload["has_flow"] is False
    assert payload["board"] == "feature"
    assert payload["scope"] == "f1"

    # Decisions and escalations lists must be populated.
    assert len(payload["decisions"]) >= 1
    assert len(payload["escalations"]) >= 1

    # board_context markdown must contain the decision text.
    assert "Use PostgreSQL not SQLite" in payload["board_context"]

    # message_count reflects recent messages (at least the 3 we posted).
    assert payload["message_count"] >= 3


def test_agent_context_decisions_non_empty(client):
    """decisions list is non-empty after posting a decision."""
    _post_msg(client, msg_type="decision", text="Deploy to GKE not ECS")

    r = client.post("/comms/agent-context", json={"board": "feature", "scope": "f1"})
    assert r.status_code == 200
    payload = json.loads(r.data)
    assert any(d.get("text") == "Deploy to GKE not ECS" for d in payload["decisions"])


def test_agent_context_board_context_contains_decision(client):
    """board_context markdown contains the decision text."""
    _post_msg(client, msg_type="decision", text="Use gRPC for internal comms")

    r = client.post("/comms/agent-context", json={"board": "feature", "scope": "f1"})
    assert r.status_code == 200
    payload = json.loads(r.data)
    assert "Use gRPC for internal comms" in payload["board_context"]


def test_agent_context_missing_scope_returns_400(client):
    """POST /comms/agent-context without scope returns 400."""
    r = client.post("/comms/agent-context", json={"board": "feature"})
    assert r.status_code == 400
    payload = json.loads(r.data)
    assert "scope" in payload["error"].lower()


def test_agent_context_empty_scope_string_returns_400(client):
    """POST /comms/agent-context with empty scope string returns 400."""
    r = client.post("/comms/agent-context", json={"board": "feature", "scope": "  "})
    assert r.status_code == 400


def test_agent_context_empty_board_no_messages(client):
    """board_context is empty string and message_count is 0 when board has nothing."""
    r = client.post("/comms/agent-context", json={"board": "feature", "scope": "empty-board"})
    assert r.status_code == 200
    payload = json.loads(r.data)
    assert payload["message_count"] == 0
    assert payload["decisions"] == []
    assert payload["escalations"] == []
