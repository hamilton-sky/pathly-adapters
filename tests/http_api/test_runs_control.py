"""POST /runs/<run_id>/stop, /runs/<run_id>/<action> — the run_id-addressed control surface
(unified-control-plane).

Resolves a run_id to its live control path: a registry RunnerState → the matching topic-keyed
supervisor fn (FSM flows), a board-lock holder → board stop (board single/evaluator, goal
single/loop; only ``abort`` is supported there), else not_active.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_find_by_holder_reverse_lookup():
    from pathly_orchestrator.supervisor import board_lock

    board_lock.acquire("feature", "sc1", "run-1")
    try:
        assert board_lock.find_by_holder("run-1") == ("feature", "sc1")
        assert board_lock.find_by_holder("nope") is None
        assert board_lock.find_by_holder("") is None
    finally:
        board_lock.release("feature", "sc1", "run-1")


def test_stop_unknown_run_is_not_active(client):
    body = client.post("/runs/ghost-run/stop").get_json()
    assert body["ok"] is True
    assert body["stopped"] is False and body["reason"] == "not_active"


def test_stop_board_run_releases_the_lock(client):
    from pathly_orchestrator.supervisor import board_lock

    assert board_lock.acquire("feature", "sc2", "run-board")
    body = client.post("/runs/run-board/stop").get_json()
    assert body["stopped"] is True and body["via"] == "board_stop"
    assert board_lock.holder("feature", "sc2") is None  # released by the stop


def test_stop_fsm_run_aborts_via_registry(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-stop", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-fsm", status="running",
    )
    with _lock:
        _registry["t-stop"] = state
    try:
        body = client.post("/runs/run-fsm/stop").get_json()
        assert body["stopped"] is True and body["via"] == "runner_abort"
        assert state._abort_flag is True  # abort_run flipped the flag
    finally:
        with _lock:
            _registry.pop("t-stop", None)


def test_action_unknown_action_is_400(client):
    resp = client.post("/runs/some-run/frobnicate")
    assert resp.status_code == 400


def test_action_unknown_run_is_not_active(client):
    body = client.post("/runs/ghost-run/pause").get_json()
    assert body["ok"] is False
    assert body["reason"] == "not_active"


def test_action_board_lock_run_rejects_flow_only_action(client):
    from pathly_orchestrator.supervisor import board_lock

    assert board_lock.acquire("feature", "sc3", "run-board-2")
    try:
        body = client.post("/runs/run-board-2/pause").get_json()
        assert body["ok"] is False
        assert body["reason"] == "unsupported_for_kind"
    finally:
        board_lock.release("feature", "sc3", "run-board-2")


def test_action_board_lock_run_supports_abort(client):
    from pathly_orchestrator.supervisor import board_lock

    assert board_lock.acquire("feature", "sc4", "run-board-3")
    body = client.post("/runs/run-board-3/abort").get_json()
    assert body["ok"] is True and body["via"] == "board_stop"
    assert board_lock.holder("feature", "sc4") is None  # released by the abort


def test_action_pause_flow_run_via_registry(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-pause", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-pause", status="running",
    )
    with _lock:
        _registry["t-pause"] = state
    try:
        body = client.post("/runs/run-pause/pause").get_json()
        assert body["ok"] is True
        assert state._pause_flag is True  # pause_run flipped the flag
    finally:
        with _lock:
            _registry.pop("t-pause", None)


def test_action_resume_flow_run_clears_pause_flag(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-resume", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-resume", status="paused",
    )
    state._pause_flag = True
    with _lock:
        _registry["t-resume"] = state
    try:
        body = client.post("/runs/run-resume/resume").get_json()
        assert body["ok"] is True
        assert state._pause_flag is False  # resume_run cleared the flag
    finally:
        with _lock:
            _registry.pop("t-resume", None)


def test_action_advance_flow_run_clears_pause_flag(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-advance", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-advance", status="paused",
    )
    state._pause_flag = True
    with _lock:
        _registry["t-advance"] = state
    try:
        body = client.post("/runs/run-advance/advance").get_json()
        assert body["ok"] is True
        assert state._pause_flag is False  # advance mirrors resume_run
    finally:
        with _lock:
            _registry.pop("t-advance", None)


def test_action_reroute_requires_adapter_then_applies_it(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-reroute", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-reroute", status="running",
    )
    with _lock:
        _registry["t-reroute"] = state
    try:
        resp = client.post("/runs/run-reroute/reroute", json={})
        assert resp.status_code == 400

        resp = client.post(
            "/runs/run-reroute/reroute", json={"adapter": "codex", "stage": "BUILDING"}
        )
        body = resp.get_json()
        assert body["ok"] is True
        assert state._reroute_adapter == "codex"
    finally:
        with _lock:
            _registry.pop("t-reroute", None)


def test_action_retry_rejects_active_run(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-retry-active", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-retry-active", status="running",
    )
    with _lock:
        _registry["t-retry-active"] = state
    try:
        body = client.post("/runs/run-retry-active/retry", json={}).get_json()
        assert body["ok"] is False and body["reason"] == "already_active"
    finally:
        with _lock:
            _registry.pop("t-retry-active", None)


def test_action_retry_missing_fields_is_400(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-retry", flow="team", project_root="/p", model="", timeout=600,
        run_id="run-retry", status="error",
    )
    with _lock:
        _registry["t-retry"] = state
    try:
        resp = client.post("/runs/run-retry/retry", json={})
        assert resp.status_code == 400
    finally:
        with _lock:
            _registry.pop("t-retry", None)


# ---------------------------------------------------------------------------
# POST /runs (create) — thin RunSpec routed to the matching EXISTING facade
# ---------------------------------------------------------------------------


def test_create_run_missing_kind_is_400(client):
    resp = client.post("/runs", json={})
    assert resp.status_code == 400


def test_create_run_bad_kind_is_400(client):
    resp = client.post("/runs", json={"kind": "not-a-kind"})
    assert resp.status_code == 400


def test_create_run_flow_routes_to_start_run(client, monkeypatch):
    import types

    import pathly_orchestrator.supervisor.api as _api

    captured = {}

    def fake_start_run(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="run-flow-launch")

    monkeypatch.setattr(_api, "start_run", fake_start_run)

    resp = client.post(
        "/runs",
        json={
            "kind": "flow",
            "scope": "my-topic",
            "flow": "team",
            "project_root": "/tmp/proj",
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json() == {"ok": True, "run_id": "run-flow-launch", "kind": "flow"}
    assert captured["topic"] == "my-topic"
    assert captured["flow"] == "team"
    assert captured["project_root"] == "/tmp/proj"
    assert callable(captured["broadcast_fn"])


def test_create_run_flow_missing_project_root_is_400(client):
    resp = client.post("/runs", json={"kind": "flow", "scope": "s", "flow": "team"})
    assert resp.status_code == 400


def test_create_run_flow_already_active_is_409(client, monkeypatch):
    import pathly_orchestrator.supervisor.api as _api

    def fake_start_run(**kw):
        raise ValueError("already active")

    monkeypatch.setattr(_api, "start_run", fake_start_run)

    resp = client.post(
        "/runs",
        json={"kind": "flow", "scope": "s", "flow": "team", "project_root": "/p"},
    )
    assert resp.status_code == 409


def test_create_run_single_routes_to_start_board_run(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    captured = {}

    def fake_start_board_run(board, scope, mode, **kw):
        captured["board"] = board
        captured["scope"] = scope
        captured["mode"] = mode
        return {"ok": True, "run_id": "run-board-launch", "mode": mode, "status": "started"}

    monkeypatch.setattr(_br, "start_board_run", fake_start_board_run)

    resp = client.post(
        "/runs", json={"kind": "single", "board": "feature", "scope": "sc-launch"}
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json() == {"ok": True, "run_id": "run-board-launch", "kind": "single"}
    assert captured["board"] == "feature"
    assert captured["scope"] == "sc-launch"
    assert captured["mode"] == "single-agent"


def test_create_run_evaluator_maps_to_evaluator_mode(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    captured = {}

    def fake_start_board_run(board, scope, mode, **kw):
        captured["mode"] = mode
        return {"ok": True, "run_id": "run-eval-launch", "mode": mode, "status": "started"}

    monkeypatch.setattr(_br, "start_board_run", fake_start_board_run)

    resp = client.post(
        "/runs", json={"kind": "evaluator", "board": "feature", "scope": "sc-eval"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["kind"] == "evaluator"
    assert captured["mode"] == "evaluator"


def test_create_run_board_busy_is_409(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    monkeypatch.setattr(
        _br,
        "start_board_run",
        lambda *a, **k: {"ok": False, "error": "board_busy", "holder": "someone"},
    )

    resp = client.post("/runs", json={"kind": "single", "scope": "sc-busy"})
    assert resp.status_code == 409
    assert resp.get_json()["ok"] is False


def test_create_run_missing_scope_is_400(client):
    resp = client.post("/runs", json={"kind": "single"})
    assert resp.status_code == 400


def test_create_run_goal_routes_to_start_goal_run(client, monkeypatch):
    import pathly_orchestrator.supervisor.goal_executor as _ge

    captured = {}

    def fake_start_goal_run(goal_id, **kw):
        captured["goal_id"] = goal_id
        captured.update(kw)
        return {"ok": True, "run_id": "run-goal-launch", "executor": "single"}

    monkeypatch.setattr(_ge, "start_goal_run", fake_start_goal_run)

    resp = client.post("/runs", json={"kind": "goal", "goal_id": "g-123"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json() == {"ok": True, "run_id": "run-goal-launch", "kind": "goal"}
    assert captured["goal_id"] == "g-123"


def test_create_run_goal_missing_goal_id_is_400(client):
    resp = client.post("/runs", json={"kind": "goal"})
    assert resp.status_code == 400


def test_create_run_goal_not_found_propagates_404(client, monkeypatch):
    import pathly_orchestrator.supervisor.goal_executor as _ge

    monkeypatch.setattr(
        _ge,
        "start_goal_run",
        lambda goal_id, **kw: {"ok": False, "reason": "not_found", "error": "nope"},
    )

    resp = client.post("/runs", json={"kind": "goal", "goal_id": "ghost"})
    assert resp.status_code == 404
