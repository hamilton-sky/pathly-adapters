"""Tests for Phase 14 — DAG task decomposition.

Covers:
  - get_ready_tasks() — tasks with null/empty deps are immediately ready
  - Tasks whose deps are pending are blocked
  - A task becomes ready after its dep is completed
  - complete_task() is idempotent
  - GET /comms/tasks?ready=true returns correct subset
  - POST /comms/tasks/complete returns 200 and newly-unblocked IDs
  - Circular deps (A depends on B, B depends on A) — neither is ready (no crash)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_task(
    client,
    text: str,
    depends_on: list[str] | None = None,
    feature: str = "myfeature",
    scope: str = "myfeature",
) -> str:
    """Post a task message via the HTTP API and return its message_id."""
    payload: dict = {
        "feature": feature,
        "from": "builder",
        "type": "task",
        "text": text,
        "board": "feature",
        "scope": scope,
    }
    if depends_on is not None:
        payload["depends_on"] = depends_on
    r = client.post("/comms/post", json=payload)
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _set_task_deps_direct(conn, message_id: str, depends_on: list[str]) -> None:
    """Directly set depends_on on a message (bypasses HTTP for setup convenience)."""
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?",
        (json.dumps(depends_on), message_id),
    )
    conn.commit()


def test_comms_tasks_list_reports_true_task_status(client):
    """GET /comms/tasks (non-ready) lists the goal's tasks with their real DAG
    task_status — a completed task stays in the list (the Goals view needs it for
    duration) but reads 'done', not 'pending'.

    Regression: the list previously filtered the generic message `status` column,
    which never changes for a task, so completion was invisible at this layer."""
    a = _post_task(client, "task A", feature="dagf", scope="dagf")
    b = _post_task(client, "task B", depends_on=[a], feature="dagf", scope="dagf")

    rc = client.post("/comms/tasks/complete", json={"message_id": a, "feature": "dagf"})
    assert rc.status_code == 200

    rows = {
        t["id"]: t for t in json.loads(client.get("/comms/tasks?feature=dagf").data)
    }
    assert set(rows) == {a, b}, "both tasks should still be listed"
    assert rows[a]["task_status"] == "done", rows[a]
    assert rows[b]["task_status"] == "pending", rows[b]


def test_comms_tasks_list_scoped_to_goal(client):
    """GET /comms/tasks?goal_id=… returns only that goal's tasks (the list used to
    ignore goal_id and return every task in the scope)."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    g1 = _post_task(client, "g1 task", feature="gscope", scope="gscope")
    g2 = _post_task(client, "g2 task", feature="gscope", scope="gscope")
    conn.execute("UPDATE comms_messages SET goal_id='G1' WHERE id=?", (g1,))
    conn.execute("UPDATE comms_messages SET goal_id='G2' WHERE id=?", (g2,))
    conn.commit()

    rows = json.loads(client.get("/comms/tasks?feature=gscope&goal_id=G1").data)
    ids = {t["id"] for t in rows}
    assert ids == {g1}, ids


# ---------------------------------------------------------------------------
# DB-layer tests
# ---------------------------------------------------------------------------


def test_comms_dag_ready_task_no_deps():
    """A task with depends_on=NULL is immediately ready."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_ready_tasks, post_message

    conn = get_db()
    mid = post_message(
        conn,
        board="feature",
        scope="f1",
        from_agent="builder",
        type="task",
        text="standalone task",
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()

    ready = get_ready_tasks(conn, boards=["feature"], scopes=["f1"])
    assert any(r["id"] == mid for r in ready), "task with no deps should be ready"


def test_comms_dag_task_with_empty_deps_is_ready():
    """A task with depends_on='[]' is immediately ready."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_ready_tasks, post_message

    conn = get_db()
    mid = post_message(
        conn,
        board="feature",
        scope="f2",
        from_agent="builder",
        type="task",
        text="task with empty deps",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on='[]' WHERE id=?",
        (mid,),
    )
    conn.commit()

    ready = get_ready_tasks(conn, boards=["feature"], scopes=["f2"])
    assert any(r["id"] == mid for r in ready)


def test_comms_dag_task_with_unmet_dep_not_ready():
    """A task whose dep is still pending does not appear in the ready list."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_ready_tasks, post_message

    conn = get_db()
    dep_id = post_message(
        conn,
        board="feature",
        scope="f3",
        from_agent="builder",
        type="task",
        text="dep task",
    )
    child_id = post_message(
        conn,
        board="feature",
        scope="f3",
        from_agent="builder",
        type="task",
        text="child task",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id IN (?, ?)",
        (dep_id, child_id),
    )
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?",
        (json.dumps([dep_id]), child_id),
    )
    conn.commit()

    ready = get_ready_tasks(conn, boards=["feature"], scopes=["f3"])
    ready_ids = {r["id"] for r in ready}
    assert dep_id in ready_ids, "dep task (no deps) should be ready"
    assert child_id not in ready_ids, "child task with unmet dep should not be ready"


def test_comms_dag_task_becomes_ready_after_dep_completes():
    """complete_task() on the dep causes the downstream task to appear in ready list."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import (
        complete_task,
        get_ready_tasks,
        post_message,
    )

    conn = get_db()
    dep_id = post_message(
        conn,
        board="feature",
        scope="f4",
        from_agent="builder",
        type="task",
        text="dep task",
    )
    child_id = post_message(
        conn,
        board="feature",
        scope="f4",
        from_agent="builder",
        type="task",
        text="child task",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id IN (?, ?)",
        (dep_id, child_id),
    )
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?",
        (json.dumps([dep_id]), child_id),
    )
    conn.commit()

    before = get_ready_tasks(conn, boards=["feature"], scopes=["f4"])
    assert child_id not in {r["id"] for r in before}

    newly_ready = complete_task(conn, dep_id)
    assert child_id in newly_ready

    after = get_ready_tasks(conn, boards=["feature"], scopes=["f4"])
    assert any(r["id"] == child_id for r in after), "child should now be ready"


def test_comms_dag_complete_idempotent():
    """Completing an already-done task returns [] with no second DB write."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import complete_task, post_message

    conn = get_db()
    mid = post_message(
        conn,
        board="feature",
        scope="f5",
        from_agent="builder",
        type="task",
        text="task",
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()

    first = complete_task(conn, mid)
    assert isinstance(first, list)

    second = complete_task(conn, mid)
    assert second == [], "completing a done task should return []"

    row = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    assert row["task_status"] == "done"


def test_comms_dag_circular_dep_handled():
    """Two tasks depending on each other are both blocked — no crash."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_ready_tasks, post_message

    conn = get_db()
    a_id = post_message(
        conn,
        board="feature",
        scope="f6",
        from_agent="builder",
        type="task",
        text="task A",
    )
    b_id = post_message(
        conn,
        board="feature",
        scope="f6",
        from_agent="builder",
        type="task",
        text="task B",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
        (json.dumps([b_id]), a_id),
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
        (json.dumps([a_id]), b_id),
    )
    conn.commit()

    ready = get_ready_tasks(conn, boards=["feature"], scopes=["f6"])
    ready_ids = {r["id"] for r in ready}
    assert a_id not in ready_ids, "circular dep A should not be ready"
    assert b_id not in ready_ids, "circular dep B should not be ready"


# ---------------------------------------------------------------------------
# HTTP-layer tests
# ---------------------------------------------------------------------------


def test_comms_dag_http_get_ready(client):
    """GET /comms/tasks?feature=x&ready=true returns tasks with all deps met."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    dep_id = post_message(
        conn,
        board="feature",
        scope="http1",
        from_agent="builder",
        type="task",
        text="dep task",
    )
    child_id = post_message(
        conn,
        board="feature",
        scope="http1",
        from_agent="builder",
        type="task",
        text="child task",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id IN (?, ?)",
        (dep_id, child_id),
    )
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?",
        (json.dumps([dep_id]), child_id),
    )
    conn.commit()

    r = client.get("/comms/tasks?feature=http1&scope=http1&ready=true")
    assert r.status_code == 200
    data = json.loads(r.data)
    ids = {m["id"] for m in data}
    assert dep_id in ids, "dep task (no unmet deps) should appear as ready"
    assert child_id not in ids, "child with unmet dep should not appear as ready"


def test_comms_dag_http_get_all_pending(client):
    """GET /comms/tasks?feature=x&status=pending returns all pending tasks."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    dep_id = post_message(
        conn,
        board="feature",
        scope="http2",
        from_agent="builder",
        type="task",
        text="dep task",
    )
    child_id = post_message(
        conn,
        board="feature",
        scope="http2",
        from_agent="builder",
        type="task",
        text="child task",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id IN (?, ?)",
        (dep_id, child_id),
    )
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?",
        (json.dumps([dep_id]), child_id),
    )
    conn.commit()

    r = client.get("/comms/tasks?feature=http2&scope=http2&status=pending")
    assert r.status_code == 200
    data = json.loads(r.data)
    ids = {m["id"] for m in data}
    assert dep_id in ids
    assert child_id in ids


def test_comms_dag_http_complete_broadcasts(client):
    """POST /comms/tasks/complete returns 200 with newly_ready list."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    dep_id = post_message(
        conn,
        board="feature",
        scope="http3",
        from_agent="builder",
        type="task",
        text="dep task",
    )
    child_id = post_message(
        conn,
        board="feature",
        scope="http3",
        from_agent="builder",
        type="task",
        text="child task",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id IN (?, ?)",
        (dep_id, child_id),
    )
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?",
        (json.dumps([dep_id]), child_id),
    )
    conn.commit()

    r = client.post(
        "/comms/tasks/complete",
        json={
            "message_id": dep_id,
            "feature": "http3",
        },
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["ok"] is True
    assert child_id in data["newly_ready"]


def test_comms_dag_http_complete_idempotent(client):
    """POST /comms/tasks/complete on an already-done task returns 200 with empty newly_ready."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    mid = post_message(
        conn,
        board="feature",
        scope="http4",
        from_agent="builder",
        type="task",
        text="solo task",
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()

    r1 = client.post(
        "/comms/tasks/complete", json={"message_id": mid, "feature": "http4"}
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/comms/tasks/complete", json={"message_id": mid, "feature": "http4"}
    )
    assert r2.status_code == 200
    data = json.loads(r2.data)
    assert data["ok"] is True
    assert data["newly_ready"] == []


def test_comms_dag_http_missing_feature(client):
    """GET /comms/tasks without feature param returns 400."""
    r = client.get("/comms/tasks")
    assert r.status_code == 400


def test_comms_dag_http_complete_missing_message_id(client):
    """POST /comms/tasks/complete without message_id returns 400."""
    r = client.post("/comms/tasks/complete", json={"feature": "x"})
    assert r.status_code == 400
