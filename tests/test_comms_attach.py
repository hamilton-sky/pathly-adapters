"""Tests for POST /comms/attach — real artifact attachment onto an existing
message row, reusing the artifact_* columns (migrations.py:237-239)."""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting an embeddable message never spawns a daemon
    thread that races the per-test DB reset."""
    import pathly_orchestrator.runner.embeddings as _emb_mod
    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    """Flask test client. DB is isolated per-test by the autouse conftest fixture."""
    from pathly_orchestrator.http_server import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_artifact_holder(client) -> str:
    r = client.post("/comms/post", json={
        "feature": "demo", "from": "human", "type": "artifact",
        "text": "DESIGN.md draft", "board": "feature", "scope": "demo",
    })
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


def test_attach_path_sets_columns_and_returns_ok(client):
    mid = _post_artifact_holder(client)
    r = client.post("/comms/attach", json={
        "message_id": mid,
        "artifact_path": "pathly/plans/demo/DESIGN.md",
        "artifact_type": "md",
    })
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["ok"] is True and body["message_id"] == mid

    # GET the board back; the row must now carry artifact_path/type.
    g = client.get("/comms?feature=demo&board=feature&scope=demo")
    rows = json.loads(g.data)
    row = next(x for x in rows if x["id"] == mid)
    assert row["artifact_path"] == "pathly/plans/demo/DESIGN.md"
    assert row["artifact_type"] == "md"


def test_attach_url_only_is_allowed(client):
    mid = _post_artifact_holder(client)
    r = client.post("/comms/attach", json={
        "message_id": mid, "artifact_url": "https://example.com/spec",
    })
    assert r.status_code == 200


def test_attach_missing_message_returns_404(client):
    r = client.post("/comms/attach", json={
        "message_id": "no-such-id", "artifact_path": "x.md",
    })
    assert r.status_code == 404
    assert json.loads(r.data)["ok"] is False


def test_attach_validation(client):
    assert client.post("/comms/attach", json={}).status_code == 400
    # message_id present but no path/url:
    mid = _post_artifact_holder(client)
    assert client.post("/comms/attach", json={"message_id": mid}).status_code == 400


def test_attach_helper_directly():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message, attach_artifact_to_message
    conn = get_db()
    mid = post_message(conn, board="feature", scope="t", from_agent="human",
                       type="artifact", text="x")
    assert attach_artifact_to_message(conn, mid, artifact_path="a.md", artifact_type="md") == "ok"
    assert attach_artifact_to_message(conn, "no-such", artifact_path="a.md") == "not_found"
