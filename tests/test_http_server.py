"""Integration tests for the HTTP server endpoints."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask test client with isolated tmp dirs."""
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.http_server import app, _rate_counters
    _rate_counters.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def test_health_returns_ok(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["status"] == "ok"


def test_rate_limit_blocks_after_limit(client):
    from pathly_orchestrator import http_server
    orig = http_server._RATE_LIMIT_MAX
    http_server._RATE_LIMIT_MAX = 3
    http_server._rate_counters.clear()
    try:
        for _ in range(3):
            r = client[0].get("/health")
            assert r.status_code == 200
        r = client[0].get("/health")
        assert r.status_code == 429
    finally:
        http_server._RATE_LIMIT_MAX = orig
        http_server._rate_counters.clear()


def test_next_action_missing_body(client):
    c, _ = client
    # POST with content-type application/json but no body → get_json() returns None → 400
    r = c.post(
        "/next_action",
        data=b"",
        content_type="application/json",
        headers={"Content-Length": "0"},
    )
    # The server returns 400 (Missing JSON body) or 4xx for any malformed request
    assert r.status_code in (400, 415, 500)
    data = json.loads(r.data)
    assert "error" in data


def test_next_action_missing_fields(client):
    c, _ = client
    r = c.post("/next_action", json={})
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data


def test_next_action_invalid_field_type(client):
    c, _ = client
    r = c.post("/next_action", json={"flow": 123, "topic": "t", "project_root": "/p"})
    assert r.status_code == 400


def test_complete_stage_missing_fields(client):
    c, _ = client
    r = c.post("/complete_stage", json={"flow": "team"})
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "Missing fields" in data["error"]


def test_record_activity_missing_fields(client):
    c, _ = client
    r = c.post("/record_activity", json={})
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data


def test_record_activity_invalid_token_count(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "a", "feature": "f", "summary": "s", "input_tokens": -1},
    )
    assert r.status_code == 400


def test_record_activity_negative_tokens_rejected(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "a", "feature": "f", "summary": "s", "input_tokens": -5},
    )
    assert r.status_code == 400


def test_events_stream_missing_params(client):
    c, _ = client
    r = c.get("/events/stream")
    assert r.status_code == 400


def test_events_stream_path_traversal(client):
    c, tmp = client
    # Use enough traversal segments to escape any project_root on any OS
    traversal = "../../../../../../../../../etc/passwd"
    r = c.get(f"/events/stream?topic={traversal}&project_root={tmp}")
    assert r.status_code == 400


@patch(
    "pathly_orchestrator.http_server.next_action",
    return_value={"current_state": "plan", "agent": "planner", "instructions": "..."},
)
def test_next_action_valid(_, client):
    c, tmp = client
    r = c.post(
        "/next_action",
        json={"flow": "team", "topic": "feat", "project_root": str(tmp)},
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["current_state"] == "plan"


def test_metrics_endpoint(client):
    c, _ = client
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"pathly_requests_total" in r.data
    assert b"pathly_sse_clients_active" in r.data
