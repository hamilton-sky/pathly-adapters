"""Tests for Phase 1.4b — write-time embedding curation.

Only message types in _EMBED_TYPES should produce a row in comms_embeddings.
Transient types (status, nudge, question, answer, task) must NOT be embedded.
"""
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


def _post_msg(client, msg_type: str, text: str = "test message") -> str:
    r = client.post("/comms/post", json={
        "feature": "demo",
        "from": "builder",
        "type": msg_type,
        "text": text,
    })
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


def _embedding_exists(message_id: str) -> bool:
    """Check whether a comms_embeddings row exists for message_id."""
    from pathly_orchestrator.db.connection import _VEC_AVAILABLE, get_db
    if not _VEC_AVAILABLE:
        # Vec table doesn't exist — test is trivially satisfied (nothing embedded)
        return False
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM comms_embeddings WHERE message_id=?", (message_id,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# _EMBED_TYPES constant test
# ---------------------------------------------------------------------------

def test_embed_types_constant_contains_expected_types():
    """_EMBED_TYPES frozenset contains the six high-value message types."""
    from pathly_orchestrator.http_server.blueprints.comms import _EMBED_TYPES
    assert "decision" in _EMBED_TYPES
    assert "discovery" in _EMBED_TYPES
    assert "constraint" in _EMBED_TYPES
    assert "warning" in _EMBED_TYPES
    assert "escalation" in _EMBED_TYPES
    assert "artifact" in _EMBED_TYPES


def test_embed_types_excludes_transient_types():
    """_EMBED_TYPES does NOT include transient message types."""
    from pathly_orchestrator.http_server.blueprints.comms import _EMBED_TYPES
    for transient in ("status", "nudge", "question", "answer", "task"):
        assert transient not in _EMBED_TYPES, f"transient type '{transient}' should not be in _EMBED_TYPES"


# ---------------------------------------------------------------------------
# Conditional embed call tests (via mocking embed_async)
# ---------------------------------------------------------------------------

def test_comms_embed_curation_status_not_embedded(client, monkeypatch):
    """Posting a 'status' message does NOT call _embed_async."""
    calls: list[str] = []

    import pathly_orchestrator.http_server.blueprints.comms as _comms_mod

    def _fake_embed_async(message_id: str, text: str) -> None:
        calls.append(message_id)

    # The blueprint imports embed_async inside the route via lazy import —
    # patch at the runner.embeddings module level so the import resolves to our fake.
    import pathly_orchestrator.runner.embeddings as _emb_mod
    monkeypatch.setattr(_emb_mod, "embed_async", _fake_embed_async)

    _post_msg(client, "status", "Build stage started")
    assert calls == [], f"embed_async should NOT be called for 'status', got: {calls}"


def test_comms_embed_curation_decision_is_embedded(client, monkeypatch):
    """Posting a 'decision' message DOES call _embed_async."""
    calls: list[str] = []

    import pathly_orchestrator.runner.embeddings as _emb_mod

    def _fake_embed_async(message_id: str, text: str) -> None:
        calls.append(message_id)

    monkeypatch.setattr(_emb_mod, "embed_async", _fake_embed_async)

    mid = _post_msg(client, "decision", "Use SQLite for all persistence")
    assert mid in calls, f"embed_async should be called for 'decision', calls={calls}"


def test_comms_embed_curation_nudge_not_embedded(client, monkeypatch):
    """Posting a 'nudge' message does NOT call _embed_async."""
    calls: list[str] = []

    import pathly_orchestrator.runner.embeddings as _emb_mod

    def _fake_embed_async(message_id: str, text: str) -> None:
        calls.append(message_id)

    monkeypatch.setattr(_emb_mod, "embed_async", _fake_embed_async)

    _post_msg(client, "nudge", "Remember to check the logs")
    assert calls == [], f"embed_async should NOT be called for 'nudge', got: {calls}"


def test_comms_embed_curation_discovery_is_embedded(client, monkeypatch):
    """Posting a 'discovery' message DOES call _embed_async."""
    calls: list[str] = []

    import pathly_orchestrator.runner.embeddings as _emb_mod

    def _fake_embed_async(message_id: str, text: str) -> None:
        calls.append(message_id)

    monkeypatch.setattr(_emb_mod, "embed_async", _fake_embed_async)

    mid = _post_msg(client, "discovery", "Auth bug: session tokens expire too fast")
    assert mid in calls, f"embed_async should be called for 'discovery', calls={calls}"


def test_comms_embed_curation_all_transient_types_skipped(client, monkeypatch):
    """All transient types (status, nudge, question, answer, task) skip embedding."""
    calls: list[str] = []

    import pathly_orchestrator.runner.embeddings as _emb_mod

    def _fake_embed_async(message_id: str, text: str) -> None:
        calls.append(message_id)

    monkeypatch.setattr(_emb_mod, "embed_async", _fake_embed_async)

    for t in ("status", "nudge", "question", "answer", "task"):
        _post_msg(client, t, f"A {t} message")

    assert calls == [], f"embed_async should NOT be called for transient types, got: {calls}"
