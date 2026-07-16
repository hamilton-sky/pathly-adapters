"""Tests for board-context-pull Solution C — POST /comms/agent-context/preview.

Covers:
  (1) Preview returns the block + per-channel counts, and is read-only (no DB writes).
  (2) The previewed block equals what board_context_for would inject (consistency).
  (3) An attached artifact is reflected in channels.catalog.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod
    import pathly_orchestrator.runner.hydrate as _hyd_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)
    monkeypatch.setattr(_hyd_mod, "index_artifact_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _board_count(client, scope: str) -> int:
    r = client.get(f"/comms?feature={scope}&board=feature&scope={scope}&limit=200")
    assert r.status_code == 200, r.data
    return len(json.loads(r.data))


def test_preview_shape_and_readonly(client):
    scope = "prev_empty"
    before = _board_count(client, scope)

    r = client.post(
        "/comms/agent-context/preview",
        json={"board": "feature", "scope": scope, "task_description": "x"},
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert "block" in body
    assert set(body["channels"].keys()) == {
        "governance",
        "referenced",
        "semantic",
        "catalog",
    }
    # Read-only: previewing must not post anything to the board.
    assert _board_count(client, scope) == before


def test_preview_requires_scope(client):
    r = client.post("/comms/agent-context/preview", json={"board": "feature"})
    assert r.status_code == 400, r.data
    assert "scope" in json.loads(r.data)["error"]


def test_preview_block_matches_injection_path(client):
    """The previewed block is byte-identical to board_context_for's output."""
    from pathly_orchestrator.runner.comms_context import board_context_for

    scope = "prev_consistency"
    r = client.post(
        "/comms/agent-context/preview",
        json={"board": "feature", "scope": scope, "task_description": "build"},
    )
    assert r.status_code == 200, r.data
    previewed = json.loads(r.data)["block"]

    direct = board_context_for(
        board="feature",
        scope=scope,
        project_root="",
        task_description="build",
    )
    assert previewed == direct


def test_preview_reflects_catalog(client):
    scope = "prev_catalog"
    # Create one catalog artifact.
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "builder",
            "type": "artifact",
            "text": "SPEC.md produced",
            "board": "feature",
            "scope": scope,
        },
    )
    mid = json.loads(r.data)["message_id"]
    r = client.post(
        "/comms/attach",
        json={
            "message_id": mid,
            "artifact_path": f"pathly/plans/{scope}/SPEC.md",
            "artifact_type": "md",
        },
    )
    assert r.status_code == 200, r.data

    r = client.post(
        "/comms/agent-context/preview",
        json={"board": "feature", "scope": scope, "task_description": "build"},
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["channels"]["catalog"] >= 1
    assert "### Catalog" in body["block"]
