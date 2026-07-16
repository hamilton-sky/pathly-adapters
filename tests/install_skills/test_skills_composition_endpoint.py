"""Tests for GET/DELETE /skills/composition — backs the Studio Skill Composition panel.

GET merges per-project DB overrides over the packaged composition.yaml (read-only, never
writes the YAML). DELETE removes a project's override for one skill, reverting it to the
packaged default. `_isolate_db` (tests/conftest.py, autouse) redirects ~/.pathly/pathly.db
to a per-test temp dir, so these tests never touch a developer's real DB.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_composition_get_returns_manifest_skills_and_fragments(client):
    r = client.get("/skills/composition")
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert "team/build" in body["skills"]
    assert body["skills"]["team/build"]["source"] == "manifest"
    assert "code-query" in body["skills"]["team/build"]["fragments"]
    assert "code-query" in body["all_fragments"]
    assert "scout-choreography" in body["all_fragments"]


def test_composition_get_reflects_db_override_source(client):
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.skill_composition import (
        set_composition_override,
    )

    set_composition_override(get_db(), None, "team/build", ["scout-choreography"])

    r = client.get("/skills/composition")
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["skills"]["team/build"]["source"] == "override"
    assert body["skills"]["team/build"]["fragments"] == ["scout-choreography"]


def test_composition_get_scopes_override_to_project_root(client):
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.skill_composition import (
        set_composition_override,
    )

    set_composition_override(get_db(), "C:/proj/a", "team/build", ["comms-post"])

    r_scoped = client.get("/skills/composition?project_root=C:/proj/a")
    assert json.loads(r_scoped.data)["skills"]["team/build"]["source"] == "override"

    r_other = client.get("/skills/composition?project_root=C:/proj/b")
    assert json.loads(r_other.data)["skills"]["team/build"]["source"] == "manifest"


def test_composition_delete_reverts_override(client):
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.skill_composition import (
        set_composition_override,
    )

    set_composition_override(get_db(), None, "team/build", ["scout-choreography"])

    r = client.delete("/skills/composition", json={"skill": "team/build"})
    assert r.status_code == 200, r.data

    r2 = client.get("/skills/composition")
    body = json.loads(r2.data)
    assert body["skills"]["team/build"]["source"] == "manifest"


def test_composition_delete_rejects_missing_skill(client):
    r = client.delete("/skills/composition", json={})
    assert r.status_code == 400


def test_composition_delete_rejects_invalid_skill_key(client):
    r = client.delete(
        "/skills/composition",
        json={"skill": "C:/Users/x/pathly/plans/foo/EDGE_CASES"},
    )
    assert r.status_code == 400
