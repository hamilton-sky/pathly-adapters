"""chief-agent 08: which action a call is, and so which tier may make it.

A post is classed by its ``type``, every listed route has the action the table gives
it, and the run-control verbs split into ``run`` and ``stop``.
"""

from __future__ import annotations

import pytest

from chief_bind_support import record_run
from chief_gate_support import (
    _chief,
    _gated,
    _msg,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    project,
)

# --- which action a post is ---------------------------------------------------------------


@pytest.mark.parametrize(
    "type_,action",
    [
        ("note", "post"),
        ("status", "post"),
        ("escalation", "post"),
        (5, "post"),
        ("goal", "plan"),
        ("task", "plan"),
        ("decision", "decide"),
        ("constraint", "decide"),
        ("Decision", "decide"),
        (" constraint ", "decide"),
    ],
)
def test_a_post_is_classed_by_its_type(client, project, type_, action):
    chief = _chief("status", project)

    resp = client.post("/comms/post", json=_msg(type_), headers=chief.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] == action


# --- listed routes: the action the table gives --------------------------------------------

LISTED = [
    ("/comms/goals/decompose", "plan"),
    ("/comms/features/decompose", "plan"),
    ("/comms/project/decompose", "plan"),
    ("/comms/supersede", "decide"),
    ("/comms/directives", "decide"),
    ("/runs", "run"),
    ("/comms/goals/run", "run"),
    ("/comms/run", "run"),
    ("/comms/tasks/run", "run"),
    ("/runs/x/stop", "stop"),
    ("/comms/goals/stop", "stop"),
    ("/comms/run/stop", "stop"),
    ("/comms/tasks/stop", "stop"),
    ("/runner/agent-answer", "answer"),
    ("/comms/answer", "answer"),
]


@pytest.mark.parametrize("path,action", LISTED, ids=[p for p, _ in LISTED])
def test_a_status_chief_is_refused_each_listed_route_by_its_action(
    client, project, path, action
):
    chief = _chief("status", project)

    resp = client.post(path, json={}, headers=chief.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] == action


@pytest.mark.parametrize(
    "path,body",
    [
        ("/comms/search", {"query": "", "feature": "demo"}),
        ("/code/query", {"project_root": "OWN"}),
    ],
)
def test_a_status_chief_may_call_the_read_routes(client, project, path, body):
    chief = _chief("status", project)
    body = {k: str(project) if v == "OWN" else v for k, v in body.items()}

    resp = client.post(path, json=body, headers=chief.headers)

    assert _passed(resp)


def test_a_chief_may_read_its_own_session(client, project):
    chief = _chief("status", project)

    resp = client.get(
        "/chief/session",
        query_string={"project_root": str(project)},
        headers=chief.headers,
    )

    assert resp.status_code == 200
    assert resp.get_json()["open"] is True


# --- run control verbs --------------------------------------------------------------------

VERBS = [
    ("pause", "run"),
    ("resume", "run"),
    ("advance", "run"),
    ("reroute", "run"),
    ("retry", "run"),
    ("abort", "stop"),
    ("stop", "stop"),
]


@pytest.mark.parametrize("verb,action", VERBS)
def test_run_control_verbs_are_run_or_stop(client, project, verb, action):
    from pathly_orchestrator.supervisor.chief_tiers import actions_for

    planner = _chief("planner", project)
    resp = client.post(f"/runs/x/{verb}", json={}, headers=planner.headers)
    assert _gated(resp)
    assert resp.get_json()["action"] == action

    assert action in actions_for("operator")
    operator = _chief("operator", project)
    record_run(project, "x")  # a chief reaches only a run it can place in its project
    # `retry` starts a run in the directory its own body names, so it names the project.
    body = {"project_root": str(project)} if verb == "retry" else {}
    resp = client.post(f"/runs/x/{verb}", json=body, headers=operator.headers)
    assert _passed(resp), resp.get_data(as_text=True)


def test_an_unknown_run_verb_is_unlisted(client, project):
    operator = _chief("operator", project)

    resp = client.post("/runs/x/bogus", json={}, headers=operator.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] is None
