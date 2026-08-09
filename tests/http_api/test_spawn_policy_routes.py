"""spawn-policy P1 — /comms/model-policy + /comms/logging-config routes.

The one editable API surface behind the Settings UI. DB isolation is the top-level _isolate_db
autouse fixture, so each test starts from an empty config.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_model_policy_roundtrip(client):
    # Empty config → default null, no role overrides.
    assert client.get("/comms/model-policy").get_json() == {"default": None, "roles": {}}

    # Set the global default.
    r = client.post("/comms/model-policy", json={"adapter": "claude", "model": "claude-opus-4-1"})
    assert r.status_code == 200 and r.get_json()["ok"] is True

    # Set a per-role override.
    r = client.post(
        "/comms/model-policy",
        json={"role": "scout", "adapter": "claude", "model": "claude-haiku-4"},
    )
    assert r.status_code == 200

    body = client.get("/comms/model-policy").get_json()
    assert body["default"] == {"adapter": "claude", "model": "claude-opus-4-1"}
    assert body["roles"]["scout"] == {"adapter": "claude", "model": "claude-haiku-4"}

    # Clear the override → falls back to default (row removed).
    r = client.post("/comms/model-policy", json={"role": "scout", "clear": True})
    assert r.status_code == 200
    assert "scout" not in client.get("/comms/model-policy").get_json()["roles"]


def test_model_policy_rejects_blank_adapter(client):
    assert client.post("/comms/model-policy", json={"model": "gpt-5"}).status_code == 400


def test_logging_config_roundtrip_and_never_exposes_monitor(client):
    cfg = client.get("/comms/logging-config").get_json()
    assert cfg["board"] is True
    # The invariant: the always-on cost/monitor spine is never a togglable key.
    assert set(cfg.keys()) == {"board", "verbosity"}

    assert client.post("/comms/logging-config", json={"board": False}).status_code == 200
    assert client.get("/comms/logging-config").get_json()["board"] is False


def test_logging_config_rejects_non_bool(client):
    assert client.post("/comms/logging-config", json={"board": "yes"}).status_code == 400
