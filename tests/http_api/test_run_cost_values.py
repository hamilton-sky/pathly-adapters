"""chief-agent 20, B13: ``max_cost_usd`` is a finite number above 0 on every route that starts a flow.

``POST /runner/start``, ``POST /runner/retry`` and the ``retry`` verb of ``POST /runs/<id>/<action>``
accepted any int or float above 0 by ``isinstance`` and ``<= 0``. ``NaN`` passed (the comparison is
false), so the run started with a cap that is never reached; ``Infinity`` passed and is never
reached; ``true`` was read as 1; an integer too large for a float raised in ``float(...)`` and
answered 500. All three now read the key with ``control/_cost.py::as_cost``, the reading that
``POST /runs`` of a flow and the chief gate already use.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

MESSAGE = "Field 'max_cost_usd' must be a positive number"
BAD = [
    "NaN",
    "Infinity",
    "-Infinity",
    "true",
    '"5"',
    "null",
    "0",
    "-1",
    "1e999",
    "1" + "0" * 400,
]
BAD_IDS = [
    "NaN",
    "Infinity",
    "-Infinity",
    "true",
    "string",
    "null",
    "zero",
    "minus-one",
    "1e999",
    "10**400",
]
GOOD = [("5", 5.0), ("0.5", 0.5)]


@pytest.fixture()
def client(monkeypatch):
    from pathly_orchestrator.http_server import app, _rate_counters

    _rate_counters.clear()
    app.config["TESTING"] = True
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    with app.test_client() as c:
        yield c


def _body(cost: str) -> bytes:
    return (
        '{"topic": "t-cost", "flow": "team", "project_root": "/p", '
        '"max_iterations": 5, "max_cost_usd": ' + cost + "}"
    ).encode()


def _start(client, cost: str):
    return client.post(
        "/runner/start", data=_body(cost), content_type="application/json"
    )


def _retry(client, cost: str):
    return client.post(
        "/runner/retry", data=_body(cost), content_type="application/json"
    )


@pytest.fixture()
def finished_run():
    """A run in the registry that ended in error, the kind ``retry`` accepts."""
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="t-cost",
        flow="team",
        project_root="/p",
        model="",
        timeout=600,
        run_id="run-cost",
        status="error",
    )
    with _lock:
        _registry["t-cost"] = state
    try:
        yield state
    finally:
        with _lock:
            _registry.pop("t-cost", None)


def _verb(client, cost: str):
    return client.post(
        "/runs/run-cost/retry", data=_body(cost), content_type="application/json"
    )


ROUTES = {
    "runner-start": (_start, "pathly_orchestrator.supervisor.start_run"),
    "runner-retry": (_retry, "pathly_orchestrator.supervisor.start_run"),
    "retry-verb": (_verb, "pathly_orchestrator.supervisor.api.start_run"),
}


def _started(target: str) -> MagicMock:
    state = MagicMock()
    state.run_id = "run-new"
    state.public_dict.return_value = {"status": "running", "topic": "t-cost"}
    return patch(target, return_value=state)


@pytest.mark.parametrize("cost", BAD, ids=BAD_IDS)
@pytest.mark.parametrize("route", list(ROUTES))
def test_a_cost_that_is_not_a_finite_number_above_0_is_a_400_and_starts_nothing(
    client, finished_run, route, cost
):
    send, target = ROUTES[route]

    with _started(target) as start:
        answer = send(client, cost)

    assert answer.status_code == 400, answer.get_data(as_text=True)
    assert answer.get_json() == {"error": MESSAGE}
    start.assert_not_called()


@pytest.mark.parametrize("cost, expected", GOOD)
@pytest.mark.parametrize("route", list(ROUTES))
def test_a_finite_number_above_0_starts_the_run_with_that_cap(
    client, finished_run, route, cost, expected
):
    send, target = ROUTES[route]

    with _started(target) as start:
        answer = send(client, cost)

    assert answer.status_code == 200, answer.get_data(as_text=True)
    start.assert_called_once()
    cap = start.call_args.kwargs["max_cost_usd"]
    assert cap == expected and type(cap) is float


def test_a_missing_cost_is_still_the_missing_field_400(client, finished_run):
    body = b'{"topic": "t-cost", "flow": "team", "project_root": "/p", "max_iterations": 5}'

    with _started("pathly_orchestrator.supervisor.start_run") as start:
        answer = client.post(
            "/runner/start", data=body, content_type="application/json"
        )

    assert answer.status_code == 400
    assert "max_cost_usd" in answer.get_json()["error"]
    start.assert_not_called()
