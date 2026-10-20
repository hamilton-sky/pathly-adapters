"""chief-agent 08 (round 6): a flow or a skill a request names is one packaged or stored name.

``flow`` and ``skill`` are request strings that reach a file: ``fsm_ops._load_flow`` reads
``core/flows/<flow>.flow.yaml`` and ``_read_skill_body`` reads ``core/skills/<skill>.md``, both
by joining the string onto a packaged folder (an absolute string replaces the folder). A goal run
of the ``team`` executor also makes ``pathly/features/<scope>/<flow>/<slug>`` of its ``flow``
before it checks the flow exists. So a chief that names a path can read another project's file
into an agent's prompt, open its flow file, or create folders in its tree.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from chief_gate_support import (
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)

MARKER = "PLANTED-IN-ANOTHER-PROJECT"

# Four `..` climb from `<project>/pathly/features/demo/` to the folder the projects share.
TRAVERSING = "../../../../proj-b/planted"
NOT_NAMES = [
    TRAVERSING,
    "OTHER/planted",
    "OTHER",
    "..",
    "a/b",
    "a\\b",
    "c:x",
    "x\0y",
]


def _goal(client) -> str:
    resp = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "human",
            "type": "goal",
            "text": "Ship export",
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["message_id"]


def _run_goal(client, goal, project, flow, headers=None):
    return client.post(
        "/comms/goals/run",
        json={
            "goal_id": goal,
            "executor": "team",
            "flow": flow,
            "project_root": str(project),
        },
        headers=headers or {},
    )


@pytest.fixture()
def team_runs(monkeypatch):
    """Record the FSM runs the goal route starts, instead of starting any."""
    calls: list[dict] = []

    def fake_start_run(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(run_id="run-1")

    monkeypatch.setattr("pathly_orchestrator.supervisor.api.start_run", fake_start_run)
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.goal_executor._reset_fsm_state_for_flow",
        lambda *a, **k: None,
    )
    # A started run keeps its feature claimed until its `on_done` fires, which a fake never does.
    monkeypatch.setattr("pathly_orchestrator.supervisor.file_claims._claims", {})
    return calls


# --- flow on a goal run -------------------------------------------------------------------


@pytest.mark.parametrize("flow", NOT_NAMES)
def test_a_chief_cannot_name_a_flow_on_a_goal_run(
    client, project, other_project, team_runs, flow
):
    chief = _chief("operator", project)
    goal = _goal(client)
    flow = flow.replace("OTHER", str(other_project))

    resp = _run_goal(client, goal, project, flow, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "flow" in resp.get_json()["error"]
    assert team_runs == []
    assert list(other_project.rglob("*")) == []


@pytest.mark.parametrize("flow", [f for f in NOT_NAMES if "\0" not in f] + ["nonesuch"])
def test_the_goal_run_route_makes_no_folder_for_a_flow_that_is_not_a_flow(
    client, project, other_project, team_runs, flow
):
    """The route itself, with no token: the folder of a run is made only for a flow that
    exists, and the flow is one name.
    """
    goal = _goal(client)
    flow = flow.replace("OTHER", str(other_project))

    resp = _run_goal(client, goal, project, flow)

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert resp.get_json()["reason"] == "unknown_flow"
    assert team_runs == []
    assert list(other_project.rglob("*")) == []
    assert not (project / "pathly").exists()


def test_the_goal_run_route_still_makes_the_folder_of_a_packaged_flow(
    client, project, team_runs
):
    goal = _goal(client)

    resp = _run_goal(client, goal, project, "team-build")

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert len(team_runs) == 1
    assert (project / "pathly" / "features" / "demo" / "goals").is_dir()


# --- flow on a flow run -------------------------------------------------------------------


def test_a_chief_cannot_start_a_flow_named_by_a_path(
    client, project, other_project, team_runs
):
    (other_project / "planted.flow.yaml").write_text("states: [A, DONE]\n")
    chief = _chief("operator", project)

    resp = client.post(
        "/runs",
        json={
            "kind": "flow",
            "scope": "demo",
            "flow": str(other_project / "planted"),
            "project_root": str(project),
        },
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "flow" in resp.get_json()["error"]
    assert team_runs == []


def test_a_flow_is_read_only_from_the_packaged_flows_or_the_database(other_project):
    """``_load_flow`` joins the name onto the packaged folder: a path must not leave it."""
    from pathly_orchestrator.fsm_ops import _load_flow

    (other_project / "planted.flow.yaml").write_text("states: [A, DONE]\n")

    with pytest.raises(FileNotFoundError):
        _load_flow(str(other_project / "planted"))
    with pytest.raises(FileNotFoundError):
        _load_flow("../" * 40 + str(other_project / "planted").lstrip("/"))


def test_a_packaged_flow_still_loads():
    from pathly_orchestrator.fsm_ops import _load_flow

    assert "BUILDING" in _load_flow("team-build")["states"]


# --- skill on a board run -----------------------------------------------------------------


def _wait_for_the_board_run(board: str, scope: str) -> None:
    from pathly_orchestrator.supervisor import board_lock

    deadline = time.monotonic() + 10
    while board_lock.holder(board, scope) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert board_lock.holder(board, scope) is None, "the board run never finished"


@pytest.fixture()
def spawned(monkeypatch):
    """Spawn no agent; keep what each board run would have been handed."""
    handed: list[str] = []

    def fake_spawn(**kwargs):
        handed.append(repr(kwargs))
        return {"result": "done"}

    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.board_run._default_spawn", fake_spawn
    )
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.sse._broadcast_runner", lambda *a, **k: None
    )
    yield handed
    # A run a failing test did not wait for must not hold the board into the next test.
    _wait_for_the_board_run("feature", "demo")


def _run_with_skill(client, project, skill, headers=None):
    return client.post(
        "/comms/run",
        json={"scope": "demo", "skill": skill, "project_root": str(project)},
        headers=headers or {},
    )


def test_a_chief_cannot_name_a_skill_that_is_a_path(
    client, project, other_project, spawned
):
    (other_project / "planted.md").write_text(MARKER + "\n")
    chief = _chief("operator", project)

    resp = _run_with_skill(
        client, project, str(other_project / "planted"), chief.headers
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "skill" in resp.get_json()["error"]
    assert spawned == []


@pytest.mark.parametrize("how", ["absolute", "climbing"])
def test_the_run_route_hands_an_agent_no_file_outside_the_skills(
    client, project, other_project, spawned, how
):
    """The route itself, with no token: ``skill`` joins onto the packaged skills folder."""
    (other_project / "planted.md").write_text(MARKER + "\n")
    target = str(other_project / "planted")
    skill = target if how == "absolute" else "../" * 40 + target.lstrip("/")

    resp = _run_with_skill(client, project, skill)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    _wait_for_the_board_run("feature", "demo")

    assert spawned, "the run should have been started"
    assert MARKER not in "".join(spawned)


def test_a_packaged_skill_is_still_composed_into_the_prompt(client, project, spawned):
    resp = _run_with_skill(client, project, "planning/evaluate")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    _wait_for_the_board_run("feature", "demo")

    assert spawned and "BOARD_EVAL" in "".join(spawned)


def test_a_chief_may_name_a_packaged_skill(client, project, spawned):
    chief = _chief("operator", project)

    resp = _run_with_skill(client, project, "planning/evaluate", chief.headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    _wait_for_the_board_run("feature", "demo")
