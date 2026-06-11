"""Tests for the /comms/scope board_scope endpoints.

board_scope controls which boards (feature/project/global) an agent reads at
/next_action. The UI sets it via these routes; retrieve_board_context() reads it
back at injection time. The two must agree on the storage key, including
project_root normalization — these tests pin that contract.
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


def test_scope_get_defaults_all_enabled(client):
    """An unset feature returns all three boards enabled."""
    r = client.get("/comms/scope?feature=demo&project_root=C:/proj")
    assert r.status_code == 200
    assert json.loads(r.data) == {"feature": True, "project": True, "global": True}


def test_scope_set_partial_merges_and_persists(client):
    """A partial scope flips only the named tier and survives a round-trip."""
    r = client.post("/comms/scope", json={
        "feature": "demo",
        "project_root": "C:/proj",
        "scope": {"project": False},
    })
    assert r.status_code == 200
    assert json.loads(r.data) == {"feature": True, "project": False, "global": True}

    r2 = client.get("/comms/scope?feature=demo&project_root=C:/proj")
    assert r2.status_code == 200
    assert json.loads(r2.data) == {"feature": True, "project": False, "global": True}


def test_scope_normalizes_backslash_root(client):
    """A scope set with a Windows backslash root reads back via the forward-slash
    form the FSM uses at injection time (key-normalization contract)."""
    set_r = client.post("/comms/scope", json={
        "feature": "demo",
        "project_root": "C:\\Users\\Yafit\\proj",
        "scope": {"global": False},
    })
    assert set_r.status_code == 200

    get_r = client.get("/comms/scope?feature=demo&project_root=C:/Users/Yafit/proj")
    assert get_r.status_code == 200
    assert json.loads(get_r.data)["global"] is False


def test_scope_is_per_feature(client):
    """Setting one feature's scope does not leak into another feature."""
    client.post("/comms/scope", json={
        "feature": "alpha", "project_root": "C:/proj", "scope": {"feature": False},
    })
    r = client.get("/comms/scope?feature=beta&project_root=C:/proj")
    assert json.loads(r.data) == {"feature": True, "project": True, "global": True}


def test_scope_set_validation(client):
    """Missing or empty required fields are rejected with 400."""
    assert client.post("/comms/scope", json={
        "feature": "demo", "project_root": "C:/proj",
    }).status_code == 400  # missing scope
    assert client.post("/comms/scope", json={
        "project_root": "C:/proj", "scope": {"feature": False},
    }).status_code == 400  # missing feature
    assert client.post("/comms/scope", json={
        "feature": "demo", "scope": {"feature": False},
    }).status_code == 400  # missing project_root
    assert client.post("/comms/scope", json={
        "feature": "demo", "project_root": "C:/proj", "scope": {},
    }).status_code == 400  # no recognized keys
    assert client.post("/comms/scope", json={
        "feature": "demo", "project_root": "C:/proj", "scope": {"bogus": True},
    }).status_code == 400  # only unrecognized keys


def test_scope_get_requires_params(client):
    """GET requires both feature and project_root."""
    assert client.get("/comms/scope?feature=demo").status_code == 400
    assert client.get("/comms/scope?project_root=C:/proj").status_code == 400
