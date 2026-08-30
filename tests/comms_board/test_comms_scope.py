"""Tests for the /comms/scope board_scope endpoints.

board_scope controls which boards (feature/project/global) an agent reads at
/next_action. The UI sets it via these routes; retrieve_board_context() reads it
back at injection time. The two must agree on the storage key, including
project_root normalization — these tests pin that contract.

The optional `role` variant keys a SECOND row (`…:<feature>:<role>`) so an architect
and a builder on one feature can be allocated different tiers. It is purely additive:
with no role row, every answer must be byte-identical to the feature-level one — the
tests below pin that, because a per-role default would silently re-cut the context of
every run already in flight.
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
    r = client.post(
        "/comms/scope",
        json={
            "feature": "demo",
            "project_root": "C:/proj",
            "scope": {"project": False},
        },
    )
    assert r.status_code == 200
    assert json.loads(r.data) == {"feature": True, "project": False, "global": True}

    r2 = client.get("/comms/scope?feature=demo&project_root=C:/proj")
    assert r2.status_code == 200
    assert json.loads(r2.data) == {"feature": True, "project": False, "global": True}


def test_scope_normalizes_backslash_root(client):
    """A scope set with a Windows backslash root reads back via the forward-slash
    form the FSM uses at injection time (key-normalization contract)."""
    set_r = client.post(
        "/comms/scope",
        json={
            "feature": "demo",
            "project_root": "C:\\Users\\Yafit\\proj",
            "scope": {"global": False},
        },
    )
    assert set_r.status_code == 200

    get_r = client.get("/comms/scope?feature=demo&project_root=C:/Users/Yafit/proj")
    assert get_r.status_code == 200
    assert json.loads(get_r.data)["global"] is False


def test_scope_is_per_feature(client):
    """Setting one feature's scope does not leak into another feature."""
    client.post(
        "/comms/scope",
        json={
            "feature": "alpha",
            "project_root": "C:/proj",
            "scope": {"feature": False},
        },
    )
    r = client.get("/comms/scope?feature=beta&project_root=C:/proj")
    assert json.loads(r.data) == {"feature": True, "project": True, "global": True}


def test_scope_set_validation(client):
    """Missing or empty required fields are rejected with 400."""
    assert (
        client.post(
            "/comms/scope",
            json={
                "feature": "demo",
                "project_root": "C:/proj",
            },
        ).status_code
        == 400
    )  # missing scope
    assert (
        client.post(
            "/comms/scope",
            json={
                "project_root": "C:/proj",
                "scope": {"feature": False},
            },
        ).status_code
        == 400
    )  # missing feature
    assert (
        client.post(
            "/comms/scope",
            json={
                "feature": "demo",
                "scope": {"feature": False},
            },
        ).status_code
        == 400
    )  # missing project_root
    assert (
        client.post(
            "/comms/scope",
            json={
                "feature": "demo",
                "project_root": "C:/proj",
                "scope": {},
            },
        ).status_code
        == 400
    )  # no recognized keys
    assert (
        client.post(
            "/comms/scope",
            json={
                "feature": "demo",
                "project_root": "C:/proj",
                "scope": {"bogus": True},
            },
        ).status_code
        == 400
    )  # only unrecognized keys


def test_scope_get_requires_params(client):
    """GET requires both feature and project_root."""
    assert client.get("/comms/scope?feature=demo").status_code == 400
    assert client.get("/comms/scope?project_root=C:/proj").status_code == 400


def test_scope_role_without_a_row_matches_the_feature_setting(client):
    """No role row → the role reads exactly what the feature-level request returns."""
    client.post(
        "/comms/scope",
        json={
            "feature": "demo",
            "project_root": "C:/proj",
            "scope": {"global": False},
        },
    )

    plain = client.get("/comms/scope?feature=demo&project_root=C:/proj")
    scoped = client.get("/comms/scope?feature=demo&project_root=C:/proj&role=architect")
    assert json.loads(scoped.data) == json.loads(plain.data)
    assert json.loads(scoped.data) == {
        "feature": True,
        "project": True,
        "global": False,
    }


def test_scope_role_row_is_additive(client):
    """Setting a role's tiers leaves the feature-level row — and other roles — untouched."""
    client.post(
        "/comms/scope",
        json={
            "feature": "demo",
            "project_root": "C:/proj",
            "scope": {"project": False, "global": False},
        },
    )
    r = client.post(
        "/comms/scope",
        json={
            "feature": "demo",
            "project_root": "C:/proj",
            "role": "architect",
            "scope": {"project": True, "global": True},
        },
    )
    assert r.status_code == 200
    assert json.loads(r.data) == {"feature": True, "project": True, "global": True}

    # The architect got its own allocation; the feature-level row and every other role
    # still answer exactly as before the role row existed.
    assert json.loads(
        client.get("/comms/scope?feature=demo&project_root=C:/proj&role=architect").data
    ) == {"feature": True, "project": True, "global": True}
    unscoped = {"feature": True, "project": False, "global": False}
    assert (
        json.loads(client.get("/comms/scope?feature=demo&project_root=C:/proj").data)
        == unscoped
    )
    assert (
        json.loads(
            client.get(
                "/comms/scope?feature=demo&project_root=C:/proj&role=builder"
            ).data
        )
        == unscoped
    )


def test_get_board_scope_role_default_is_todays_behavior():
    """The DB helper's fallback chain: role row → feature row → all-enabled default.

    Pinned directly (not through the route) because this is the guarantee that makes the
    role parameter safe to add to every call site at once.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import (
        get_board_scope,
        set_board_scope,
    )

    conn = get_db()
    all_on = {"feature": True, "project": True, "global": True}

    # Nothing stored at all.
    assert get_board_scope(conn, "C:/proj", "demo", role="builder") == all_on

    # Feature row only — the role falls through to it.
    set_board_scope(conn, "C:/proj", "demo", {**all_on, "global": False})
    assert get_board_scope(conn, "C:/proj", "demo", role="builder") == get_board_scope(
        conn, "C:/proj", "demo"
    )

    # Role row wins for that role alone.
    set_board_scope(conn, "C:/proj", "demo", {**all_on}, role="architect")
    assert get_board_scope(conn, "C:/proj", "demo", role="architect") == all_on
    assert get_board_scope(conn, "C:/proj", "demo")["global"] is False
