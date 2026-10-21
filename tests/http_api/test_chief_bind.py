"""chief-agent 14: a chief reaches a run, a goal, a task or a message by id only inside its project.

The gate binds what a request names as a place (a root, a scope, a file) in ticket 08. These calls
name their target by id and carry none of those, so ``chief_bind.target_in_project`` looks the id
up: a run by the project its history, the registry or the board lock records, a goal, a task or a
message by the board and scope of its row. Every case runs the real gate and route with an
operator chief on project A and a second project B, each in its own temporary directory. A call
the gate lets through is one the route answers (``_passed``); the gate's own 403 always carries
``allowed`` (``_gated``). Where a run is placed from, a malformed id and the answer routes are in
``test_chief_bind_edges.py``.
"""

from __future__ import annotations

import pytest
from chief_bind_support import (
    DEMO,
    _boards_are_free,
    acknowledge,
    feature_dir,
    feature_row,
    is_refused,
    project_row,
    record_run,
    row,
    rows_named,
    run_call,
    shown,
    stubs,
)
from chief_cite_support import builder_headers
from chief_gate_support import (
    _chief,
    _gated,
    _passed,
    app,
    client,
    other_project,
    project,
    started,
)

# --- a run is addressed by its id in the URL ------------------------------------------------

VERBS = ["pause", "resume", "advance", "reroute", "retry", "abort", "stop"]


@pytest.mark.parametrize("action", VERBS)
def test_a_run_recorded_for_another_project_is_refused(
    client, project, other_project, action
):
    chief = _chief("operator", project)
    record_run(other_project, "run-theirs")

    resp = run_call(client, chief, project, "run-theirs", action)

    assert is_refused(resp), shown(resp)


@pytest.mark.parametrize("action", VERBS)
def test_a_run_recorded_for_the_chiefs_project_passes_the_gate(client, project, action):
    chief = _chief("operator", project)
    record_run(project, "run-ours")

    resp = run_call(client, chief, project, "run-ours", action)

    assert _passed(resp), shown(resp)


@pytest.mark.parametrize("action", VERBS)
def test_a_run_nobody_knows_is_refused(client, project, action):
    chief = _chief("operator", project)

    resp = run_call(client, chief, project, "run-nobody", action)

    assert is_refused(resp), shown(resp)


def test_a_finished_run_of_the_project_can_still_be_stopped(client, project):
    chief = _chief("operator", project)
    record_run(project, "run-done", status="done")

    resp = run_call(client, chief, project, "run-done", "stop")

    assert _passed(resp) and resp.get_json()["reason"] == "not_active", shown(resp)


def test_the_action_check_comes_before_the_id_check(client, project, other_project):
    planner = _chief("planner", project)
    record_run(other_project, "run-theirs")

    resp = run_call(client, planner, project, "run-theirs", "pause")

    assert _gated(resp) and resp.get_json()["error"] == "a planner chief may not run"


# --- a message is in the project by its board and scope -------------------------------------


def test_a_project_row_of_another_project_is_refused_and_ours_passes(
    client, project, other_project
):
    chief = _chief("operator", project)
    theirs, ours = project_row(other_project), project_row(project)

    refused = acknowledge(client, chief, theirs)
    allowed = acknowledge(client, chief, ours)

    assert is_refused(refused), shown(refused)
    assert _passed(allowed) and allowed.status_code == 200, shown(allowed)


def test_a_feature_row_is_in_the_project_that_has_the_feature_folder(
    client, project, other_project
):
    chief = _chief("operator", project)
    feature_dir(other_project)
    feature_dir(project, "ours")
    feature_dir(project, "kept", archived=True)
    theirs, ours = feature_row(DEMO), feature_row("ours")
    kept, nowhere = feature_row("kept"), feature_row("nowhere")

    assert is_refused(acknowledge(client, chief, theirs))
    assert _passed(acknowledge(client, chief, ours))
    assert _passed(acknowledge(client, chief, kept))
    assert is_refused(acknowledge(client, chief, nowhere))


def test_a_global_row_is_refused(client, project):
    chief = _chief("operator", project)

    resp = acknowledge(client, chief, row("global", "global"))

    assert is_refused(resp), shown(resp)


def test_an_unknown_message_id_passes_the_gate_and_the_route_answers_it(
    client, project
):
    chief = _chief("operator", project)
    body = {"old_id": "no-such-message", "new_id": "nor-this-one"}

    superseded = client.post("/comms/supersede", json=body, headers=chief.headers)
    acknowledged = acknowledge(client, chief, "no-such-message")

    assert _passed(superseded) and superseded.status_code == 404, shown(superseded)
    assert _passed(acknowledged) and acknowledged.status_code == 200  # a no-op


def test_supersede_is_refused_when_either_id_is_in_another_project(
    client, project, other_project
):
    chief = _chief("operator", project)
    ours, also_ours = project_row(project), project_row(project)
    theirs = project_row(other_project)

    def supersede(old_id, new_id):
        body = {"old_id": old_id, "new_id": new_id}
        return client.post("/comms/supersede", json=body, headers=chief.headers)

    assert is_refused(supersede(theirs, ours)), "old_id"
    assert is_refused(supersede(ours, theirs)), "new_id"
    both = supersede(ours, also_ours)
    assert _passed(both) and both.status_code == 200, shown(both)


# --- a goal and a task are rows of the board too --------------------------------------------

# (route, key that names the target, row type, the rest of a valid body)
TARGETS = [
    ("/comms/goals/run", "goal_id", "goal", {}),
    ("/comms/goals/stop", "goal_id", "goal", {}),
    ("/comms/goals/decompose", "goal_id", "goal", {"mode": "planner"}),
    ("/runs", "goal_id", "goal", {"kind": "goal"}),
    ("/comms/tasks/run", "message_id", "task", {}),
    ("/comms/tasks/stop", "message_id", "task", {}),
]
IDS = [f"{rule} {key}" for rule, key, _, _ in TARGETS]


def _call(client, chief, project, rule, key, target, rest):
    body = {"project_root": str(project), key: target, **rest}
    return client.post(rule, json=body, headers=chief.headers)


@pytest.mark.parametrize("rule,key,type_,rest", TARGETS, ids=IDS)
def test_a_goal_or_task_of_another_project_is_refused(
    client, project, other_project, stubs, started, rule, key, type_, rest
):
    chief = _chief("operator", project)
    theirs = project_row(other_project, type_)

    resp = _call(client, chief, project, rule, key, theirs, rest)

    assert is_refused(resp), shown(resp)
    assert stubs == {"goal": [], "decompose": [], "board": []} and started == []


@pytest.mark.parametrize("rule,key,type_,rest", TARGETS, ids=IDS)
def test_a_goal_or_task_of_the_chiefs_project_passes_the_gate(
    client, project, stubs, started, rule, key, type_, rest
):
    chief = _chief("operator", project)
    ours = project_row(project, type_)

    resp = _call(client, chief, project, rule, key, ours, rest)

    assert _passed(resp) and resp.status_code == 200, shown(resp)


@pytest.mark.parametrize("rule,key,type_,rest", TARGETS, ids=IDS)
def test_a_feature_goal_follows_the_feature_folder(
    client, project, other_project, stubs, started, rule, key, type_, rest
):
    chief = _chief("operator", project)
    feature_dir(other_project)
    theirs = feature_row(DEMO, type_)

    refused = _call(client, chief, project, rule, key, theirs, rest)
    feature_dir(project)
    allowed = _call(client, chief, project, rule, key, theirs, rest)

    assert is_refused(refused), shown(refused)
    assert _passed(allowed), shown(allowed)


@pytest.mark.parametrize("rule,key,type_,rest", TARGETS, ids=IDS)
def test_an_unknown_goal_or_task_passes_the_gate_and_the_route_answers_404(
    client, project, rule, key, type_, rest
):
    chief = _chief("operator", project)

    resp = _call(client, chief, project, rule, key, "no-such-row", rest)

    assert _passed(resp) and resp.status_code == 404, shown(resp)


def test_a_post_that_carries_the_goal_of_another_project_is_refused(
    client, project, other_project
):
    chief = _chief("operator", project)
    theirs, ours = project_row(other_project, "goal"), project_row(project, "goal")

    def post(words, **extra):
        body = {"feature": DEMO, "from": "chief", "type": "status", "text": words}
        return client.post("/comms/post", json={**body, **extra}, headers=chief.headers)

    refused = post("under their goal", goal_id=theirs)
    allowed = post("under our goal", goal_id=ours)
    others = [
        post("under no goal"),
        post("under an unknown goal", goal_id="no-such-goal"),
        post("under a null goal", goal_id=None),
        post("under a blank goal", goal_id=""),
    ]

    assert is_refused(refused), shown(refused)
    assert rows_named("under their goal") == 0
    for resp in [allowed, *others]:
        assert resp.status_code == 200, shown(resp)
    assert rows_named("under our goal") == 1


# --- anyone who is not a chief is unchanged -------------------------------------------------


def _every_call(other_project) -> list[tuple[str, dict]]:
    """A call to each route this ticket binds, naming something of project B."""
    theirs = project_row(other_project)
    goal, task = project_row(other_project, "goal"), project_row(other_project, "task")
    record_run(other_project, "run-theirs")
    return [
        ("/runs/run-theirs/stop", {}),
        ("/runs/run-theirs/pause", {}),
        ("/comms/acknowledge", {"message_id": theirs, "agent": "me"}),
        ("/comms/supersede", {"old_id": theirs, "new_id": "nobody"}),
        ("/comms/goals/stop", {"goal_id": goal}),
        ("/comms/tasks/stop", {"message_id": task}),
        ("/comms/goals/run", {"goal_id": goal}),
        ("/runs", {"kind": "goal", "goal_id": goal}),
    ]


@pytest.mark.parametrize("who", ["builder", "nobody"])
def test_a_caller_that_is_not_a_chief_is_not_held_to_a_project(
    client, project, other_project, stubs, started, who
):
    headers = builder_headers(project) if who == "builder" else {}

    for path, body in _every_call(other_project):
        resp = client.post(path, json=body, headers=headers)

        assert not _gated(resp), (who, path, shown(resp))
        assert resp.status_code < 500, (who, path, shown(resp))
