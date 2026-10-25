"""Shared setup for the build-proof 05 tests (`test_task_proof*.py`).

A real `git init` project under `tmp_path`, a run state that points at it, board tasks, and a
fake spawn that edits files the way an agent would and reports success.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from _paths import PYTHON

from pathly_orchestrator.supervisor.drain import drain_frontier
from pathly_orchestrator.supervisor.isolation import SerialIsolation

SCOPE = "proof-feat"
PLAN = "pathly/features/proof-feat/IMPLEMENTATION_PLAN.md"
SAMPLE_TEST = "def test_sample():\n    assert 1 + 1 == 2\n"
SKIPPED_TEST = (
    "import pytest\n\n\n@pytest.mark.skip\ndef test_sample():\n    assert 1 + 1 == 2\n"
)
RED_TEXT = f"""Add the greeting.

```check
$ {PYTHON} -c "import sys; print('red-marker'); sys.exit(3)"
```
"""


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def make_repo(tmp_path: Path, *, with_git: bool = True) -> Path:
    """A project with a source file, a test, a plan and a .gitignore for the server's exports."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pathly" / "features" / SCOPE).mkdir(parents=True)
    (repo / ".gitignore").write_text("BOARD.json\nEVENTS.jsonl\n*.tmp\n")
    (repo / "src" / "app.py").write_text("def greet():\n    return 'hi'\n")
    (repo / "tests" / "test_sample.py").write_text(SAMPLE_TEST)
    (repo / PLAN).write_text("# Plan\n\n- build it\n")
    if with_git:
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "test")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "initial")
    return repo


class State:
    """The slice of `RunnerState` a drain reads."""

    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "m"
    goal_id = ""

    def __init__(self, repo: Path) -> None:
        self.project_root = str(repo)
        self.topic = SCOPE
        self.storage_path = str(repo / "pathly" / "features" / SCOPE / "goals" / "g1")


def add_task(text: str, files=None) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    mid = post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="planner",
        type="task",
        text=text,
        files=files,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def row(task_id: str) -> dict:
    from pathly_orchestrator.db.connection import get_db

    found = get_db().execute("SELECT * FROM comms_messages WHERE id=?", (task_id,))
    return dict(found.fetchone())


def set_text(task_id: str, text: str) -> None:
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    conn.execute("UPDATE comms_messages SET text=? WHERE id=?", (text, task_id))
    conn.commit()


def set_app_setting(key: str, value: str) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), key, value)


def proofs(state: State) -> list[dict]:
    from pathly_orchestrator.eventlog import read_events

    return [e for e in read_events(state.storage_path) if e["type"] == "TASK_PROOF"]


def write(path: str, text: str):
    """A step that writes `text` to `path` under the repo."""

    def step(repo: Path) -> None:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    return step


class Agent:
    """A fake spawn. `steps[task_id]` holds one callable per attempt, each given the repo."""

    def __init__(self, repo: Path, steps=None, cost: float = 0.0) -> None:
        self.repo = repo
        self.steps = steps or {}
        self.cost = cost
        self.prompts: dict[str, list[str]] = {}

    def __call__(self, state, instructions, adapter, model, run_id, broadcast_fn):
        task_id, _, number = run_id.removeprefix("sched-").partition("#")
        self.prompts.setdefault(task_id, []).append(instructions)
        steps = self.steps.get(task_id, [])
        if int(number) <= len(steps):
            steps[int(number) - 1](self.repo)
        return {"outcome": "success", "cost_usd": self.cost}


def drain(state: State, agent: Agent):
    return drain_frontier(
        state, "feature", SCOPE, isolation=SerialIsolation(), spawn_fn=agent
    )
