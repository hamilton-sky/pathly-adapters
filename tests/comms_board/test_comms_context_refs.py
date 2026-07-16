"""Tests for Phase 2 — context_refs on the comms write path.

Mirrors tests/test_comms_goal_executor.py's shape.

Covers:
  (1) Round-trip: a task posted WITH context_refs (non-null) → GET back → assert
      it persisted (JSON-decoded list matches).
  (2) Malformed context_refs → 400: missing artifact key, wrong types, not a list.
  (3) A task with NO context_refs → 200 + NULL column (back-compat).
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting never spawns background threads during tests."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _get_message(client, feature: str, scope: str, message_id: str) -> dict:
    """Fetch the board for scope and return the row with the given id."""
    r = client.get(f"/comms?feature={feature}&scope={scope}&limit=100")
    assert r.status_code == 200, r.data
    rows = json.loads(r.data)
    match = [m for m in rows if m["id"] == message_id]
    assert match, f"message {message_id} not found in board {scope}"
    return match[0]


# ---------------------------------------------------------------------------
# (1) Round-trip — context_refs persists non-null
# ---------------------------------------------------------------------------


def test_context_refs_roundtrip_non_null(client):
    """A task posted with context_refs comes back with the list intact."""
    feature = scope = "cr_roundtrip"
    refs = [
        {"artifact": "EDGE_CASES.md", "anchor": "phase-1"},
        {"artifact": "HAPPY_FLOW.md", "anchor": "phase-1"},
        {"artifact": "ARCHITECTURE_PROPOSAL.md", "anchor": None},
    ]

    r = client.post(
        "/comms/post",
        json={
            "feature": feature,
            "from": "planner",
            "type": "task",
            "text": "Phase 1: do the thing",
            "board": "feature",
            "scope": scope,
            "stage": "BUILDING",
            "conv": 1,
            "context_refs": refs,
        },
    )
    assert r.status_code == 200, r.data
    task_id = json.loads(r.data)["message_id"]

    row = _get_message(client, feature, scope, task_id)
    assert row["type"] == "task"
    # context_refs must come back as a JSON-decoded list matching what we sent
    stored = row.get("context_refs")
    assert stored is not None, "context_refs must not be NULL after round-trip"
    # GET returns JSON — may be a pre-decoded list or a JSON string depending on
    # whether the serializer decodes it; handle both.
    if isinstance(stored, str):
        stored = json.loads(stored)
    assert stored == refs


# ---------------------------------------------------------------------------
# (2) Malformed context_refs → 400
# ---------------------------------------------------------------------------


def test_context_refs_not_a_list_rejected(client):
    """A string context_refs is rejected with 400."""
    r = client.post(
        "/comms/post",
        json={
            "feature": "cr_bad",
            "from": "planner",
            "type": "task",
            "text": "bad context_refs",
            "board": "feature",
            "scope": "cr_bad",
            "context_refs": "notalist",
        },
    )
    assert r.status_code == 400, r.data
    assert "context_refs" in json.loads(r.data)["error"]


def test_context_refs_entry_missing_artifact_rejected(client):
    """An entry without an 'artifact' string key is rejected with 400."""
    r = client.post(
        "/comms/post",
        json={
            "feature": "cr_bad2",
            "from": "planner",
            "type": "task",
            "text": "bad context_refs entry",
            "board": "feature",
            "scope": "cr_bad2",
            "context_refs": [{"anchor": 1}],
        },
    )
    assert r.status_code == 400, r.data
    assert "context_refs" in json.loads(r.data)["error"]


def test_context_refs_anchor_non_string_rejected(client):
    """An entry with a non-string, non-null anchor is rejected with 400."""
    r = client.post(
        "/comms/post",
        json={
            "feature": "cr_bad3",
            "from": "planner",
            "type": "task",
            "text": "bad anchor type",
            "board": "feature",
            "scope": "cr_bad3",
            "context_refs": [{"artifact": "EDGE_CASES.md", "anchor": 42}],
        },
    )
    assert r.status_code == 400, r.data
    assert "context_refs" in json.loads(r.data)["error"]


# ---------------------------------------------------------------------------
# (3) Back-compat — a task without context_refs posts fine with NULL column
# ---------------------------------------------------------------------------


def test_task_without_context_refs_is_back_compat(client):
    """A task with no context_refs posts 200 and leaves the column NULL."""
    feature = scope = "cr_backcompat"
    r = client.post(
        "/comms/post",
        json={
            "feature": feature,
            "from": "builder",
            "type": "task",
            "text": "legacy task",
            "board": "feature",
            "scope": scope,
        },
    )
    assert r.status_code == 200, r.data
    task_id = json.loads(r.data)["message_id"]

    row = _get_message(client, feature, scope, task_id)
    assert row.get("context_refs") is None
    # Back-compat: DAG frontier behavior unchanged
    assert row["task_status"] == "pending"
