"""Shared fixtures for the HQ operator tests (pathly/features/local-operator).

Imported as ``from _operator_env import ...`` (the install_skills/_install_env
pattern). The DB is auto-isolated per test by tests/conftest.py.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

BOARD = "opboard"
ALL_ACTIONS = [
    "pause_run",
    "resume_run",
    "retry_run",
    "stop_run",
    "run_goal",
    "plan_goal",
    "post_note",
    "diagram_artifact",
    "add_diagram_to_board",
]


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def db():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def make_all_available(client) -> None:
    resp = client.put("/hq/actions/available", json={"actions": ALL_ACTIONS})
    assert resp.status_code == 200


def seed_goal(text: str = "Ship the gateway", executor: str = "single") -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        db(),
        board="feature",
        scope=BOARD,
        from_agent="planner",
        type="goal",
        text=text,
        executor=executor,
    )


def seed_artifact(path: str, title: str = "Gateway design") -> str:
    """An artifact row on BOARD pointing at *path*; returns the artifact id."""
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact

    conn = db()
    message_id = post_message(
        conn,
        board="feature",
        scope=BOARD,
        from_agent="architect",
        type="status",
        text=title,
    )
    return insert_artifact(conn, message_id, path=path, type="design", title=title)


@contextmanager
def registry_run(run_id: str, status: str, flow: str = "team", topic: str = ""):
    """A RunnerState in the live registry for the duration of the block."""
    from pathly_orchestrator.supervisor.registry import _lock, _registry
    from pathly_orchestrator.supervisor.state import RunnerState

    topic = topic or f"t-{run_id}"
    state = RunnerState(
        topic=topic,
        flow=flow,
        project_root="/proj",
        model="",
        timeout=600,
        run_id=run_id,
        status=status,
        current_state="BUILDING",
    )
    with _lock:
        _registry[topic] = state
    try:
        yield state
    finally:
        with _lock:
            _registry.pop(topic, None)


def check(client, proposals: list[dict], enabled: list[str] | None = None) -> dict:
    resp = client.post(
        "/hq/actions/check",
        json={
            "board": BOARD,
            "project_root": "/proj",
            "enabled_actions": enabled if enabled is not None else ALL_ACTIONS[:8],
            "proposals": proposals,
        },
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def run_card(client, card: dict) -> dict:
    resp = client.post(
        "/hq/actions/run",
        json={
            "board": BOARD,
            "project_root": "/proj",
            "name": card["name"],
            "args": card["args"],
            "fingerprint": card["fingerprint"],
        },
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def audit_rows() -> list:
    return (
        db()
        .execute(
            "SELECT text, type, author_source FROM comms_messages "
            "WHERE from_agent='local-operator' AND scope=? ORDER BY ts",
            (BOARD,),
        )
        .fetchall()
    )
