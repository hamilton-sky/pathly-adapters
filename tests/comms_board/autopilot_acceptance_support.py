"""Helpers of the round-one autopilot acceptance test (chief-autopilot 09).

``AgentHost`` is the chief acceptance test's ``SpawnHost`` (a thread reading a queue registered in
``sse._spawn_clients``, what an ``/events/spawn`` client gets) whose worker spawns run a fake
agent process: ``host.agent(payload)`` makes the agent's own calls with the spawn's run token,
then the host reports the process exited 0 through ``POST /runner/terminal/result`` with what the
agent printed as its stdout tail, as Studio does. The agents here follow the texts they are given:
``drain_dag_asks`` and ``drain_dag_finishes`` make the calls of ``development/drain-dag`` (its
claim body is the literal ``"$GOAL_ID-single"``), ``loop_task_asks`` is a goal-loop task agent
that asks its human and ends. Imported by bare name: ``tests/comms_board`` is on ``sys.path`` for
the test files that sit in it.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable, Iterator

import pytest
from chief_acceptance_support import (
    TOKEN_HEADER,
    Chief,
    SpawnHost,
    Worker,
    db,
    wait_for,
)

DRAIN_DAG_CLAIM_RUN_ID = "$GOAL_ID-single"  # drain-dag's body, as an agent copies it
WAITING = "waiting_for_answer"
ANSWER_HEADING = "## Answers to your questions"
ENDED = ("done", "error", "aborted", "parked")
RUN_WAIT = 60.0


def printed_token(payload: dict) -> str:
    """What an agent prints that leaks its credential (``env | grep PATHLY``)."""
    return f"PATHLY_RUN_TOKEN: {payload['run_token']}\n"


class AgentHost(SpawnHost):
    """A spawn host whose worker spawns run ``self.agent`` and then report the exit through the
    route Studio posts to. ``client`` is the agents' own test client: one that a test holds open
    in a ``with`` block keeps its request context on its own thread."""

    def __init__(self) -> None:
        from pathly_orchestrator.http_server import app

        super().__init__()
        self.client = app.test_client()
        self.agent: Callable[[dict], str] = lambda payload: ""
        self.spawns: list[dict] = []

    def _handle(self, payload: dict) -> None:
        from pathly_orchestrator.db.queries.run_tokens import resolve_run_token
        from pathly_orchestrator.supervisor.registry import get_run

        if payload.get("type") != "TERMINAL_SPAWN" or payload.get("interactive"):
            super()._handle(payload)
            return
        run_id = payload["run_id"]
        run = get_run(run_id)
        assert run is not None, f"no run is registered for the spawn of {run_id}"
        live = resolve_run_token(db(), payload.get("run_token"))
        self.workers[run_id] = Worker(payload, live)
        self.spawns.append(payload)
        run.mark_started()
        if self.hold:
            return
        stdout = self.agent(payload)
        resp = self.client.post(
            "/runner/terminal/result",
            json={
                "topic": payload["topic"],
                "run_id": run_id,
                "adapter": payload.get("adapter") or "claude",
                "exit_code": 0,
                "wall_seconds": 1,
                "stdout_tail": stdout,
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)


@pytest.fixture()
def agent_host() -> Iterator[AgentHost]:
    host = AgentHost()
    host.start()
    try:
        yield host
    finally:
        host.stop()


# -- what a fake agent does with its token -------------------------------------------------------


class AgentCalls:
    """The calls of one agent process: every one sends the spawn's run token."""

    def __init__(self, client, payload: dict) -> None:
        self.client = client
        self.headers = {TOKEN_HEADER: payload["run_token"]}

    def get(self, path: str, **query):
        resp = self.client.get(path, query_string=query, headers=self.headers)
        assert resp.status_code == 200, (path, resp.get_data(as_text=True))
        return resp.get_json()

    def post(self, path: str, body: dict) -> dict:
        resp = self.client.post(path, json=body, headers=self.headers)
        assert resp.status_code == 200, (path, resp.get_data(as_text=True))
        return resp.get_json()


def ready_tasks(calls: AgentCalls, root: str, goal_id: str) -> list[dict]:
    """drain-dag step 1 on the project board."""
    found = calls.get(
        "/comms/tasks",
        ready="true",
        board="project",
        feature=root,
        scope=root,
        goal_id=goal_id,
    )
    return found if isinstance(found, list) else found["tasks"]


def ask_human(calls: AgentCalls, root: str, text: str) -> str:
    body = {
        "feature": "project",
        "board": "project",
        "scope": root,
        "from": "builder",
        "to": "human",
        "type": "question",
        "text": text,
    }
    return calls.post("/comms/post", body)["message_id"]


def drain_dag_asks(client, root: str, goal_id: str, seen: dict, question: str):
    """A drain-dag agent that claims the first ready task, asks its human and ends unfinished."""

    def agent(payload: dict) -> str:
        calls = AgentCalls(client, payload)
        task = ready_tasks(calls, root, goal_id)[0]
        claim = {"message_id": task["id"], "run_id": DRAIN_DAG_CLAIM_RUN_ID}
        seen["claim"] = calls.post("/comms/tasks/claim", claim)
        seen["claimed_by"] = task_row(task["id"])["claimed_by"]
        seen["question"] = ask_human(calls, root, question)
        seen["run_id"] = payload["run_id"]
        seen["token"] = payload["run_token"]
        return printed_token(payload)

    return agent


def drain_dag_finishes(client, root: str, goal_id: str, seen: dict):
    """A drain-dag agent that reads its ready task, claims it and completes it."""

    def agent(payload: dict) -> str:
        calls = AgentCalls(client, payload)
        task = ready_tasks(calls, root, goal_id)[0]
        seen["task"] = task
        claim = {"message_id": task["id"], "run_id": DRAIN_DAG_CLAIM_RUN_ID}
        seen["claim"] = calls.post("/comms/tasks/claim", claim)
        done = {"message_id": task["id"], "feature": "project"}
        seen["complete"] = calls.post("/comms/tasks/complete", done)
        seen["run_id"] = payload["run_id"]
        return "drained the goal\n"

    return agent


def _substituted(prompt: str, key: str) -> str:
    """The value the runner substituted for ``key`` in the completion-report command."""
    found = re.search(rf"'{key}': '([^']*)'", prompt)
    assert found is not None, f"no {key} in the prompt"
    return found.group(1)


def completion_report(client, payload: dict, outcome: str, error: str = "") -> None:
    """The completion-report fragment's AGENT_DONE, as the command in the prompt posts it."""
    prompt = payload["prompt"]
    event = {
        "type": "AGENT_DONE",
        "agent": "builder",
        "model": "claude-sonnet-4-6",
        "run_id": _substituted(prompt, "run_id"),
        "category": _substituted(prompt, "category"),
        "board_scope": _substituted(prompt, "board_scope"),
        "result": "DONE",
        "outcome": outcome,
        "error": error,
        "summary": error or "wrote the parser",
        "schema_version": 1,
    }
    body = {
        "type": "AGENT_DONE",
        "feature": _substituted(prompt, "feature"),
        "project_root": payload["cwd"],
        "payload": event,
    }
    resp = client.post("/runner/event", json=body)
    assert resp.status_code == 200, resp.get_data(as_text=True)


def loop_task_asks(client, root: str, question: str, seen: list):
    """A goal-loop task agent: the first spawn asks its human and reports it could not finish,
    a later one does the work and reports success. Any other spawn is recorded and exits.
    """

    def agent(payload: dict) -> str:
        seen.append(payload)
        if not payload["run_id"].startswith("sched-"):
            return ""  # not a task's spawn: the test's assertions name it
        if len(seen) == 1:
            ask_human(AgentCalls(client, payload), root, question)
            completion_report(client, payload, "failed", "waiting for the answer")
        else:
            completion_report(client, payload, "success")
        return ""

    return agent


# -- what the chief does -------------------------------------------------------------------------


def chief_post(client, chief: Chief, root: str, **fields) -> str:
    body = {
        "from": "chief",
        "board": "project",
        "scope": root,
        "feature": "project",
        "project_root": root,
    }
    body.update(fields)
    resp = client.post("/comms/post", json=body, headers=chief.headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["message_id"]


def start_goal(client, chief: Chief, root: str, goal_id: str) -> str:
    body = {"kind": "goal", "goal_id": goal_id, "project_root": root}
    resp = client.post("/runs", json=body, headers=chief.headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["kind"] == "goal"
    return resp.get_json()["run_id"]


# -- what the tests read -------------------------------------------------------------------------


def task_row(task_id: str) -> dict:
    row = db().execute(
        "SELECT task_status, claimed_by, attempts, waits, fail_reason"
        " FROM comms_messages WHERE id=?",
        (task_id,),
    )
    return dict(row.fetchone())


def run_detail(client, run_id: str) -> dict:
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["run"]


def ended(run_id: str) -> str:
    """Wait until ``run_history`` says the run ended; its status."""

    def status():
        row = (
            db()
            .execute("SELECT status FROM run_history WHERE run_id=?", (run_id,))
            .fetchone()
        )
        return row["status"] if row is not None and row["status"] in ENDED else None

    return wait_for(status, f"the run {run_id} to end", RUN_WAIT)


def rows_holding(text: str) -> list[tuple[str, str]]:
    """Every ``fsm_events``, ``run_log`` and ``comms_messages`` row with ``text`` in a column."""
    found = []
    for table in ("fsm_events", "run_log", "comms_messages"):
        for row in db().execute(f"SELECT * FROM {table}").fetchall():
            if any(text in str(value) for value in tuple(row)):
                found.append((table, json.dumps(dict(row), default=str)[:200]))
    return found


def invocations_of(run_id: str) -> int:
    row = (
        db()
        .execute("SELECT COUNT(*) FROM agent_invocations WHERE run_id=?", (run_id,))
        .fetchone()
    )
    return int(row[0])


def git_project(root: Path) -> None:
    """Make ``root`` a git repository with one commit: the loop's proof gates read its diff."""

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    (root / ".gitignore").write_text("pathly/**/BOARD.json\nEVENTS.jsonl\n")
    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    git("add", "-A")
    git("commit", "-q", "-m", "initial")
