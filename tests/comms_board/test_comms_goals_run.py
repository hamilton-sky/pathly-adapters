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


@pytest.fixture(autouse=True)
def _clear_file_claims():
    """Isolate the module-level file-claim registry between tests."""
    from pathly_orchestrator.supervisor import file_claims

    file_claims._claims.clear()
    yield
    file_claims._claims.clear()


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


def test_dispatch_loop_launches_the_goal_loop_fsm_flow():
    """Phase E: `executor: loop` runs the FSM, not a second engine.

    It used to drive `scheduler_loop` itself, top-level, as a peer of `orchestrator._loop`.
    Now it launches the `goal-loop` flow — whose single DRAINING state declares
    `parallel_states`, so the SAME scheduler drains the frontier as the executor OF a state.

    `goal-loop`, deliberately NOT `team-build`: `loop` is a flat drain, and retiring it into
    the team flow would hand a user who chose `loop` for speed a fully reviewed pipeline.
    """
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_loop", executor="loop")

    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="loop-run-1")

    result = start_goal_run(goal, project_root="/x", start_fn=fake_start, block=True)

    assert result["ok"] is True
    assert result["executor"] == "loop", "the dispatcher's label, not the flow's"
    assert result["run_id"] == "loop-run-1"
    assert captured["flow"] == "goal-loop"
    assert (
        captured["flow"] != "team-build"
    ), "loop must not become the reviewed pipeline"
    # The goal is carried, so require_tasks_done and the fan-out both scope to THIS goal.
    assert captured["goal_id"] == goal
    assert captured["interactive"] is False, "a goal run is headless"


def test_the_goal_loop_flow_is_flat_not_a_reviewed_pipeline():
    """The product guarantee, read off the packaged flow the executor names.

    If `goal-loop` ever grew a REVIEWING/TESTING stage it would stop being the fast path
    `executor: loop` exists to offer — the failure mode that made "retire loop into team"
    the wrong reading of Phase E.
    """
    import yaml

    from pathly_orchestrator.supervisor.goal_executor import _LOOP_FLOW
    from tests._paths import SRC

    flow = yaml.safe_load(
        (SRC / "pathly_data" / "core" / "flows" / f"{_LOOP_FLOW}.flow.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert flow["flow"] == _LOOP_FLOW
    assert flow["states"] == ["DRAINING", "DONE"], "one working state, then done"
    assert "parallel_states" in flow, "the drain must be a fan-out state"
    # The join still runs the ground-truth checks verify_clean_drain used to run by hand.
    gate_types = {g["type"] for g in flow["gates"]["DRAINING->DONE"]}
    assert gate_types == {"require_tasks_done", "command_gate"}


def test_dispatch_loop_creates_nested_goal_dir(tmp_path):
    """T6: the loop executor materializes its goal dir at the board-scoped nested home
    (pathly/features/<feature>/goals/<slug>) via _goal_storage_dir — never the flat
    pathly/goals/<slug> it used to hardcode. Every other goal path already nests; the loop
    was the one straggler. project_root must be set for the dir to be created at all (the
    existing loop tests pass '' and so never exercised this)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_loop_dir"
    goal = _make_goal(conn, scope, executor="loop")
    _make_task(conn, scope, "task-A", goal)

    result = start_goal_run(
        goal,
        project_root=str(tmp_path),
        spawn_fn=lambda *a, **k: {"ok": True},
        block=True,
    )
    assert result["ok"] is True

    nested = tmp_path / "pathly" / "features" / scope / "goals"
    assert (
        nested.is_dir()
    ), "loop goal dir must nest under pathly/features/<feature>/goals/"
    assert list(
        nested.iterdir()
    ), "the goal-slug dir must exist under features/<f>/goals/"
    assert not (
        tmp_path / "pathly" / "goals"
    ).exists(), "the flat pathly/goals/ home must not be created"


def test_dispatch_loop_scopes_the_run_to_its_own_goal():
    """A loop run addresses only ITS goal — a sibling goal on the same board is untouched.

    Scoping used to be asserted by draining and checking which tasks ran. The drain moved
    into the FSM stage (covered end-to-end in tests/runner_supervisor/test_fan_out.py), so
    what this pins now is the pair that carries the scoping: the goal_id threaded into the
    run, and the per-goal storage topic that keeps two goals on one board apart.
    """
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_loop_scoped"
    g1 = _make_goal(conn, scope, executor="loop", text="Goal 1")
    g2 = _make_goal(conn, scope, executor="loop", text="Goal 2")

    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="loop-run-1")

    start_goal_run(g1, project_root="/x", start_fn=fake_start, block=True)

    assert captured["goal_id"] == g1
    assert captured["goal_id"] != g2
    assert captured["topic"].startswith(f"features/{scope}/goals/")
    assert g1[:8] in captured["topic"] and g2[:8] not in captured["topic"]


def test_dispatch_executor_override_wins_and_persists():
    """executor_override beats the goal's stored executor and is persisted back."""
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    scope = "gr_override"
    goal = _make_goal(conn, scope, executor="single")  # stored as single

    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="loop-run-1")

    # Override to loop → launches the goal-loop flow (not board_run) and persists 'loop'.
    result = start_goal_run(
        goal,
        executor_override="loop",
        project_root="/x",
        start_fn=fake_start,
        block=True,
    )
    assert result["ok"] is True
    assert result["executor"] == "loop"
    assert captured["flow"] == "goal-loop"

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
    # topic is the scope-nested goal path (features/<scope>/goals/<slug>), so the team-build run's
    # storage nests under the feature the goal lives on — not the raw scope, not a flat slug.
    topic = captured["topic"]
    assert topic.startswith(
        "features/gr_team/goals/"
    ), "team-build storage nests under the feature"
    assert (
        goal[:8] in topic
    ), "the slug (with the goal id prefix) is the trailing segment"
    assert topic != "gr_team" and " " not in topic  # filesystem-safe scope-nested path


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


def test_dispatch_debug_flow_nests_under_debugs(tmp_path):
    """board-scoped-storage: a flow run ON a board nests under that board by the flow's KIND —
    a debug flow lands at features/<f>/debugs/<slug>, NOT goals/<slug>."""
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_dbg_nest", executor="team")
    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="dbg-1")

    result = start_goal_run(
        goal,
        flow_override="debug",
        project_root=str(tmp_path),
        start_fn=fake_start,
        block=True,
    )
    assert result["ok"] is True and result["flow"] == "debug"
    topic = captured["topic"]
    assert topic.startswith("features/gr_dbg_nest/debugs/"), topic
    assert "/goals/" not in topic
    # the nested board dir is materialized so _resolve_storage_path lands the run there
    assert (tmp_path / "pathly" / "features" / "gr_dbg_nest" / "debugs").is_dir()


def test_dispatch_custom_flow_nests_under_flow_name(tmp_path):
    """A custom/user-created flow gets its OWN name as the board folder kind:
    features/<f>/<flow>/<slug>. New flows are self-describing on disk — no code change to add one.
    """
    import types
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_custom", executor="team")
    captured = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="c-1")

    result = start_goal_run(
        goal,
        flow_override="audit",
        project_root=str(tmp_path),
        start_fn=fake_start,
        block=True,
    )
    assert result["ok"] is True
    assert captured["topic"].startswith("features/gr_custom/audit/"), captured["topic"]
    assert (tmp_path / "pathly" / "features" / "gr_custom" / "audit").is_dir()


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


def test_dispatch_gate_serializes_on_file_overlap():
    """A feature whose files overlap an ACTIVE feature's claim is refused (project_busy)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor import file_claims
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_overlap", executor="single")
    _make_task(conn, "gr_overlap", "edit x", goal)  # no files declared -> wildcard
    file_claims.try_claim(
        "feature-A", {"src/x.ts"}
    )  # a sibling is already editing src/x.ts
    result = start_goal_run(goal, project_root="", spawn_fn=lambda **k: {}, block=True)
    assert result["ok"] is False
    assert result["reason"] == "project_busy"
    assert result["holder"] == "feature-A"


def test_dispatch_gate_allows_disjoint_files_in_parallel():
    """Two features touching DISJOINT files (e.g. backend vs frontend) run in parallel."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.supervisor import file_claims
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    goal = _make_goal(conn, "gr_frontend", executor="single")
    post_message(
        conn,
        board="feature",
        scope="gr_frontend",
        from_agent="planner",
        type="task",
        text="edit UI",
        goal_id=goal,
        files=["studio/src/app.tsx"],
    )
    file_claims.try_claim(
        "feature-backend", {"src/pathly_orchestrator/x.py"}
    )  # disjoint
    result = start_goal_run(goal, project_root="", spawn_fn=lambda **k: {}, block=True)
    assert result["ok"] is True  # disjoint -> runs in parallel, not refused
    assert result["executor"] == "single"


def test_dispatch_gate_off_allows_overlap(monkeypatch):
    """serialize_feature_builds=false drops the gate entirely (overlap allowed)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting
    from pathly_orchestrator.supervisor import file_claims
    from pathly_orchestrator.supervisor.goal_run import start_goal_run

    conn = get_db()
    set_setting(conn, "serialize_feature_builds", "false")
    try:
        goal = _make_goal(conn, "gr_toggle", executor="single")
        _make_task(conn, "gr_toggle", "edit x", goal)
        file_claims.try_claim(
            "feature-A", {"src/x.ts"}
        )  # would overlap, but gate is OFF
        result = start_goal_run(
            goal, project_root="", spawn_fn=lambda **k: {}, block=True
        )
        assert result["ok"] is True  # gate off -> runs despite overlap
    finally:
        set_setting(conn, "serialize_feature_builds", "true")


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


def test_http_goals_run_parked_status_posts_paused_not_failed(client, monkeypatch):
    """A parked run (headless human checkpoint, RunnerState.status == "parked") is a
    deliberate non-failure — resumable via /runner/resume-parked, per CLAUDE.md's Human
    checkpoints section. It must not fold into the generic 'goal run failed' text/phase
    the way any other res["error"] does."""
    import types
    from pathly_orchestrator.db.connection import get_db
    import pathly_orchestrator.http_server.blueprints.comms.goals as _goals_mod
    import pathly_orchestrator.supervisor.api as _api

    conn = get_db()
    scope = "gr_http_parked"
    goal = _make_goal(conn, scope, executor="team")
    broadcasts = []
    monkeypatch.setattr(
        _goals_mod,
        "_broadcast_comms",
        lambda scope, payload: broadcasts.append(payload),
    )

    def fake_start_run(**kw):
        kw["on_done"]("run-1", {"error": "parked", "status": "parked"})
        return types.SimpleNamespace(run_id="run-1")

    monkeypatch.setattr(_api, "start_run", fake_start_run)

    r = client.post("/comms/goals/run", json={"goal_id": goal})
    assert r.status_code == 200, r.data

    rows = conn.execute(
        "SELECT text FROM comms_messages WHERE scope=? AND type='status'",
        (scope,),
    ).fetchall()
    texts_lower = [r["text"].lower() for r in rows]
    assert any("paused" in t for t in texts_lower), texts_lower
    assert not any("failed" in t for t in texts_lower), texts_lower

    # Order isn't asserted: _run_team fires on_start AFTER start_fn returns (a REAL run's
    # on_done fires asynchronously, much later — this test's synchronous stub inverts
    # that). What matters is that "error" never appears for a parked run.
    phases = [b.get("phase") for b in broadcasts if b.get("event") == "goal_run"]
    assert "stopped" in phases
    assert "error" not in phases


def test_http_goals_run_stage_overrides_validated_against_the_chosen_flow(
    client, monkeypatch
):
    """stage_overrides must be validated against the flow ACTUALLY being run (`flow`),
    not a hardcoded "team-build" — a debug-flow goal run's FIXING override was
    previously silently dropped because FIXING isn't a team-build.flow.yaml state."""
    import types
    from pathly_orchestrator.db.connection import get_db
    import pathly_orchestrator.supervisor.api as _api

    conn = get_db()
    goal = _make_goal(conn, "gr_http_stage_override", executor="team")
    captured = {}

    def fake_start_run(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="r-http-override")

    monkeypatch.setattr(_api, "start_run", fake_start_run)

    r = client.post(
        "/comms/goals/run",
        json={
            "goal_id": goal,
            "flow": "debug",
            "stage_overrides": {"FIXING": "custom override text"},
        },
    )

    assert r.status_code == 200, r.data
    assert captured.get("stage_overrides") == {"FIXING": "custom override text"}


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


def test_decompose_plan_routes_to_planning_plan():
    """mode='plan' runs the planning/plan skill as ONE board agent → a context_refs DAG."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_run import start_goal_decompose

    conn = get_db()
    goal = _make_goal(conn, "dec_plan")
    seen = {}

    def fake_board_spawn(**kw):
        seen.update(kw)
        return {"result": "seeded"}

    result = start_goal_decompose(
        goal, mode="plan", project_root="", spawn_fn=fake_board_spawn, block=True
    )
    assert result["ok"] is True
    assert result["mode"] == "plan"
    # the planning/plan skill body is composed into the prompt (it derives context_refs)...
    assert "context_refs" in seen["prompt"]
    # ...and the directive names the existing goal so the planner reuses it (no duplicate).
    assert goal in seen["prompt"]


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

    def _sentinel_done(run_id, res):
        pass

    result = start_goal_decompose(
        goal,
        mode="consultation",
        project_root="/x",
        start_fn=fake_start,
        on_done=_sentinel_done,
    )
    assert result["ok"] is True
    assert result["mode"] == "consultation"
    assert captured["flow"] == "consultation"
    # A board-context decompose has no human at a terminal, so the consultation flow
    # must run headless — an interactive PTY would block waiting for input.
    assert captured["interactive"] is False
    # The goal_id is threaded so the terminal planner seeds THIS goal's DAG (not a new
    # goal), and on_done is wired so the board's "Decomposing…" indicator clears on
    # terminal status even when the flow errors out.
    assert captured["goal_id"] == goal
    assert captured["on_done"] is _sentinel_done


def test_decompose_directive_targets_only_the_dag_seeder():
    """The 'seed THIS goal' suffix fires only for planning/plan with a goal_id set."""
    from pathly_orchestrator.supervisor.orchestrator import _decompose_directive

    d = _decompose_directive("planning/plan", "g-123")
    assert "g-123" in d and "Decompose target" in d and "do NOT post a new goal" in d
    # No goal_id → no directive (a normal flow run, not a decompose).
    assert _decompose_directive("planning/plan", "") == ""
    # Other stages (PO, architect, the team-flow planner) must not get it — only the
    # board-DAG seeder does.
    assert _decompose_directive("planning/po", "g-123") == ""
    assert _decompose_directive("team/plan", "g-123") == ""
    assert _decompose_directive("team/build", "g-123") == ""


def test_start_run_fires_on_done_on_terminal_status(tmp_path, monkeypatch):
    """A supervised run fires on_done once it reaches a terminal status.

    This is what clears the board's "Decomposing…" indicator — without it, a consultation
    decompose that ends in error leaves the timer running forever (the bug we hit).
    """
    import threading

    from pathly_orchestrator import fsm_http_client as fhc
    from pathly_orchestrator.supervisor.api import start_run

    # FSM reports done on the first poll → _loop returns at once with status='done'.
    monkeypatch.setattr(fhc, "next_action", lambda args: {"done": True})

    seen: dict = {}
    fired = threading.Event()

    def _on_done(run_id, res):
        seen["run_id"] = run_id
        seen["res"] = res
        fired.set()

    state = start_run(
        topic="on_done_topic",
        flow="consultation",
        project_root=str(tmp_path),
        broadcast_fn=None,
        goal_id="g-xyz",
        on_done=_on_done,
    )
    assert fired.wait(
        timeout=5
    ), "on_done must fire when the run reaches terminal status"
    assert seen["run_id"] == state.run_id
    assert seen["res"]["status"] == "done"
    assert state.goal_id == "g-xyz"  # goal_id threaded onto the run


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


# ---------------------------------------------------------------------------
# Stale-state reset — re-running an FSM flow on a scope must not no-op.
# These drive the REAL next_action (no mock on the FSM side) so the round-trip
# is exercised end-to-end: a scope left at DONE (or a foreign flow's state) is
# the "run started but no terminal opened" trap.
# ---------------------------------------------------------------------------


def _consultation_storage(root: str, scope: str):
    from pathlib import Path

    from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path

    flow_cfg = _load_flow("consultation", root)
    storage = Path(str(_resolve_storage_path(flow_cfg, root, scope)))
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def test_reset_unsticks_done_consultation_real_fsm(tmp_path):
    """A scope parked at DONE makes next_action short-circuit; reset re-seeds the PO stage."""
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.fsm_ops import next_action
    from pathly_orchestrator.supervisor.goal_executor import _reset_fsm_state_for_flow

    scope = "reset_done"
    root = str(tmp_path)
    storage = _consultation_storage(root, scope)
    eventlog._write_state_db(storage, storage.name, {"current": "DONE"})

    # Before the reset: the real FSM reports done and would spawn nothing.
    pre = next_action({"flow": "consultation", "topic": scope, "project_root": root})
    assert pre.get("done") is True

    _reset_fsm_state_for_flow("consultation", scope, root)

    post = next_action({"flow": "consultation", "topic": scope, "project_root": root})
    assert not post.get("done"), "after reset the flow must re-run, not report done"
    assert post["current_state"] == "PO_DISCUSSING"


def test_reset_unsticks_foreign_state_real_fsm(tmp_path):
    """A scope left in another flow's state (team's BUILDING) is re-seeded to this flow's start."""
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.fsm_ops import next_action
    from pathly_orchestrator.supervisor.goal_executor import _reset_fsm_state_for_flow

    scope = "reset_foreign"
    root = str(tmp_path)
    storage = _consultation_storage(root, scope)
    # BUILDING is a team-flow state — the consultation flow has no agent_map entry for it.
    eventlog._write_state_db(storage, storage.name, {"current": "BUILDING"})

    _reset_fsm_state_for_flow("consultation", scope, root)

    post = next_action({"flow": "consultation", "topic": scope, "project_root": root})
    assert post["current_state"] == "PO_DISCUSSING"


def test_reset_preserves_valid_midflow(tmp_path):
    """A valid, non-terminal state for THIS flow is left untouched so the run can resume."""
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.supervisor.goal_executor import _reset_fsm_state_for_flow

    scope = "reset_midflow"
    root = str(tmp_path)
    storage = _consultation_storage(root, scope)
    eventlog._write_state_db(storage, storage.name, {"current": "ARCHITECTING"})

    _reset_fsm_state_for_flow("consultation", scope, root)

    cur = (eventlog.read_state(str(storage)) or {}).get("current")
    assert cur == "ARCHITECTING", "a resumable mid-flow state must not be clobbered"
