"""Helpers of the round-two autopilot acceptance test (chief-autopilot-round-two 12).

The fake agents of round two, for ``autopilot_acceptance_support.AgentHost``. ``Agents`` is the
host's ``agent``: a ``consult-`` spawn runs ``consult``, any other spawn runs ``worker``. The
workers ask a role with their spawn's run token, on the project board the token names, so the
real router (``POST /comms/post``'s ``after_request`` hook) routes the question:
``loop_task_asks_role`` is a goal-loop task agent, ``drain_dag_asks_role`` a drain-dag agent that
leaves its claimed task unfinished. ``consult_says`` is the consult's agent: it writes its
``AGENT_DONE`` with the summary the test chooses (``ANSWER: ...``, ``ANSWER: USER ...``), after
editing a source file when told to. ``planner_posts`` is a decompose's planner agent. Imported by
bare name: ``tests/comms_board`` is on ``sys.path`` for the test files that sit in it.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable

from autopilot_acceptance_support import (
    DRAIN_DAG_CLAIM_RUN_ID,
    AgentCalls,
    completion_report,
    printed_token,
    ready_tasks,
    task_row,
)
from chief_acceptance_support import db, wait_for

CONSULT_PREFIX = "consult-"
CONSULT_WAIT = 60.0


def ask_role(calls: AgentCalls, root: str, text: str, to: str = "architect") -> str:
    """A worker's question to a role with its run token: the body of the ``consult`` fragment's
    post, as the prompt gives it (``feature`` and ``scope`` the board scope, ``board`` the
    project board the token names).
    """
    body = {
        "feature": root,
        "board": "project",
        "scope": root,
        "from": "builder",
        "to": to,
        "type": "question",
        "text": text,
    }
    return calls.post("/comms/post", body)["message_id"]


class Agents:
    """The host's agent: a ``consult-`` spawn runs ``consult``, any other one ``worker``.
    Every payload is recorded in ``spawns`` (the consults' also in ``consults``)."""

    def __init__(self, worker: Callable[[dict], str], consult: Callable[[dict], str]):
        self.worker = worker
        self.consult = consult
        self.spawns: list[dict] = []
        self.consults: list[dict] = []

    def __call__(self, payload: dict) -> str:
        self.spawns.append(payload)
        if payload["run_id"].startswith(CONSULT_PREFIX):
            self.consults.append(payload)
            return self.consult(payload)
        return self.worker(payload)


def consult_says(
    client,
    summary: str | Callable[[dict], str],
    edit: Path | None = None,
) -> Callable[[dict], str]:
    """A consult agent: writes ``edit`` (a source file) when given, then its ``AGENT_DONE``
    with ``summary`` (a text, or a function of the spawn's payload) through ``/runner/event``,
    the completion-report fragment's call."""

    def agent(payload: dict) -> str:
        if edit is not None:
            edit.write_text(edit.read_text(encoding="utf-8") + "# the consult\n")
        said = summary(payload) if callable(summary) else summary
        found = re.search(r"'feature': '([^']*)'", payload["prompt"])
        event = {
            "type": "AGENT_DONE",
            "agent": payload.get("agent") or "architect",
            "model": "claude-sonnet-4-6",
            "run_id": payload["run_id"],
            "category": "consult",
            "result": "DONE",
            "outcome": "success",
            "summary": said,
            "schema_version": 1,
        }
        body = {
            "type": "AGENT_DONE",
            "feature": found.group(1) if found else "project",
            "project_root": payload["cwd"],
            "payload": event,
        }
        resp = client.post("/runner/event", json=body)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return ""

    return agent


def loop_task_asks_role(client, root: str, question: str, seen: list) -> Callable:
    """A goal-loop task agent: its first spawn asks the architect and reports it could not
    finish, a later one reports success. Every task spawn's payload goes in ``seen``."""

    def agent(payload: dict) -> str:
        seen.append(payload)
        if not payload["run_id"].startswith("sched-"):
            return ""  # not a task's spawn: the test's assertions name it
        if len(seen) == 1:
            ask_role(AgentCalls(client, payload), root, question)
            completion_report(client, payload, "failed", "waiting for the architect")
        else:
            completion_report(client, payload, "success")
        return ""

    return agent


def drain_dag_asks_role(
    client, root: str, goal_id: str, seen: dict, questions: list[str]
) -> Callable:
    """A drain-dag agent that claims the first ready task, asks the architect each of
    ``questions`` and ends with the task unfinished (the answer decides how to build it).
    """

    def agent(payload: dict) -> str:
        calls = AgentCalls(client, payload)
        task = ready_tasks(calls, root, goal_id)[0]
        claim = {"message_id": task["id"], "run_id": DRAIN_DAG_CLAIM_RUN_ID}
        seen["claim"] = calls.post("/comms/tasks/claim", claim)
        seen["questions"] = [ask_role(calls, root, text) for text in questions]
        seen["run_id"] = payload["run_id"]
        return printed_token(payload)

    return agent


def planner_posts(client, root: str, goal_id: str, texts: list[str], seen: dict):
    """A decompose's planner agent: posts each of ``texts`` as a task of the goal with its run
    token and keeps every answer (status and body) in ``seen["posts"]``."""

    def agent(payload: dict) -> str:
        headers = {"X-Pathly-Run-Token": payload["run_token"]}
        seen["run_id"] = payload["run_id"]
        seen["posts"] = []
        for text in texts:
            body = {
                "feature": "project",
                "board": "project",
                "scope": root,
                "from": "planner",
                "type": "task",
                "goal_id": goal_id,
                "text": text,
            }
            resp = client.post("/comms/post", json=body, headers=headers)
            seen["posts"].append((resp.status_code, resp.get_json()))
        return ""

    return agent


# -- what the tests read -------------------------------------------------------------------------


def consults_ended() -> None:
    """Wait until every consult thread (the router's ``consult-<question>`` and the run's
    ``consult-<12 hex>``) ended: the chief guard does not watch them."""
    wait_for(
        lambda: not [
            t
            for t in threading.enumerate()
            if t.is_alive() and t.name.startswith(CONSULT_PREFIX)
        ],
        "the consult threads to end",
        CONSULT_WAIT,
    )


def route_of(question_id: str) -> dict | None:
    row = (
        db()
        .execute("SELECT * FROM consult_routes WHERE question_id=?", (question_id,))
        .fetchone()
    )
    return dict(row) if row is not None else None


def route_ended(question_id: str) -> dict:
    """The question's route once it ended (``answered``, ``to_person``, ``withheld``,
    ``failed``)."""
    from pathly_orchestrator.db.queries.consult_routes import END_STATUSES

    def ended():
        route = route_of(question_id)
        return route if route and route["status"] in END_STATUSES else None

    return wait_for(ended, f"the route of {question_id} to end", CONSULT_WAIT)


def message(message_id: str) -> dict:
    row = db().execute("SELECT * FROM comms_messages WHERE id=?", (message_id,))
    return dict(row.fetchone())


def replies(question_id: str, type_: str) -> list[dict]:
    rows = db().execute(
        "SELECT * FROM comms_messages WHERE reply_to=? AND type=? AND deleted_at IS NULL"
        " ORDER BY ts",
        (question_id, type_),
    )
    return [dict(r) for r in rows.fetchall()]


def invocations(run_id: str) -> list[dict]:
    rows = db().execute(
        "SELECT agent_role, category FROM agent_invocations WHERE run_id=?", (run_id,)
    )
    return [dict(r) for r in rows.fetchall()]


def task_waits_on(task_id: str) -> str:
    """The question a parked task waits on (its ``fail_reason``'s id)."""
    row = task_row(task_id)
    assert row["task_status"] == "blocked", row
    assert row["fail_reason"].startswith("waiting_for_answer:"), row
    return row["fail_reason"].split(":", 1)[1]
