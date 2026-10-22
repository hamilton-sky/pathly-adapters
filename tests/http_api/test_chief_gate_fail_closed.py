"""The chief gate fails closed: a check that cannot be made is a 500, never a call let through.

Under ``TESTING`` Flask re-raises an exception instead of answering, so a test would see the
exception and not the server's answer. ``PROPAGATE_EXCEPTIONS = False`` makes the test client get
what a caller gets. In each case an operator chief starts work, a check the gate has to make fails,
and the route must not run and the session must not be charged for it. The one place the gate may
swallow an error is the response hook that gives a slot back after a 4xx: there the 4xx stands.
"""

from __future__ import annotations

import dataclasses
import inspect
import logging
import sqlite3

import pytest
from chief_bind_support import _boards_are_free, project_row, stubs
from chief_budget_support import (
    CEILING_KEY,
    LIMIT_KEY,
    flow_runs,
    runs_started,
    shown,
    start_flow,
)
from chief_gate_support import _chief, app, client, other_project, project


@pytest.fixture(autouse=True)
def _the_server_answers_instead_of_raising(app, monkeypatch):
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)


def _raises(target: str, error: Exception, monkeypatch, only=None) -> list:
    """Make ``target`` (a dotted name) raise ``error``; with ``only``, just for a call whose second
    argument is in it and the real function for any other. Returns the list of calls it refused.
    """
    module_name, name = target.rsplit(".", 1)
    module = __import__(module_name, fromlist=[name])
    real = getattr(module, name)
    refused: list = []

    def fails(*args, **kwargs):
        if only is not None and (len(args) < 2 or args[1] not in only):
            return real(*args, **kwargs)
        refused.append(args[1:] if only is not None else args)
        raise error

    monkeypatch.setattr(module, name, fails)
    return refused


# --- a setting the gate cannot read -------------------------------------------------------


@pytest.mark.parametrize("key", [CEILING_KEY, LIMIT_KEY])
def test_a_setting_that_cannot_be_read_is_a_500_and_starts_nothing(
    client, project, flow_runs, monkeypatch, key
):
    chief = _chief("operator", project)
    asked = _raises(
        "pathly_orchestrator.db.queries.app_settings.get_setting",
        sqlite3.OperationalError("database is locked"),
        monkeypatch,
        only={key},
    )

    resp = start_flow(client, chief, project)

    assert asked, "the gate never read the setting, so the test proves nothing"
    assert resp.status_code == 500, shown(resp)
    assert flow_runs.calls == []
    assert runs_started(chief) == 0


def test_the_control_without_the_failure_starts_the_run(client, project, flow_runs):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 200, shown(resp)
    assert len(flow_runs.calls) == 1 and runs_started(chief) == 1


# --- a run slot the gate cannot take ------------------------------------------------------


def test_a_slot_that_cannot_be_taken_is_a_500_and_starts_nothing(
    client, project, flow_runs, monkeypatch
):
    chief = _chief("operator", project)
    asked = _raises(
        "pathly_orchestrator.db.queries.chief_run_slots.take_run_slot",
        sqlite3.OperationalError("database is locked"),
        monkeypatch,
    )

    resp = start_flow(client, chief, project)

    assert asked
    assert resp.status_code == 500, shown(resp)
    assert flow_runs.calls == []
    assert runs_started(chief) == 0


# --- an id the gate cannot place ----------------------------------------------------------


def test_an_id_that_cannot_be_placed_is_a_500_and_the_route_does_not_run(
    client, project, stubs, monkeypatch
):
    chief = _chief("operator", project)
    goal = project_row(project, "goal")
    asked = _raises(
        "pathly_orchestrator.db.queries.placement.message_board_scope",
        sqlite3.OperationalError("database is locked"),
        monkeypatch,
    )
    body = {"goal_id": goal, "project_root": str(project)}

    resp = client.post("/comms/goals/run", json=body, headers=chief.headers)

    assert asked, "the gate never placed the goal, so the test proves nothing"
    assert resp.status_code == 500, shown(resp)
    assert stubs["goal"] == []
    assert runs_started(chief) == 0


# --- the one error the gate swallows: giving a slot back ----------------------------------


def _start_without_a_scope(client, chief, project):
    """A flow start the route refuses with a 400: the body names no scope."""
    body = {"kind": "flow", "flow": "team", "project_root": str(project)}
    return client.post("/runs", json=body, headers=chief.headers)


def test_the_control_gives_the_slot_back_after_a_4xx(client, project, flow_runs):
    chief = _chief("operator", project)

    resp = _start_without_a_scope(client, chief, project)

    assert resp.status_code == 400, shown(resp)
    assert flow_runs.calls == [] and runs_started(chief) == 0


def test_a_slot_that_cannot_be_given_back_leaves_the_4xx_standing(
    client, project, flow_runs, monkeypatch, caplog
):
    chief = _chief("operator", project)
    asked = _raises(
        "pathly_orchestrator.db.queries.chief_run_slots.give_back_run_slot",
        sqlite3.OperationalError("database is locked"),
        monkeypatch,
    )

    with caplog.at_level(logging.WARNING, logger="pathly.http"):
        resp = _start_without_a_scope(client, chief, project)

    assert asked
    assert resp.status_code == 400, shown(resp)
    assert flow_runs.calls == []
    assert runs_started(chief) == 1, "the slot stays used when it cannot be given back"
    warnings = [
        r for r in caplog.records if "could not give back a run slot" in r.getMessage()
    ]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert chief.run_id in warnings[0].getMessage()
    assert warnings[0].exc_info is not None


# --- the three copies of the default cost -------------------------------------------------


def test_the_default_cost_is_the_same_number_everywhere():
    """A flow start that states no cost runs at ``start_run``'s default and a run state carries
    that default (the dataclass field's default, since a state needs its other fields to be built);
    the gate judges the same number. Three copies of ``1.0`` that nothing kept equal would let the
    gate judge a cost the run does not have."""
    from pathly_orchestrator.http_server.blueprints.control._cost import (
        DEFAULT_FLOW_COST_USD,
    )
    from pathly_orchestrator.supervisor.api import start_run
    from pathly_orchestrator.supervisor.state import RunnerState

    parameter = inspect.signature(start_run).parameters["max_cost_usd"]
    field = {f.name: f for f in dataclasses.fields(RunnerState)}["max_cost_usd"]

    assert DEFAULT_FLOW_COST_USD == parameter.default
    assert DEFAULT_FLOW_COST_USD == field.default
