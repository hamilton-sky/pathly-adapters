"""chief-agent 08: a route that falls back to another project must be told which.

A run, decompose or read route whose ``project_root`` is optional (the server's working
directory, or every project, is the fallback) refuses a chief that names none, and
``project_root`` counts only where the view reads it (body for a POST, query string for
a GET).
"""

from __future__ import annotations

import pytest

from chief_bind_support import record_run
from chief_gate_support import (
    NAMES_A_PROJECT,
    NAMES_A_PROJECT_READS,
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
    started,
)
from chief_session_guard import _no_watcher_outlives_its_test


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT, ids=[p for p, _ in NAMES_A_PROJECT]
)
@pytest.mark.parametrize("value", ["absent", None, "", 0, []])
def test_a_chief_that_names_no_project_is_refused_on_a_run_route(
    client, project, path, body, value
):
    chief = _chief("operator", project)
    sent = dict(body) if value == "absent" else {**body, "project_root": value}

    resp = client.post(path, json=sent, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT, ids=[p for p, _ in NAMES_A_PROJECT]
)
def test_a_chief_that_names_its_project_passes_a_run_route(
    client, project, started, path, body
):
    # ``started`` stands in for start_board_run: the real one spawns on a thread that waits
    # 30 seconds for a spawn host and so outlives the test.
    chief = _chief("operator", project)

    resp = client.post(
        path, json={**body, "project_root": str(project)}, headers=chief.headers
    )

    assert _passed(resp), resp.get_data(as_text=True)


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT[4:], ids=[p for p, _ in NAMES_A_PROJECT[4:]]
)
def test_a_planner_that_names_no_project_is_refused_on_a_decompose_route(
    client, project, path, body
):
    chief = _chief("planner", project)

    resp = client.post(path, json=body, headers=chief.headers)

    assert _gated(resp)
    assert "project_root" in resp.get_json()["error"]


def test_a_project_named_only_in_the_query_string_does_not_count(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs?project_root=" + str(project),
        json={"kind": "bogus"},
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


# --- round 3: what every route reads as a project, board, scope or file -------------------
#
# Two rounds each left one hole of the same class: a request field a route reads as a project,
# a board or a scope that the gate did not look at (a query-string `project_root` on a route that
# reads the body, `/comms/search`'s `feature` fallback, `GET /comms?board=project&scope=...`, an
# absolute `/code/query` target). `chief_fields.ROUTE_FIELDS` now says, per route the chief can
# reach, which fields it reads that way, and `chief_project` applies that one table to the body
# and the query string.


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT, ids=[p for p, _ in NAMES_A_PROJECT]
)
def test_a_project_named_only_in_the_query_string_does_not_name_it(
    client, project, path, body
):
    chief = _chief("operator", project)

    resp = client.post(
        path,
        query_string={"project_root": str(project)},
        json=body,
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


def test_the_route_reads_the_body_so_the_body_must_carry_the_root(
    client, project, started
):
    chief = _chief("operator", project)
    spec = {"kind": "single", "board": "feature", "scope": "demo"}

    query_only = client.post(
        "/runs",
        query_string={"project_root": str(project)},
        json=spec,
        headers=chief.headers,
    )
    in_body = client.post(
        "/runs", json={**spec, "project_root": str(project)}, headers=chief.headers
    )

    assert _gated(query_only)
    assert in_body.status_code == 200, in_body.get_data(as_text=True)
    assert [c["project_root"] for c in started] == [str(project)]


@pytest.mark.parametrize("rule", NAMES_A_PROJECT_READS)
def test_a_read_that_falls_back_to_another_project_must_name_the_chiefs(
    client, project, other_project, rule
):
    path = rule.replace("<feature>", "x").replace("<artifact_id>", "x")
    chief = _chief("status", project)

    unnamed = client.get(path, headers=chief.headers)
    other = client.get(
        path, query_string={"project_root": str(other_project)}, headers=chief.headers
    )
    own = client.get(
        path, query_string={"project_root": str(project)}, headers=chief.headers
    )

    assert _gated(unnamed), (unnamed.status_code, unnamed.get_data(as_text=True)[:200])
    assert "project_root" in unnamed.get_json()["error"]
    assert _gated(other)
    assert _passed(own), (own.status_code, own.get_data(as_text=True)[:200])


def test_a_read_that_filters_by_project_is_bound_by_its_query_string(
    client, project, other_project
):
    chief = _chief("status", project)

    for path in ("/runs", "/api/features", "/skills/prompts", "/comms/permissions"):
        other = client.get(
            path,
            query_string={"project_root": str(other_project)},
            headers=chief.headers,
        )
        own = client.get(
            path, query_string={"project_root": str(project)}, headers=chief.headers
        )
        assert _gated(other), path
        assert _passed(own), (path, own.get_data(as_text=True)[:200])


# --- round 4: a name or a root a route takes as given -------------------------------------
#
# The earlier rounds bound the fields the views read as a project. The review of round 3 found
# three places where a route does more with a field than the table said: `retry` starts a run in
# the directory its own body names (and takes an empty one), `/comms/features/decompose` joins the
# `feature` into a path, and `/telemetry/trends` with no feature sums every project.

RETRY_FIELDS = {"flow": "team", "max_iterations": 3, "max_cost_usd": 1}


@pytest.fixture()
def finished_run(monkeypatch, project):
    """A finished run of the registry (the chief's project's), and a record of the runs a retry
    starts."""
    from types import SimpleNamespace

    from pathly_orchestrator.supervisor import registry

    started_runs: list[dict] = []

    def fake_start_run(**kwargs):
        started_runs.append(kwargs)
        return SimpleNamespace(run_id="run-new-1")

    monkeypatch.setitem(
        registry._registry,
        "retry-topic",
        SimpleNamespace(run_id="run-own-1", status="done", project_root=str(project)),
    )
    monkeypatch.setattr("pathly_orchestrator.supervisor.api.start_run", fake_start_run)
    return started_runs


@pytest.mark.parametrize("value", ["absent", "", None, 0, False, [], {}], ids=repr)
def test_a_retry_that_names_no_project_is_refused(client, project, finished_run, value):
    chief = _chief("operator", project)
    body = dict(RETRY_FIELDS)
    if value != "absent":
        body["project_root"] = value

    resp = client.post("/runs/run-own-1/retry", json=body, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]
    assert finished_run == []


def test_a_retry_that_names_its_own_project_starts_the_run_there(
    client, project, finished_run
):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs/run-own-1/retry",
        json={**RETRY_FIELDS, "project_root": str(project)},
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert [c["project_root"] for c in finished_run] == [str(project)]


def test_a_retry_in_another_project_is_refused(
    client, project, other_project, finished_run
):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs/run-own-1/retry",
        json={**RETRY_FIELDS, "project_root": str(other_project)},
        headers=chief.headers,
    )

    assert _gated(resp)
    assert finished_run == []


@pytest.mark.parametrize("verb", ["pause", "resume", "advance", "reroute"])
def test_the_other_run_verbs_need_no_root(client, project, verb):
    """They act on a run's own state, not on a directory the body names."""
    chief = _chief("operator", project)
    record_run(project, "x")  # a chief reaches only a run it can place in its project

    resp = client.post(f"/runs/x/{verb}", json={}, headers=chief.headers)

    assert _passed(resp), resp.get_data(as_text=True)
