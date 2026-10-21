"""Helpers of the cited-answer tests (chief-agent 10).

``Asker`` is a run of the registry whose stage asked its human a question: a real
``_await_agent_question`` waits in a thread, as it does in production. ``Session`` is a chief
session the hook has already recorded the style prompt for, so the next thing a test ``type``s is
a ``human`` message, the way the hook stores what the person submits in the tab. The ``ask``
fixture is imported by name into each test file that uses it.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from chief_gate_support import Chief, _chief

# One message with the characters that break a shell-quoted JSON argument.
TEXT = 'use CSV, it\'s what "ops" asked for\nand keep the header row'

NOT_CITED = "cite a human message from this chief session"
CITE_ONLY = "send cite only: Pathly relays the cited message's text"
ALREADY = "that message was already cited"
AS_CHIEF = "a chief acknowledges a human escalation as 'chief'"
NOT_OWN = "that is not this chief's project"
PAUSE = 0.02


def db():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def later() -> None:
    """Let the clock move on, so a message and a question are never stamped alike."""
    time.sleep(PAUSE)


class Session:
    """A chief session of ``tier`` on ``root`` whose style prompt is already recorded."""

    def __init__(self, tier: str, root: Path, engine: str = "claude"):
        self.chief: Chief = _chief(tier, root)
        self.root = root
        if engine != "claude":
            with db() as conn:
                conn.execute(
                    "UPDATE chief_sessions SET engine = ? WHERE run_id = ?",
                    (engine, self.chief.run_id),
                )
        self.style_id = self.type("You are the chief of this project.")

    @property
    def headers(self) -> dict:
        return self.chief.headers

    @property
    def run_id(self) -> str:
        return self.chief.run_id

    def type(self, text: str, relayed: bool = False) -> int:
        """What the hook stores when the person submits ``text`` (or another session sends it)."""
        from pathly_orchestrator.db.queries.chief import add_human_message

        stored = add_human_message(
            db(), self.run_id, str(self.root), text, relayed=relayed
        )
        return stored["id"]


def builder_headers(root: Path) -> dict:
    """The header of a live builder run token (an agent, not a chief)."""
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    token = mint_run_token(
        db(), "run-builder", "builder", "demo", str(root), "feature", "demo"
    )
    return {"X-Pathly-Run-Token": token}


class Asker:
    """A run registered under ``topic`` whose stage asked ``questions`` and waits for the answer."""

    def __init__(self, topic: str, root: Path | str, questions: list[dict]):
        from pathly_orchestrator.supervisor import registry
        from pathly_orchestrator.supervisor.interactions import (
            _await_agent_question,
        )
        from pathly_orchestrator.supervisor.state import RunnerState

        self.topic = topic
        self.state = RunnerState(
            topic=topic,
            flow="team",
            project_root=str(root),
            model="m",
            timeout=60,
            run_id="run-" + topic,
            status="running",
        )
        with registry._lock:
            registry._registry[topic] = self.state
        self.events: list[dict] = []
        self.result: list = []
        asked = {"tool_input": {"questions": questions}}

        def wait() -> None:
            self.result.append(
                _await_agent_question(
                    self.state,
                    topic,
                    asked,
                    lambda _t, event: self.events.append(event),
                )
            )

        self.thread = threading.Thread(target=wait, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 5
        while not self.state._awaiting_agent_answer and time.monotonic() < deadline:
            time.sleep(0.005)
        later()

    def still_waiting(self) -> bool:
        return (
            self.thread.is_alive()
            and self.state._awaiting_agent_answer
            and self.state._agent_question is not None
        )

    def answer(self, timeout: float = 5.0):
        """What the waiting stage returned (None when it is still waiting or was aborted)."""
        self.thread.join(timeout)
        return None if self.thread.is_alive() or not self.result else self.result[0]

    def stop(self) -> None:
        from pathly_orchestrator.supervisor import registry

        with registry._lock:
            self.state._abort_flag = True
            registry._registry.pop(self.topic, None)
        self.thread.join(5)


@pytest.fixture()
def idle(project):
    """``idle("topic")`` registers a run that asked nothing; taken out again after the test."""
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.state import RunnerState

    topics: list[str] = []

    def register(topic: str, root: Path | str | None = None) -> None:
        state = RunnerState(
            topic=topic,
            flow="team",
            project_root=str(root or project),
            model="m",
            timeout=60,
            run_id="run-" + topic,
            status="running",
        )
        with registry._lock:
            registry._registry[topic] = state
        topics.append(topic)

    yield register
    with registry._lock:
        for topic in topics:
            registry._registry.pop(topic, None)


ONE = [{"question": "CSV or JSON?", "options": [{"label": "CSV"}, {"label": "JSON"}]}]


@pytest.fixture()
def ask(project):
    """``ask("topic")`` starts a waiting run in the chief's project; stopped after the test."""
    made: list[Asker] = []

    def start(topic="t-1", questions=None, root=None) -> Asker:
        asker = Asker(topic, root or project, questions or ONE)
        made.append(asker)
        return asker

    yield start
    for asker in made:
        asker.stop()


def citations() -> list[dict]:
    rows = db().execute(
        "SELECT run_id, message_id, route, target FROM chief_citations ORDER BY id"
    )
    return [dict(row) for row in rows.fetchall()]


@pytest.fixture(autouse=True)
def _demo_is_a_feature_of_the_chiefs_project(project):
    """``post_row`` posts on the feature ``demo``. A chief reaches a row only inside its project
    (ticket 14), and a feature row is the project's when the feature has a folder there.
    """
    (project / "pathly" / "features" / "demo").mkdir(parents=True)


def post_row(type_: str, to_agent: str = "*", **extra) -> str:
    """A board row posted by an agent on the demo feature."""
    from pathly_orchestrator.db.queries.comms_messages import post_message

    return post_message(
        db(),
        board="feature",
        scope="demo",
        from_agent="builder",
        to_agent=to_agent,
        type=type_,
        text="A or B?" if type_ == "question" else "need a decision",
        **extra,
    )


def answer_rows(question_id: str) -> list[str]:
    rows = db().execute(
        "SELECT text FROM comms_messages WHERE reply_to = ? AND type = 'answer'",
        (question_id,),
    )
    return [row["text"] for row in rows.fetchall()]


def acknowledged_by(message_id: str) -> list:
    import json

    row = (
        db()
        .execute(
            "SELECT acknowledged_by FROM comms_messages WHERE id = ?", (message_id,)
        )
        .fetchone()
    )
    return json.loads(row["acknowledged_by"] or "[]")
