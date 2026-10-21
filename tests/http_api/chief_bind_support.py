"""Helpers of the id-binding tests (chief-agent 14).

Two projects in temporary directories, a board with something on it for each, and the runs a
chief may be pointed at. A row is posted straight through the query (as an agent or the person
would post it, with no chief token), so the test controls its board and scope. ``stubs`` keeps the
routes that start an agent from starting one: it records the goal runs, goal decomposes and board
runs the routes would have started.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from chief_cite_support import db
from chief_gate_support import _gated

DEMO = "demo"
NOT_IN_PROJECT = "not in this chief's project"


def is_refused(resp) -> bool:
    """True when this is the chief gate's 403 for an id that is not in the chief's project."""
    return _gated(resp) and resp.get_json()["error"] == NOT_IN_PROJECT


def shown(resp) -> str:
    """A response as one line, for the message of a failed assertion."""
    return f"{resp.status_code} {resp.get_data(as_text=True)[:200]}"


def run_call(client, chief, project, run_id, action):
    """``POST /runs/<run_id>/<action>`` with the keys its entry lists (a stop takes only the
    root; ``retry`` is the one verb that must name it)."""
    body = {"project_root": str(project)}
    if action != "stop":
        body.update(adapter="claude", flow="team")
    return client.post(f"/runs/{run_id}/{action}", json=body, headers=chief.headers)


def acknowledge(client, chief, message_id):
    body = {"message_id": message_id, "agent": "chief"}
    return client.post("/comms/acknowledge", json=body, headers=chief.headers)


def feature_dir(root: Path, name: str = DEMO, archived: bool = False) -> Path:
    """The folder a feature of ``root`` lives in (live, or under ``features/.archive``)."""
    base = root / "pathly" / "features"
    folder = (base / ".archive" / name) if archived else (base / name)
    folder.mkdir(parents=True)
    return folder


def row(board: str, scope: str, type_: str = "decision", **extra) -> str:
    """A board row posted with no token; returns its id."""
    from pathly_orchestrator.db.queries.comms_messages import post_message

    return post_message(
        db(),
        board=board,
        scope=scope,
        from_agent="human",
        type=type_,
        text="a row for the binding test",
        **extra,
    )


def project_row(root: Path, type_: str = "decision", **extra) -> str:
    """A row on the project board of ``root`` (whose scope is the root itself)."""
    return row("project", str(root), type_, **extra)


def feature_row(scope: str = DEMO, type_: str = "decision", **extra) -> str:
    return row("feature", scope, type_, **extra)


def record_run(root: Path | str, run_id: str, status: str = "running") -> str:
    """A run the history knows (the identity every spawn writes before its process starts)."""
    from pathly_orchestrator.db.queries.run_history import upsert_run

    upsert_run(db(), str(root), DEMO, run_id, status)
    return run_id


def hold(board: str, scope: str, run_id: str) -> None:
    """Make ``run_id`` the holder of a board: a run that only the board lock knows."""
    from pathly_orchestrator.supervisor import board_lock

    assert board_lock.acquire(board, scope, run_id)


def rows_named(text: str) -> int:
    """How many rows carry ``text``: a post the gate refused stores nothing."""
    found = db().execute("SELECT COUNT(*) FROM comms_messages WHERE text = ?", (text,))
    return found.fetchone()[0]


@pytest.fixture(autouse=True)
def _boards_are_free():
    """A board lock a test takes is given back, so no test sees another's run."""
    from pathly_orchestrator.supervisor import board_lock

    with board_lock._lock:
        board_lock._held.clear()
    yield
    with board_lock._lock:
        board_lock._held.clear()


@pytest.fixture()
def stubs(monkeypatch) -> dict[str, list]:
    """The agents the routes would start, replaced by records of the call."""
    from pathly_orchestrator.supervisor import board_run, goal_executor, goal_run

    started: dict[str, list] = {"goal": [], "decompose": [], "board": []}

    def goal(goal_id, **kwargs):
        started["goal"].append(goal_id)
        return {"ok": True, "run_id": "run-goal"}

    def decompose(goal_id, **kwargs):
        started["decompose"].append(goal_id)
        return {"ok": True, "run_id": "run-decompose"}

    def board(*args, **kwargs):
        started["board"].append(args)
        return {"ok": True, "run_id": "run-board"}

    # `/comms/goals/run` and `/decompose` take the names from `goal_run`; `POST /runs` from
    # `goal_executor`; `/comms/tasks/run` starts a board run.
    monkeypatch.setattr(goal_run, "start_goal_run", goal)
    monkeypatch.setattr(goal_executor, "start_goal_run", goal)
    monkeypatch.setattr(goal_run, "start_goal_decompose", decompose)
    monkeypatch.setattr(board_run, "start_board_run", board)
    return started
