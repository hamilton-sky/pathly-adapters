"""Helpers of the chief acceptance test that are about one scenario (chief-agent 13).

The fixtures and the fake spawn host are in ``chief_acceptance_support``. Here: ``Asker`` is a run
of the registry whose stage waits in ``_await_agent_question``, ``busy`` an active run that makes
a flow start a route 409, ``Subscribed`` a client of ``/events/runner`` and ``/events/runs`` on
every topic and run, and the calls and reads the scenarios repeat. Imported by bare name:
``tests/comms_board`` is on ``sys.path`` for the test files that sit in it.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from binding_support import governance_part, standing_part
from chief_acceptance_support import (
    WAIT,
    Chief,
    db,
    later,
    open_chief,
    paste_prompt,
    session_row,
    wait_for,
)

from _paths import SRC

# -- an agent that asks its human a question -----------------------------------------------


class Asker:
    """A run in the registry whose stage asked its human ``questions`` and waits for the answer,
    as a real ``_await_agent_question`` does."""

    def __init__(self, topic: str, root: Path, questions: list[dict]) -> None:
        from pathly_orchestrator.supervisor import registry
        from pathly_orchestrator.supervisor.interactions import _await_agent_question
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
        self.result: list = []
        asked = {"tool_input": {"questions": questions}}
        self._thread = threading.Thread(
            target=lambda: self.result.append(
                _await_agent_question(self.state, topic, asked, None)
            ),
            name=f"asker-{topic}",
            daemon=True,
        )
        self._thread.start()
        wait_for(lambda: self.state._agent_question is not None, "the question")
        later()

    def still_waiting(self) -> bool:
        return self._thread.is_alive() and self.state._agent_question is not None

    def answer(self):
        """What the stage received (None when it is still waiting)."""
        self._thread.join(WAIT)
        return None if self._thread.is_alive() or not self.result else self.result[0]

    def stop(self) -> None:
        from pathly_orchestrator.supervisor import registry

        with registry._lock:
            self.state._abort_flag = True
            registry._registry.pop(self.topic, None)
        self._thread.join(WAIT)
        assert not self._thread.is_alive()


@pytest.fixture()
def ask(project: Path):
    """``ask("topic")`` starts a waiting run in the project; stopped after the test."""
    made: list[Asker] = []

    def start(topic: str, questions: list[dict]) -> Asker:
        asker = Asker(topic, project, questions)
        made.append(asker)
        return asker

    yield start
    for asker in made:
        asker.stop()


# -- a client that listens on every topic and every run ------------------------------------


class Subscribed(dict):
    """A registry in which every key already holds one queue: a client subscribed to every
    topic (``/events/runner``) or every run (``/events/runs``), which a test cannot name before
    the chief's and the worker's ids exist."""

    def __init__(self, sink: queue.Queue) -> None:
        super().__init__()
        self.sink = sink

    def get(self, key, default=None):
        return [self.sink]


def drained(sink: queue.Queue) -> list[str]:
    """What ``sink`` received, as the raw JSON the stream would have sent."""
    found: list[str] = []
    while True:
        try:
            found.append(sink.get_nowait())
        except queue.Empty:
            return found


@pytest.fixture()
def busy(project: Path):
    """``busy("topic")`` registers an active run, so starting a flow on that topic is a 409:
    a start the chief gate lets through and the route then refuses, with nothing started.
    """
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.state import RunnerState

    topics: list[str] = []

    def register(topic: str) -> None:
        state = RunnerState(
            topic=topic,
            flow="team",
            project_root=str(project),
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


# -- what the agents and the person say, as the scenarios repeat it ---------------------------

NOT_CITED = "cite a human message from this chief session"
CITE_ONLY = "send cite only: Pathly relays the cited message's text"
ALREADY = "that message was already cited"
AS_CHIEF = "a chief acknowledges a human escalation as 'chief'"
ABOVE = "max_cost_usd above this chief's ceiling"
MAXED = "this chief session has started its maximum number of runs"
NOT_IN_PROJECT = "not in this chief's project"
BINDING_REFUSED = "only the chief retires a binding directive"
# Quotes and a line break: what a shell-quoted JSON argument would mangle if the chief wrote it.
WORDS = 'use CSV, it\'s what "ops" asked for\nand keep the header row'
ONE = [{"question": "CSV or JSON?", "options": [{"label": "CSV"}, {"label": "JSON"}]}]
NO_DEPS = "Never add a dependency without asking the human first."
FORMAT_FIRST = "Run the formatter before every commit."
STAGES = ("BUILDING", "REVIEWING", "TESTING")  # team/build, team/review, team/test


def root_line(chief: Chief) -> str:
    return f"Your project root: {session_row(chief.run_id)['project_root']}"


def post_goal(client, chief, root, text="Ship the CSV export"):
    body = {
        "from": "chief",
        "type": "goal",
        "text": text,
        "board": "project",
        "scope": root,
        "feature": "project",
        "project_root": root,
    }
    return client.post("/comms/post", json=body, headers=chief.headers)


def start_single_run(client, chief, root):
    body = {"kind": "single", "board": "project", "scope": root, "project_root": root}
    return client.post("/runs", json=body, headers=chief.headers)


def writes_of(root: str) -> list[tuple[str, dict, str]]:
    """Calls that change something, with the action the gate names for each."""
    note = {"feature": "demo", "from": "chief", "text": "a note from the status chief"}
    own = {"project_root": root}
    run = {"kind": "single", "board": "project", "scope": root, **own}
    return [
        ("/comms/post", {**note, "type": "discovery"}, "post"),
        ("/comms/post", {**note, "type": "goal"}, "plan"),
        ("/comms/post", {**note, "type": "decision"}, "decide"),
        ("/comms/directives", {**own, "to_agent": "*", "text": "x"}, "decide"),
        ("/runs", run, "run"),
        ("/runs/none/stop", own, "stop"),
        ("/comms/answer", {"question_id": "q-1", "cite": 1}, "answer"),
    ]


def opened_with_the_prompt_recorded(client, spawn_host, project) -> Chief:
    chief = open_chief(client, spawn_host, project, "operator")
    paste_prompt(client, chief)
    return chief


def post_directive(client, chief, root, text, to_agent="*") -> str:
    body = {"project_root": root, "to_agent": to_agent, "text": text}
    resp = client.post("/comms/directives", json=body, headers=chief.headers)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()["id"]


def standing_orders(project) -> dict[str, str]:
    """The standing-orders block of the prompt of each stage, for a feature of the project."""
    from pathly_orchestrator.fsm_compose import build_prompt
    from pathly_orchestrator.fsm_ops import _load_flow

    flow = _load_flow("team")
    storage = project / "pathly" / "features" / "demo"
    prompts = {s: build_prompt(flow, s, storage) for s in STAGES}
    assert [flow["agent_map"][s] for s in STAGES] == [
        "team/build",
        "team/review",
        "team/test",
    ]
    return {s: standing_part(governance_part(p)) for s, p in prompts.items()}


def worker_token(role: str, root: str) -> str:
    """The run token of a worker of ``role`` on the project board (an agent, not a chief)."""
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    return mint_run_token(db(), f"run-{role}", role, "demo", root, "project", root)


def board_row(message_id: str):
    found = db().execute("SELECT * FROM comms_messages WHERE id=?", (message_id,))
    return found.fetchone()


def in_place(message_id: str) -> bool:
    """True when the row is not retired: not superseded, not deleted, still binding."""
    row = board_row(message_id)
    return (row["superseded_by"], row["deleted_at"], row["binding"]) == (None, None, 1)


def put_setting(client, key: str, value):
    """What the person does in Settings: no run token, so no chief gate."""
    return client.put(f"/db/settings/{key}", json={"value": value})


def session_state(client, root: str) -> dict:
    return client.get("/chief/session", query_string={"project_root": root}).get_json()


def run_pathly(
    args: list[str], token: str, port: int, home
) -> subprocess.CompletedProcess:
    """``pathly api ...`` as the chief's tab runs it: its own process, the token and the port in
    the environment, and a home with no server secret in it."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PATHLY_")}
    env.update(
        PATHLY_RUN_TOKEN=token,
        PATHLY_FSM_HTTP_PORT=str(port),
        PYTHONPATH=str(SRC),
        HOME=str(home),
        USERPROFILE=str(home),
    )
    return subprocess.run(
        [sys.executable, "-m", "pathly_orchestrator.chief_cli", "api", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
