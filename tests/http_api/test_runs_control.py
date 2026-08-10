"""POST /runs/<run_id>/stop — the run_id-addressed stop (unified-control-plane).

Resolves a run_id to its live stop path: a registry RunnerState → abort_run (FSM flows), a
board-lock holder → board stop (board single/evaluator, goal single/loop), else not_active.
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
