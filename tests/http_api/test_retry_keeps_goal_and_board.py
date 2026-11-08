"""chief-autopilot-round-two 21: a retried run keeps its goal, its board and its interactive mode.

``POST /runs/<id>/retry`` and ``POST /runner/retry`` rebuilt the run from the body alone, so a
retried goal run lost its ``goal_id``, a project-board run came back on ``feature`` and a headless
run came back interactive. Both now pass the ended run's ``goal_id``, ``scope_tier`` (as ``board``)
and ``interactive`` to ``start_run``, as ``resume_parked_run`` does. Both also dropped the ended
run's registry entry before validating the body, so a 400 lost the run; the entry now stays until
the body is valid.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

TOPIC = "t-retry-keeps"
RUN_ID = "run-retry-keeps"
VALID = {
    "topic": TOPIC,
    "flow": "goal-loop",
    "project_root": "/p",
    "max_iterations": 5,
    "max_cost_usd": 5,
}


@pytest.fixture()
def client(monkeypatch):
    from pathly_orchestrator.http_server import app, _rate_counters

    _rate_counters.clear()
    app.config["TESTING"] = True
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    with app.test_client() as c:
        yield c


@pytest.fixture()
def ended_run():
    """A headless goal run on the project board that ended in error."""
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic=TOPIC,
        flow="goal-loop",
        project_root="/p",
        model="",
        timeout=600,
        run_id=RUN_ID,
        status="error",
        interactive=False,
        scope_tier="project",
        goal_id="g-1",
    )
    with _lock:
        _registry[TOPIC] = state
    try:
        yield state
    finally:
        with _lock:
            _registry.pop(TOPIC, None)


def _verb(client, body):
    return client.post(f"/runs/{RUN_ID}/retry", json=body)


def _runner(client, body):
    return client.post("/runner/retry", json=body)


ROUTES = {
    "retry-verb": (_verb, "pathly_orchestrator.supervisor.api.start_run"),
    "runner-retry": (_runner, "pathly_orchestrator.supervisor.start_run"),
}


def _started(target: str):
    state = MagicMock()
    state.run_id = "run-new"
    state.public_dict.return_value = {"status": "running", "topic": TOPIC}
    return patch(target, return_value=state)


def _in_registry() -> bool:
    from pathly_orchestrator.supervisor.registry import _lock, _registry

    with _lock:
        return TOPIC in _registry


@pytest.mark.parametrize("route", list(ROUTES))
def test_a_retry_carries_the_ended_runs_goal_board_and_interactive_mode(
    client, ended_run, route
):
    send, target = ROUTES[route]

    with _started(target) as start:
        answer = send(client, VALID)

    assert answer.status_code == 200, answer.get_data(as_text=True)
    start.assert_called_once()
    kwargs = start.call_args.kwargs
    assert kwargs["goal_id"] == "g-1"
    assert kwargs["board"] == "project"
    assert kwargs["interactive"] is False


@pytest.mark.parametrize("route", list(ROUTES))
def test_a_retry_with_a_bad_body_keeps_the_ended_run_for_a_valid_retry(
    client, ended_run, route
):
    send, target = ROUTES[route]
    bad = {k: v for k, v in VALID.items() if k != "max_cost_usd"}

    with _started(target) as start:
        refused = send(client, bad)

        assert refused.status_code == 400, refused.get_data(as_text=True)
        start.assert_not_called()
        assert _in_registry()

        answer = send(client, VALID)

    assert answer.status_code == 200, answer.get_data(as_text=True)
    start.assert_called_once()
    assert start.call_args.kwargs["goal_id"] == "g-1"


def test_runner_retry_with_no_prior_state_keeps_the_defaults(client):
    from pathly_orchestrator.supervisor.registry import _lock, _registry

    with _lock:
        _registry.pop(TOPIC, None)

    with _started("pathly_orchestrator.supervisor.start_run") as start:
        answer = _runner(client, VALID)

    assert answer.status_code == 200, answer.get_data(as_text=True)
    kwargs = start.call_args.kwargs
    assert kwargs.get("goal_id", "") == ""
    assert kwargs.get("board", "") == ""
    assert kwargs.get("interactive", True) is True
