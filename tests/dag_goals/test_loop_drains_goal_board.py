"""chief-autopilot 14: a loop goal's tasks drain from the goal's own board.

A chief posts its goals and tasks on the project board (``board: project``, ``scope: <project
root>``). A ``loop`` goal runs the ``goal-loop`` flow, whose ``DRAINING`` state hands the frontier
to ``supervisor/fan_out.py``. The drain must ask for ready tasks on the goal's own board, so the
project-board goal's task is claimed as ``sched-<task>#1``; a feature-board loop goal still drains
as before.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
    (root / ".gitignore").write_text("pathly/**/BOARD.json\nEVENTS.jsonl\n")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _post(board: str, scope: str, kind: str, text: str, goal_id=None) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    conn = _conn()
    mid = post_message(
        conn,
        board=board,
        scope=scope,
        from_agent="chief",
        type=kind,
        text=text,
        goal_id=goal_id,
    )
    if kind == "task":
        conn.execute(
            "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
            (json.dumps([]), mid),
        )
        conn.commit()
    return mid


def _row(tid: str) -> dict:
    row = _conn().execute("SELECT * FROM comms_messages WHERE id=?", (tid,))
    return dict(row.fetchone())


def _run_loop_goal(monkeypatch, root: Path, goal_id: str) -> list:
    """Start the goal as ``executor: loop`` through the real goal executor; return the spawns."""
    from pathly_orchestrator import fsm_http_client as fhc
    from pathly_orchestrator import supervisor
    from pathly_orchestrator.db.queries.app_settings import set_setting
    from pathly_orchestrator.fsm_ops import next_action
    from pathly_orchestrator.fsm_ops_complete import complete_stage
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    set_setting(_conn(), "code_context.backend", "off")
    monkeypatch.setattr(fhc, "next_action", next_action)
    monkeypatch.setattr(fhc, "complete_stage", complete_stage)

    spawns: list = []

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **_):
        spawns.append(run_id)
        return {"cost_usd": 0.0, "session_id": None}

    monkeypatch.setattr(supervisor, "_run_stage_via_terminal", fake_spawn)
    finished = threading.Event()

    started = start_goal_run(
        goal_id,
        executor_override="loop",
        project_root=str(root),
        broadcast_fn=lambda t, p: None,
        on_done=lambda *a: finished.set(),
    )
    assert started.get("ok"), started
    run_id = started["run_id"]
    try:
        assert finished.wait(120), f"run did not finish: {spawns}"
    finally:
        with supervisor._lock:
            topics = [t for t, s in supervisor._registry.items() if s.run_id == run_id]
        for topic in topics:
            if not finished.is_set():
                supervisor.abort_run(topic)
                finished.wait(30)
            with supervisor._lock:
                supervisor._registry.pop(topic, None)
    return spawns


def test_a_loop_goal_on_the_project_board_claims_its_ready_task(tmp_path, monkeypatch):
    root = _project(tmp_path)
    scope = str(root)
    goal_id = _post("project", scope, "goal", "Goal: the chief's loop goal")
    task = _post("project", scope, "task", "Build the parser.", goal_id=goal_id)

    spawns = _run_loop_goal(monkeypatch, root, goal_id)

    assert spawns and spawns[0] == f"sched-{task}#1", spawns
    assert _row(task)["task_status"] == "done"


def test_a_loop_goal_on_a_feature_board_still_drains(tmp_path, monkeypatch):
    root = _project(tmp_path)
    feature = "feat-loop-board"
    (root / "pathly" / "features" / feature).mkdir(parents=True)
    goal_id = _post("feature", feature, "goal", "Goal: a feature loop goal")
    task = _post("feature", feature, "task", "Build the printer.", goal_id=goal_id)

    spawns = _run_loop_goal(monkeypatch, root, goal_id)

    assert spawns and spawns[0] == f"sched-{task}#1", spawns
    assert _row(task)["task_status"] == "done"
