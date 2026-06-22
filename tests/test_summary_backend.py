"""Summarizer backend controls — global default route + per-upload /comms/post field."""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_get_summary_backend_default(client):
    r = client.get("/comms/summary-backend")
    assert r.status_code == 200, r.data
    assert json.loads(r.data)["backend"] in ("minilm", "ollama", "haiku")


def test_set_and_get_roundtrip(client):
    try:
        r = client.post("/comms/summary-backend", json={"backend": "haiku"})
        assert r.status_code == 200, r.data
        assert json.loads(r.data)["backend"] == "haiku"
        g = client.get("/comms/summary-backend")
        assert json.loads(g.data)["backend"] == "haiku"
    finally:
        # Restore the global default so this test never leaks state into others.
        client.post("/comms/summary-backend", json={"backend": "minilm"})


def test_set_invalid_backend_400(client):
    r = client.post("/comms/summary-backend", json={"backend": "bogus"})
    assert r.status_code == 400


def test_set_missing_backend_400(client):
    r = client.post("/comms/summary-backend", json={})
    assert r.status_code == 400


def _post(client, **extra):
    body = {
        "feature": "sb-test",
        "from": "planner",
        "type": "nudge",
        "text": "hi",
        "board": "feature",
        "scope": "sb-test",
        **extra,
    }
    return client.post("/comms/post", json=body)


def test_post_invalid_summary_backend_400(client):
    r = _post(client, summary_backend="bogus")
    assert r.status_code == 400


def test_post_valid_summary_backend_200(client):
    r = _post(client, summary_backend="haiku")
    assert r.status_code == 200, r.data


def test_post_without_summary_backend_still_ok(client):
    r = _post(client)
    assert r.status_code == 200, r.data
