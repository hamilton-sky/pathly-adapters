"""Goals read-model (GET /comms/goals): goals enriched with a task-DAG rollup.

Locks the contract of get_goals_with_rollup + the route — the symmetric READ
partner to /comms/goals/{run,stop,decompose}. `ready` is the buildable frontier
(pending with all deps done), distinct from the `blocked` task_status.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_goal(scope: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        get_db(), board="feature", scope=scope, from_agent="planner", type="goal",
        text="Goal", executor="loop",
    )


def _post_task(scope: str, goal_id: str, status: str = "pending", deps=None) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    tid = post_message(
        conn, board="feature", scope=scope, from_agent="planner", type="task",
        text="T", goal_id=goal_id, depends_on=deps or [],
    )
    if status != "pending":
        conn.execute("UPDATE comms_messages SET task_status=? WHERE id=?", (status, tid))
        conn.commit()
    return tid


def test_goals_rollup_counts_by_status(client):
    scope = "grm-rollup"
    g = _post_goal(scope)
    _post_task(scope, g, "done")
    _post_task(scope, g, "done")
    ip = _post_task(scope, g, "in_progress")
    _post_task(scope, g, "pending")                 # no deps → ready
    _post_task(scope, g, "pending", deps=[ip])      # dep in_progress → NOT ready
    _post_task(scope, g, "failed")

    r = client.get(f"/comms/goals?feature={scope}")
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) == 1
    row = data[0]
    assert row["id"] == g
    assert row["executor"] == "loop"
    assert row["tasks"] == {
        "total": 6, "done": 2, "in_progress": 1, "pending": 2,
        "blocked": 0, "failed": 1, "ready": 1,
    }


def test_ready_updates_as_deps_complete(client):
    """A task blocked behind a dep becomes ready once the dep is done."""
    from pathly_orchestrator.db.connection import get_db

    scope = "grm-ready"
    g = _post_goal(scope)
    up = _post_task(scope, g, "pending")            # ready now
    _post_task(scope, g, "pending", deps=[up])      # blocked behind `up`
    assert client.get(f"/comms/goals?feature={scope}").get_json()[0]["tasks"]["ready"] == 1

    get_db().execute("UPDATE comms_messages SET task_status='done' WHERE id=?", (up,))
    get_db().commit()
    # `up` done → the downstream task's dep is satisfied → both ready count flips to 1
    t = client.get(f"/comms/goals?feature={scope}").get_json()[0]["tasks"]
    assert t == {"total": 2, "done": 1, "in_progress": 0, "pending": 1,
                 "blocked": 0, "failed": 0, "ready": 1}


def test_multiple_goals_isolated(client):
    scope = "grm-multi"
    g1 = _post_goal(scope)
    g2 = _post_goal(scope)
    _post_task(scope, g1, "done")
    _post_task(scope, g2, "pending")
    data = {row["id"]: row["tasks"] for row in client.get(f"/comms/goals?feature={scope}").get_json()}
    assert data[g1]["done"] == 1 and data[g1]["total"] == 1
    assert data[g2]["ready"] == 1 and data[g2]["total"] == 1


def test_no_goals_returns_empty(client):
    r = client.get("/comms/goals?feature=grm-none-xyz")
    assert r.status_code == 200 and r.get_json() == []


def test_missing_feature_is_400(client):
    assert client.get("/comms/goals").status_code == 400
