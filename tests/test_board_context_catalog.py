"""Tests for board-context-pull Solution A — the 📚 Catalog channel.

Covers:
  (1) Empty board → byte-identical to before: board_context_for returns '' and the
      counts dict is all-zero (no catalog channel emitted).
  (2) A board WITH an artifact → the catalog channel is emitted, lists the artifact
      path, and counts['catalog'] reflects it.
  (3) Permission boundary → an artifact on scope A is not enumerated for scope B.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async(monkeypatch):
    """Stub the async embed + artifact-index daemons so posting/attaching never
    spawns a background thread that races the per-test DB reset."""
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


def _attach_artifact(client, scope: str, path: str) -> None:
    """Post an artifact-holder message on the feature board and attach a path,
    creating a comms_artifacts catalog row."""
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "builder",
            "type": "artifact",
            "text": f"{path} produced",
            "board": "feature",
            "scope": scope,
        },
    )
    assert r.status_code == 200, r.data
    mid = json.loads(r.data)["message_id"]
    r = client.post(
        "/comms/attach",
        json={"message_id": mid, "artifact_path": path, "artifact_type": "md"},
    )
    assert r.status_code == 200, r.data


def test_empty_board_is_byte_identical(client):
    """No messages, no artifacts → empty block and all-zero counts (channel omitted)."""
    from pathly_orchestrator.runner.comms_context import board_context_for

    counts: dict = {}
    block = board_context_for(
        board="feature",
        scope="cat_empty_unique",
        project_root="/tmp/proj",
        task_description="anything",
        counts=counts,
    )
    assert block == ""
    assert counts == {
        "governance": 0,
        "referenced": 0,
        "semantic": 0,
        "catalog": 0,
    }


def test_catalog_channel_emitted_with_artifact(client):
    """An attached artifact surfaces in the 📚 Catalog channel + counts."""
    from pathly_orchestrator.runner.comms_context import board_context_for

    scope = "cat_present"
    _attach_artifact(client, scope, "pathly/plans/cat_present/DESIGN.md")

    counts: dict = {}
    block = board_context_for(
        board="feature",
        scope=scope,
        project_root="/tmp/proj",
        task_description="build the thing",
        counts=counts,
    )
    assert "📚 Catalog" in block
    assert "pathly/plans/cat_present/DESIGN.md" in block
    # The scoped pull URL is handed to the agent already bounded to its board.
    assert "board=feature&scope=cat_present" in block
    assert counts["catalog"] >= 1


def test_catalog_scope_isolation(client):
    """An artifact on scope A is not enumerated in scope B's catalog."""
    from pathly_orchestrator.runner.comms_context import board_context_for

    _attach_artifact(client, "cat_scope_a", "pathly/plans/cat_scope_a/SECRET.md")

    counts: dict = {}
    block = board_context_for(
        board="feature",
        scope="cat_scope_b",
        project_root="/tmp/proj",
        task_description="unrelated",
        counts=counts,
    )
    assert "SECRET.md" not in block
    assert counts["catalog"] == 0
