"""Tests for Phase 13 — role-based write permissions.

comms_post() must:
  - Allow any role to write to 'feature' board (always permitted).
  - Allow only _PROJECT_WRITERS to write to 'project' board (403 otherwise).
  - Allow only _GLOBAL_WRITERS to write to 'global' board (403 otherwise).
  - Return 403 JSON with 'error' and 'allowed_roles' keys.

GET /comms/permissions must:
  - Return the resolved permission table with 'feature', 'project', 'global' keys.

get_write_permissions / set_write_permissions in app_settings must:
  - Return defaults when no overrides stored.
  - Merge project-level overrides onto defaults.
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


def _post_msg(
    client,
    from_agent: str,
    board: str,
    scope: str | None = None,
    msg_type: str = "decision",
    text: str = "test message",
    project_root: str | None = None,
):
    payload: dict = {
        "feature": "demo",
        "from": from_agent,
        "type": msg_type,
        "text": text,
        "board": board,
    }
    if scope is not None:
        payload["scope"] = scope
    if project_root is not None:
        payload["project_root"] = project_root
    return client.post("/comms/post", json=payload)


# ---------------------------------------------------------------------------
# _check_write_permission unit tests
# ---------------------------------------------------------------------------


def test_comms_write_perm_check_feature_always_allowed():
    """_check_write_permission returns True for any role on 'feature' board."""
    from pathly_orchestrator.http_server.blueprints.comms import _check_write_permission

    for role in ("builder", "tester", "reviewer", "human", "director", "unknown_role"):
        assert (
            _check_write_permission(role, "feature") is True
        ), f"Role '{role}' should be allowed on feature board"


def test_comms_write_perm_check_project_writers_allowed():
    """_check_write_permission returns True for _PROJECT_WRITERS on 'project' board."""
    from pathly_orchestrator.http_server.blueprints.comms import (
        _PROJECT_WRITERS,
        _check_write_permission,
    )

    for role in _PROJECT_WRITERS:
        assert (
            _check_write_permission(role, "project") is True
        ), f"Role '{role}' should be allowed on project board"


def test_comms_write_perm_check_builder_allowed_on_project():
    """_check_write_permission returns True for 'builder' on 'project' board (d5159971)."""
    from pathly_orchestrator.http_server.blueprints.comms import _check_write_permission

    assert _check_write_permission("builder", "project") is True


def test_comms_write_perm_check_global_writers_allowed():
    """_check_write_permission returns True for _GLOBAL_WRITERS on 'global' board."""
    from pathly_orchestrator.http_server.blueprints.comms import (
        _GLOBAL_WRITERS,
        _check_write_permission,
    )

    for role in _GLOBAL_WRITERS:
        assert (
            _check_write_permission(role, "global") is True
        ), f"Role '{role}' should be allowed on global board"


def test_comms_write_perm_check_builder_blocked_on_global():
    """_check_write_permission returns False for 'builder' on 'global' board."""
    from pathly_orchestrator.http_server.blueprints.comms import _check_write_permission

    assert _check_write_permission("builder", "global") is False


def test_comms_write_perm_check_tester_blocked_on_global():
    """_check_write_permission returns False for 'tester' on 'global' board."""
    from pathly_orchestrator.http_server.blueprints.comms import _check_write_permission

    assert _check_write_permission("tester", "global") is False


# ---------------------------------------------------------------------------
# HTTP route tests — 200 cases
# ---------------------------------------------------------------------------


def test_comms_write_perm_builder_feature_allowed(client):
    """builder can post to 'feature' board — returns 200."""
    r = _post_msg(client, "builder", "feature", scope="demo")
    assert (
        r.status_code == 200
    ), f"builder→feature should be 200, got {r.status_code}: {r.data}"


def test_comms_write_perm_director_global_allowed(client):
    """director can post to 'global' board — returns 200."""
    r = _post_msg(client, "director", "global", scope="global")
    assert (
        r.status_code == 200
    ), f"director→global should be 200, got {r.status_code}: {r.data}"


def test_comms_write_perm_human_global_allowed(client):
    """human can post to 'global' board — returns 200."""
    r = _post_msg(client, "human", "global", scope="global")
    assert (
        r.status_code == 200
    ), f"human→global should be 200, got {r.status_code}: {r.data}"


def test_comms_write_perm_tester_project_allowed(client):
    """tester can post to 'project' board — returns 200."""
    r = _post_msg(client, "tester", "project", scope="myproject")
    assert (
        r.status_code == 200
    ), f"tester→project should be 200, got {r.status_code}: {r.data}"


def test_comms_write_perm_reviewer_project_allowed(client):
    """reviewer can post to 'project' board — returns 200."""
    r = _post_msg(client, "reviewer", "project", scope="myproject")
    assert (
        r.status_code == 200
    ), f"reviewer→project should be 200, got {r.status_code}: {r.data}"


# ---------------------------------------------------------------------------
# HTTP route tests — 403 cases
# ---------------------------------------------------------------------------


def test_comms_write_perm_builder_global_returns_403(client):
    """builder posting to 'global' board returns 403."""
    r = _post_msg(client, "builder", "global", scope="global")
    assert r.status_code == 403, f"builder→global should be 403, got {r.status_code}"


def test_comms_write_perm_builder_global_403_body(client):
    """403 response body contains 'error' and 'allowed_roles' keys."""
    r = _post_msg(client, "builder", "global", scope="global")
    assert r.status_code == 403
    body = json.loads(r.data)
    assert "error" in body, "403 body must have 'error' key"
    assert "allowed_roles" in body, "403 body must have 'allowed_roles' key"
    assert "builder" in body["error"]
    assert "global" in body["error"]


def test_comms_write_perm_builder_global_403_allowed_roles_are_global_writers(client):
    """For global board rejection, allowed_roles lists _GLOBAL_WRITERS sorted."""
    from pathly_orchestrator.http_server.blueprints.comms import _GLOBAL_WRITERS

    r = _post_msg(client, "builder", "global", scope="global")
    assert r.status_code == 403
    body = json.loads(r.data)
    assert set(body["allowed_roles"]) == set(_GLOBAL_WRITERS)


def test_comms_write_perm_builder_project_returns_200(client):
    """builder posting to 'project' board is allowed — returns 200 (d5159971)."""
    r = _post_msg(client, "builder", "project", scope="myproject")
    assert (
        r.status_code == 200
    ), f"builder→project should be 200, got {r.status_code}: {r.data}"


def test_comms_write_perm_project_403_allowed_roles_are_project_writers(client):
    """For project board rejection, allowed_roles lists _PROJECT_WRITERS sorted."""
    from pathly_orchestrator.http_server.blueprints.comms import _PROJECT_WRITERS

    # web-researcher is not a project writer, so it is rejected on 'project'.
    r = _post_msg(client, "web-researcher", "project", scope="myproject")
    assert r.status_code == 403
    body = json.loads(r.data)
    assert set(body["allowed_roles"]) == set(_PROJECT_WRITERS)


def test_comms_write_perm_tester_global_returns_403(client):
    """tester posting to 'global' board returns 403."""
    r = _post_msg(client, "tester", "global", scope="global")
    assert r.status_code == 403


def test_comms_write_perm_unknown_role_global_returns_403(client):
    """An unknown/custom role posting to 'global' board returns 403."""
    r = _post_msg(client, "custom_agent", "global", scope="global")
    assert r.status_code == 403


def test_comms_write_perm_unknown_role_project_returns_403(client):
    """An unknown/custom role posting to 'project' board returns 403."""
    r = _post_msg(client, "custom_agent", "project", scope="myproject")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /comms/permissions route
# ---------------------------------------------------------------------------


def test_comms_write_perm_permissions_route_returns_200(client):
    """GET /comms/permissions returns HTTP 200."""
    r = client.get("/comms/permissions")
    assert r.status_code == 200


def test_comms_write_perm_permissions_route_returns_table(client):
    """GET /comms/permissions returns a dict with feature, project, global keys."""
    r = client.get("/comms/permissions")
    assert r.status_code == 200
    body = json.loads(r.data)
    assert "feature" in body
    assert "project" in body
    assert "global" in body


def test_comms_write_perm_permissions_route_feature_unrestricted(client):
    """GET /comms/permissions shows feature board as unrestricted (['*'])."""
    r = client.get("/comms/permissions")
    body = json.loads(r.data)
    assert body["feature"] == ["*"], "feature board should be unrestricted"


def test_comms_write_perm_permissions_route_global_writers(client):
    """GET /comms/permissions global board lists only director and human."""
    from pathly_orchestrator.http_server.blueprints.comms import _GLOBAL_WRITERS

    r = client.get("/comms/permissions")
    body = json.loads(r.data)
    assert set(body["global"]) == set(_GLOBAL_WRITERS)


def test_comms_write_perm_permissions_route_with_project_root(client):
    """GET /comms/permissions?project_root=<root> returns defaults when no overrides."""
    r = client.get("/comms/permissions?project_root=C%3A%2Fproj")
    assert r.status_code == 200
    body = json.loads(r.data)
    assert "feature" in body and "project" in body and "global" in body


# ---------------------------------------------------------------------------
# app_settings: get_write_permissions / set_write_permissions
# ---------------------------------------------------------------------------


def test_comms_write_perm_get_defaults():
    """get_write_permissions returns the default table when no overrides stored."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import get_write_permissions

    conn = get_db()
    perms = get_write_permissions(conn, "C:/myproject")
    assert "feature" in perms
    assert "project" in perms
    assert "global" in perms
    assert perms["feature"] == ["*"]


def test_comms_write_perm_set_and_get_overrides():
    """set_write_permissions persists overrides; get_write_permissions returns them merged."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import (
        get_write_permissions,
        set_write_permissions,
    )

    conn = get_db()
    overrides = {"global": ["director", "human", "tester"]}
    set_write_permissions(conn, "C:/myproject", overrides)

    perms = get_write_permissions(conn, "C:/myproject")
    assert "tester" in perms["global"], "override should add tester to global"
    # Other tiers should remain at defaults
    assert perms["feature"] == ["*"]


def test_comms_write_perm_overrides_do_not_affect_other_projects():
    """Overrides stored for one project_root do not affect another."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import (
        get_write_permissions,
        set_write_permissions,
    )

    conn = get_db()
    set_write_permissions(conn, "C:/project-a", {"global": ["tester"]})

    perms_b = get_write_permissions(conn, "C:/project-b")
    assert "tester" not in perms_b.get(
        "global", []
    ), "override for project-a must not bleed into project-b"


# ---------------------------------------------------------------------------
# Module-level frozenset constants
# ---------------------------------------------------------------------------


def test_comms_write_perm_project_writers_constant():
    """_PROJECT_WRITERS frozenset contains the expected roles."""
    from pathly_orchestrator.http_server.blueprints.comms import _PROJECT_WRITERS

    expected = {
        "builder",
        "tester",
        "reviewer",
        "explorer",
        "architect",
        "planner",
        "designer",
        "research",
        "director",
        "human",
    }
    assert _PROJECT_WRITERS == frozenset(expected)


def test_comms_write_perm_global_writers_constant():
    """_GLOBAL_WRITERS frozenset contains only director and human."""
    from pathly_orchestrator.http_server.blueprints.comms import _GLOBAL_WRITERS

    assert _GLOBAL_WRITERS == frozenset({"director", "human"})


# ---------------------------------------------------------------------------
# G3: HTTP end-to-end — project-level override respected by POST /comms/post
# ---------------------------------------------------------------------------


def test_comms_write_perm_override_grants_builder_project_access(client):
    """B1 fix: a project-level override that grants 'builder' project access is
    enforced by comms_post(), not just stored in app_settings."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_write_permissions

    project_root = "C:/override-test-project"
    conn = get_db()
    # Grant builder write access to 'project' scope for this project
    set_write_permissions(
        conn,
        project_root,
        {
            "project": [
                "builder",
                "tester",
                "reviewer",
                "explorer",
                "architect",
                "planner",
                "designer",
                "director",
                "human",
            ],
        },
    )

    # builder -> project should now be 200, not 403
    resp = _post_msg(client, "builder", "project", project_root=project_root)
    assert (
        resp.status_code == 200
    ), f"Expected 200 after project override grants builder access; got {resp.status_code}: {resp.get_json()}"


def test_comms_write_perm_override_blocks_previously_allowed_role(client):
    """B1 fix: a restrictive project-level override that removes a role is also enforced."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_write_permissions

    project_root = "C:/restrictive-test-project"
    conn = get_db()
    # Restrict 'project' board to only director (removes tester who is normally allowed)
    set_write_permissions(conn, project_root, {"project": ["director", "human"]})

    resp = _post_msg(client, "tester", "project", project_root=project_root)
    assert (
        resp.status_code == 403
    ), f"Expected 403 after project override removes tester; got {resp.status_code}"
    body = resp.get_json()
    assert "director" in body.get("allowed_roles", [])
    assert "tester" not in body.get("allowed_roles", [])
