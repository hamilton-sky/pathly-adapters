"""Tests for Phase 1 — the goal executor dispatcher (start_goal_run + /comms/goals/run).

Execution paths (single/loop) are driven with injected fake spawns and block=True so
no real PTY/agent is launched. The HTTP route is tested on the paths that route
WITHOUT spawning (validation, not-found, non-goal, team-gated).
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


def _make_goal(conn, scope, executor="single", text="Goal: x"):
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text=text,
        executor=executor,
    )


def _make_task(conn, scope, text, goal_id, depends_on=None):
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        goal_id=goal_id,
        depends_on=depends_on,
    )


# ---------------------------------------------------------------------------
# start_goal_run — routing + execution (block=True, fake spawns)
# ---------------------------------------------------------------------------


def test_dispatch_single_routes_to_board_run():
    """executor='single' delegates to board_run with the drain-dag skill."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_single"
    goal = _make_goal(conn, scope, executor="single")

    seen = {}

    def fake_board_spawn(**kw):
        seen.update(kw)
        return {"result": "drained"}

    result = start_goal_run(
        goal, project_root="", spawn_fn=fake_board_spawn, block=True
    )

    assert result["ok"] is True
    assert result["executor"] == "single"
    assert result["goal_id"] == goal
    # The composed prompt carries the drain-dag contract + the goal_id directive.
    assert goal in seen["prompt"]
    assert "ready" in seen["prompt"].lower()
    assert seen["mode"] == "single-agent"


def test_dispatch_loop_runs_scheduler_in_order():
    """executor='loop' drives scheduler_loop over the goal's DAG (serial, in order)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_loop"
    goal = _make_goal(conn, scope, executor="loop")
    a = _make_task(conn, scope, "task-A", goal)
    b = _make_task(conn, scope, "task-B", goal, depends_on=[a])

    order = []

    def fake_sched_spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        order.append(run_id[len("sched-") :] if run_id.startswith("sched-") else run_id)
        return {"ok": True}

    result = start_goal_run(
        goal, project_root="", spawn_fn=fake_sched_spawn, block=True
    )

    assert result["ok"] is True
    assert result["executor"] == "loop"
    sched = result["result"]
    assert set(sched["completed"]) == {a, b}
    assert sched["failed"] == [] and sched["blocked"] == []
    assert order == [a, b], "A must run before B (B depends on A)"


def test_dispatch_loop_scopes_to_goal():
    """A loop run drains only ITS goal's tasks, not a sibling goal in the same scope."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_loop_scoped"
    g1 = _make_goal(conn, scope, executor="loop", text="Goal 1")
    g2 = _make_goal(conn, scope, executor="loop", text="Goal 2")
    t1 = _make_task(conn, scope, "g1-task", g1)
    t2 = _make_task(conn, scope, "g2-task", g2)

    ran = []

    def fake_sched_spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        ran.append(run_id[len("sched-") :] if run_id.startswith("sched-") else run_id)
        return {"ok": True}

    result = start_goal_run(g1, project_root="", spawn_fn=fake_sched_spawn, block=True)

    assert set(result["result"]["completed"]) == {t1}
    assert t2 not in ran, "goal 2's task must not run under goal 1's loop"


def test_dispatch_executor_override_wins_and_persists():
    """executor_override beats the goal's stored executor and is persisted back."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_override"
    goal = _make_goal(conn, scope, executor="single")  # stored as single
    t = _make_task(conn, scope, "task-A", goal)

    ran = []

    def fake_sched_spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        ran.append(run_id)
        return {"ok": True}

    # Override to loop → runs the scheduler (not board_run) and persists 'loop'.
    result = start_goal_run(
        goal, executor_override="loop", spawn_fn=fake_sched_spawn, block=True
    )
    assert result["ok"] is True
    assert result["executor"] == "loop"
    assert set(result["result"]["completed"]) == {t}

    row = conn.execute(
        "SELECT executor FROM comms_messages WHERE id=?", (goal,)
    ).fetchone()
    assert row["executor"] == "loop", "override should persist onto the goal"


def test_dispatch_team_routes_to_team_build_flow():
    """executor='team' launches the team-build FSM flow via start_run."""
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_team", executor="team")

    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="team-run-1")

    result = start_goal_run(goal, project_root="/x", start_fn=fake_start, block=True)
    assert result["ok"] is True
    assert result["executor"] == "team"
    assert result["run_id"] == "team-run-1"
    assert (
        captured["flow"] == "team-build"
    ), "team executor must run the trimmed team-build flow"
    assert captured["topic"] == "gr_team"


def test_dispatch_team_custom_flow():
    """executor='team' with flow=… runs that flow on the goal, not just team-build."""
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_team_flow", executor="team")
    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="r-debug")

    result = start_goal_run(
        goal, flow_override="debug", project_root="/x", start_fn=fake_start, block=True
    )
    assert result["ok"] is True
    assert result["flow"] == "debug"
    assert (
        captured["flow"] == "debug"
    ), "the chosen flow runs, not the team-build default"


def test_dispatch_team_board_busy():
    """team refuses when a run already holds the board lock (serial)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_team_busy"
    goal = _make_goal(conn, scope, executor="team")
    board_lock.acquire("feature", scope, "someone-else")
    try:
        result = start_goal_run(goal, start_fn=lambda **k: None, block=True)
        assert result["ok"] is False
        assert result["reason"] == "board_busy"
    finally:
        board_lock.release("feature", scope, "someone-else")


def test_dispatch_goal_not_found():
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    result = start_goal_run("no-such-goal-id", block=True)
    assert result["ok"] is False
    assert result["reason"] == "not_found"


def test_dispatch_non_goal_rejected():
    """Pointing the dispatcher at a task (not a goal) is rejected."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_nongoal"
    goal = _make_goal(conn, scope)
    task = _make_task(conn, scope, "a task", goal)
    result = start_goal_run(task, block=True)
    assert result["ok"] is False
    assert result["reason"] == "not_goal"


# ---------------------------------------------------------------------------
# HTTP route — non-spawning paths only
# ---------------------------------------------------------------------------


def test_http_goals_run_missing_goal_id(client):
    r = client.post("/comms/goals/run", json={})
    assert r.status_code == 400


def test_http_goals_run_not_found(client):
    r = client.post("/comms/goals/run", json={"goal_id": "nope"})
    assert r.status_code == 404
    assert json.loads(r.data)["reason"] == "not_found"


def test_http_goals_run_team(client, monkeypatch):
    """POST a team goal → 200; start_run is stubbed so no real pipeline spawns."""
    import types
    from pathly_orchestrator.db.connection import get_db
    import pathly_orchestrator.supervisor.api as _api

    conn = get_db()
    goal = _make_goal(conn, "gr_http_team", executor="team")
    monkeypatch.setattr(
        _api, "start_run", lambda **kw: types.SimpleNamespace(run_id="r-http-team")
    )

    r = client.post("/comms/goals/run", json={"goal_id": goal})
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert body["executor"] == "team"


def test_http_goals_run_non_goal(client):
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "gr_http_nongoal"
    goal = _make_goal(conn, scope)
    task = _make_task(conn, scope, "a task", goal)
    r = client.post("/comms/goals/run", json={"goal_id": task})
    assert r.status_code == 400
    assert json.loads(r.data)["reason"] == "not_goal"


def test_http_tasks_ready_goal_id_filter(client):
    """GET /comms/tasks?ready=true&goal_id=… returns only that goal's ready tasks."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "gr_http_filter"
    g1 = _make_goal(conn, scope, text="G1")
    g2 = _make_goal(conn, scope, text="G2")
    t1 = _make_task(conn, scope, "g1 task", g1)
    t2 = _make_task(conn, scope, "g2 task", g2)

    r = client.get(
        f"/comms/tasks?feature={scope}&scope={scope}&ready=true&goal_id={g1}"
    )
    assert r.status_code == 200
    ids = {m["id"] for m in json.loads(r.data)}
    assert t1 in ids
    assert t2 not in ids


# ---------------------------------------------------------------------------
# Decompose bridge — goal → task DAG (planner | consultation)
# ---------------------------------------------------------------------------


def test_decompose_planner_routes_to_board_run():
    """mode='planner' runs the planner on the goal's scope to seed the DAG."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

    conn = get_db()
    scope = "dec_planner"
    goal = _make_goal(conn, scope)
    seen = {}

    def fake_board_spawn(**kw):
        seen.update(kw)
        return {"result": "seeded"}

    result = start_goal_decompose(
        goal, mode="planner", project_root="", spawn_fn=fake_board_spawn, block=True
    )
    assert result["ok"] is True
    assert result["mode"] == "planner"
    # the directive tells the planner the goal already exists and to stamp tasks with it
    assert goal in seen["prompt"]
    assert "task" in seen["prompt"].lower()


def test_decompose_consultation_routes_to_consultation_flow():
    """mode='consultation' launches the consultation FSM flow."""
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

    conn = get_db()
    goal = _make_goal(conn, "dec_consult")
    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="cons-1")

    result = start_goal_decompose(
        goal, mode="consultation", project_root="/x", start_fn=fake_start
    )
    assert result["ok"] is True
    assert result["mode"] == "consultation"
    assert captured["flow"] == "consultation"


def test_decompose_already_decomposed():
    """Refuse to decompose a goal that already has tasks."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

    conn = get_db()
    scope = "dec_already"
    goal = _make_goal(conn, scope)
    _make_task(conn, scope, "existing task", goal)
    result = start_goal_decompose(goal, mode="planner", block=True)
    assert result["ok"] is False
    assert result["reason"] == "already_decomposed"


def test_decompose_unknown_mode():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

    conn = get_db()
    goal = _make_goal(conn, "dec_badmode")
    result = start_goal_decompose(goal, mode="magic", block=True)
    assert result["ok"] is False
    assert result["reason"] == "unknown_mode"


def test_decompose_not_a_goal():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

    conn = get_db()
    scope = "dec_nongoal"
    goal = _make_goal(conn, scope)
    task = _make_task(conn, scope, "a task", goal)
    result = start_goal_decompose(task, mode="planner", block=True)
    assert result["ok"] is False
    assert result["reason"] == "not_goal"


def test_http_decompose_missing_goal_id(client):
    r = client.post("/comms/goals/decompose", json={})
    assert r.status_code == 400


def test_http_decompose_not_found(client):
    r = client.post("/comms/goals/decompose", json={"goal_id": "nope"})
    assert r.status_code == 404


def test_http_decompose_already(client):
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "dec_http_already"
    goal = _make_goal(conn, scope)
    _make_task(conn, scope, "t", goal)
    r = client.post("/comms/goals/decompose", json={"goal_id": goal})
    assert r.status_code == 409
    assert json.loads(r.data)["reason"] == "already_decomposed"
