"""Shared setup for the build-proof acceptance test (``test_build_proof_acceptance.py``).

A real ``git init`` project, a goal with board tasks, and one scripted fake agent standing in for
``supervisor._run_stage_via_terminal``. The real ``team-build`` and ``goal-loop`` flows run
through ``supervisor.start_run`` with the real ``fsm_ops`` (``fhc.next_action`` and
``fhc.complete_stage`` patched to the in-process functions), so every gate, the spawn windows and
the task proof run for real; only the model is replaced.
"""

from __future__ import annotations

import re
import subprocess
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

import pytest

from pathly_orchestrator import eventlog, supervisor
from pathly_orchestrator import fsm_http_client as fhc
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_tasks import (
    claim_task,
    complete_task,
    get_ready_tasks,
)
from pathly_orchestrator.fsm_ops import next_action
from pathly_orchestrator.fsm_ops_complete import complete_stage
from tests._python import python_command

APP = "def add(a, b):\n    return a + b\n"
APP_V2 = APP + "\n\ndef answer():\n    return 42\n"
TEST_APP = "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
# What a builder does to get green by weakening the bar.
SKIPPED_TEST = (
    "import pytest\nfrom app import add\n\n\n"
    "@pytest.mark.skip\ndef test_add():\n    assert add(1, 2) == 3\n"
)
GITIGNORE = "pathly/**/BOARD.json\nEVENTS.jsonl\n"
STORIES = "# Stories\n- adds things\n"
BUILDER_SUMMARY = "BUILDER-SELF-REPORT-MARKER"
DEBUG_HEADING = "## Root-cause debugging"
DEADLINE = 300

_FEEDBACK_RUN = re.compile(r"-fb[0-9]+-")
_TASK_RUN = re.compile(r"sched-(?P<task>[^#]+)#(?P<attempt>[0-9]+)")


def sh(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def check_block(command: str) -> str:
    return "\n\n```check\n$ %s\n```\n" % command


def appending(log: Path) -> str:
    """A check that exits 0 and appends one character to ``log`` (outside the repo)."""
    return python_command("open('%s', 'a').write('x')" % log.as_posix())


class Projects:
    """Makes a ``git init`` project per scenario, so several runs in one test never share a tree."""

    def __init__(self, tmp_path: Path, monkeypatch) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch

    def new(self, name: str) -> Path:
        """A project with one commit; the board plan is written after it (uncommitted)."""
        root = self.tmp_path / name
        root.mkdir()
        sh(root, "init", "-q")
        sh(root, "config", "user.email", "test@example.com")
        sh(root, "config", "user.name", "test")
        for rel, text in (
            ("src/app.py", APP),
            ("tests/test_app.py", TEST_APP),
            (".gitignore", GITIGNORE),
        ):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        sh(root, "add", "-A")
        sh(root, "commit", "-q", "-m", "initial")
        return root


@pytest.fixture
def projects(tmp_path: Path, monkeypatch) -> Projects:
    # build_prompt would otherwise start a code-intel tool through the `auto` backend.
    set_setting(get_db(), "code_context.backend", "off")
    monkeypatch.setattr(fhc, "next_action", next_action)
    monkeypatch.setattr(fhc, "complete_stage", complete_stage)
    return Projects(tmp_path, monkeypatch)


@contextmanager
def settings(values: dict[str, str]) -> Iterator[None]:
    """App settings for one run; cleared afterwards (an empty value means not configured)."""
    for key, value in values.items():
        set_setting(get_db(), key, value)
    try:
        yield
    finally:
        for key in values:
            set_setting(get_db(), key, "")


@dataclass
class Spawn:
    """One call of the fake agent. ``kind`` is ``stage``, ``feedback`` or ``task``."""

    run_id: str
    kind: str
    state: str
    instructions: str
    session: Optional[str]
    feedback: list[str]

    @property
    def task_id(self) -> str:
        found = _TASK_RUN.fullmatch(self.run_id)
        return found.group("task") if found else ""

    @property
    def attempt(self) -> int:
        found = _TASK_RUN.fullmatch(self.run_id)
        return int(found.group("attempt")) if found else 0

    @property
    def returned_session(self) -> str:
        return "%s-sess" % self.run_id


@dataclass
class Harness:
    """The scripted agent: records every spawn, then lets ``script(h, spawn)`` act on the project.

    ``script`` returns the summary the agent reports in its ``AGENT_DONE`` (or ``None`` for a
    default one). A spawn the script does nothing for is a no-op success.
    """

    root: Path
    topic: str
    script: Callable[["Harness", Spawn], Optional[str]] = lambda h, s: None
    spawns: list[Spawn] = field(default_factory=list)
    seen: dict[str, str] = field(default_factory=dict)
    broadcasts: list[dict] = field(default_factory=list)
    goal_id: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def storage(self) -> Path:
        return self.root / "pathly" / "features" / self.topic

    def __call__(
        self,
        state,
        instructions,
        adapter,
        model,
        run_id,
        broadcast_fn,
        session=None,
        autonomy=True,
        **_,
    ):
        feedback_dir = self.storage / "feedback"
        pending = sorted(p.name for p in feedback_dir.glob("*.md"))
        kind = "task" if run_id.startswith("sched-") else "stage"
        if _FEEDBACK_RUN.search(run_id):
            kind = "feedback"
        spawn = Spawn(run_id, kind, state.current_state, instructions, session, pending)
        with self._lock:
            self.spawns.append(spawn)
        summary = self.script(self, spawn) or "done %s" % run_id
        self.agent_done(spawn, summary)
        return {"cost_usd": 0.0, "session_id": spawn.returned_session}

    def agent_done(self, spawn: Spawn, summary: str) -> None:
        eventlog.append_event(
            str(self.storage),
            {
                "type": "AGENT_DONE",
                "agent": "builder" if spawn.kind != "stage" else spawn.state.lower(),
                "conversation": 1,
                "run_id": spawn.run_id,
                "summary": summary,
                "outcome": "success",
            },
        )

    # ── what an agent does to the project and the board ─────────────────────────────────────
    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def claim(self) -> list[str]:
        """Claim every ready task the way ``team/build`` does (run id ``build``)."""
        conn = get_db()
        ready = get_ready_tasks(conn, ["feature"], [self.topic], self.goal_id or None)
        ids = [t["id"] for t in ready]
        for task_id in ids:
            assert claim_task(conn, task_id, "build")
        return ids

    def finish(self, ids: list[str]) -> None:
        for task_id in ids:
            complete_task(get_db(), task_id)

    def review_passes(self) -> None:
        (self.storage / "REVIEW.md").write_text(
            "RESULT: PASS\nReviewed the diff against the task: clean.\n",
            encoding="utf-8",
        )

    def feedback_text(self, name: str) -> str:
        return (self.storage / "feedback" / name).read_text(encoding="utf-8")

    def broadcast(self, topic: str, payload: dict) -> None:
        self.broadcasts.append(payload)

    # ── what happened ───────────────────────────────────────────────────────────────────────
    def events(self, kind: str) -> list[dict]:
        return [e for e in eventlog.read_events(str(self.storage)) if e["type"] == kind]


def add_goal(topic: str) -> str:
    return post_message(
        get_db(),
        board="feature",
        scope=topic,
        from_agent="architect",
        type="goal",
        text="Goal: %s" % topic,
    )


def add_task(
    topic: str,
    goal_id: str,
    text: str,
    *,
    files: Optional[list[str]] = None,
    depends_on: Optional[list[str]] = None,
) -> str:
    return post_message(
        get_db(),
        board="feature",
        scope=topic,
        from_agent="planner",
        type="task",
        text=text,
        goal_id=goal_id,
        files=files,
        depends_on=depends_on,
    )


def task_row(task_id: str) -> dict:
    row = get_db().execute("SELECT * FROM comms_messages WHERE id=?", (task_id,))
    return dict(row.fetchone())


def board_posts(topic: str, kind: str) -> list[dict]:
    rows = get_db().execute(
        "SELECT * FROM comms_messages WHERE scope=? AND type=? AND deleted_at IS NULL",
        (topic, kind),
    )
    return [dict(r) for r in rows.fetchall()]


def make_harness(projects: Projects, topic: str, script: Callable) -> Harness:
    """The harness for one run in a new project, with the board plan written (uncommitted)."""
    h = Harness(projects.new(topic), topic, script)
    h.storage.mkdir(parents=True, exist_ok=True)
    h.write("pathly/features/%s/USER_STORIES.md" % topic, STORIES)
    h.write(
        "pathly/features/%s/IMPLEMENTATION_PLAN.md" % topic, "# Plan\n- `src/app.py`\n"
    )
    h.goal_id = add_goal(topic)
    return h


def drive(projects: Projects, h: Harness, flow: str) -> supervisor.RunnerState:
    """Start the real run and wait for its supervisor thread to finish (``on_done`` fired)."""
    projects.monkeypatch.setattr(supervisor, "_run_stage_via_terminal", h)
    finished = threading.Event()
    state = supervisor.start_run(
        topic=h.topic,
        flow=flow,
        project_root=str(h.root),
        max_iterations=30,
        max_cost_usd=10.0,
        interactive=False,
        goal_id=h.goal_id,
        broadcast_fn=h.broadcast,
        on_done=lambda run_id, result: finished.set(),
    )
    try:
        if not finished.wait(DEADLINE):
            raise AssertionError(
                "run did not finish: status=%s state=%s spawns=%s"
                % (state.status, state.current_state, [s.run_id for s in h.spawns])
            )
    finally:
        if not finished.is_set():
            supervisor.abort_run(h.topic)
            finished.wait(30)
        with supervisor._lock:
            supervisor._registry.pop(h.topic, None)
    return state
