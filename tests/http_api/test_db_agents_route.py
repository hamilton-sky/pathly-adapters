"""GET /db/agents — registry-backed agent list for the spawn-policy Settings model-policy UI.

The Settings "Agents" group is driven by this route so a newly-created agent appears
automatically instead of being hard-coded. DB isolation is the top-level _isolate_db autouse
fixture; a fresh DB is seeded from core/agents/, so the registry is non-empty.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _seed(role, name, model, project_root=None):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.agent_defs import upsert_agent_definition

    upsert_agent_definition(get_db(), project_root, role, name, "", model, [], [])


def test_agents_returns_sorted_registry(client):
    body = client.get("/db/agents").get_json()
    agents = body["agents"]
    assert isinstance(agents, list) and agents  # fresh DB is seeded from core/agents/
    roles = [a["role"] for a in agents]
    assert "builder" in roles and "architect" in roles
    assert roles == sorted(roles)  # sorted by role
    for a in agents:
        assert set(a) >= {"role", "name", "model", "description"}


def test_agents_reflects_upsert(client):
    # INSERT OR REPLACE keys on role (global), so this replaces the seeded builder row.
    _seed("builder", "Custom Builder", "opus")
    body = client.get("/db/agents").get_json()
    builder = next(a for a in body["agents"] if a["role"] == "builder")
    assert builder["name"] == "Custom Builder" and builder["model"] == "opus"


def test_agents_project_overrides_global(client):
    _seed("builder", "Global Builder", "sonnet")  # global (project_root NULL)
    _seed("builder", "Proj Builder", "opus", project_root="/proj")

    body = client.get("/db/agents?project_root=/proj").get_json()
    builders = [a for a in body["agents"] if a["role"] == "builder"]
    assert len(builders) == 1 and builders[0]["name"] == "Proj Builder"  # project wins
