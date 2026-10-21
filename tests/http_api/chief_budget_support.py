"""Helpers of the chief budget tests (chief-agent 15).

A chief session has a ceiling for the cost one run may state and a limit on the runs it may
start. The tests drive the real gate and routes with an operator chief; the code that would start
an agent is replaced by a record of the call (``flow_runs`` for ``supervisor.api.start_run``,
``stubs`` of ``chief_bind_support`` for goal and board runs). ``STARTS`` is one call per route that
starts work, each answered 200, so a test can run the same case over all of them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from chief_bind_support import project_row
from chief_cite_support import db

ABOVE = "max_cost_usd above this chief's ceiling"
NOT_A_COST = "max_cost_usd must be a finite number above 0"
MAXED = "this chief session has started its maximum number of runs"
CEILING_KEY = "chief.max_cost_usd_per_run"
LIMIT_KEY = "chief.max_runs_per_session"
RETRY_FIELDS = {"flow": "team", "max_iterations": 3}


def setting(key: str, value: str) -> None:
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(db(), key, value)


def runs_started(chief) -> int:
    row = db().execute(
        "SELECT runs_started FROM chief_sessions WHERE run_id = ?", (chief.run_id,)
    )
    return row.fetchone()[0]


def shown(resp) -> str:
    return f"{resp.status_code} {resp.get_data(as_text=True)[:200]}"


def is_above(resp, ceiling: float = 10.0) -> bool:
    """The gate's 403 for a cost above the ceiling (it carries the usual refusal fields too)."""
    body = resp.get_json(silent=True) or {}
    return (
        resp.status_code == 403
        and body.get("error") == ABOVE
        and body.get("ceiling") == ceiling
        and "allowed" in body
    )


def is_maxed(resp, limit: int) -> bool:
    body = resp.get_json(silent=True) or {}
    return (
        resp.status_code == 403
        and body.get("error") == MAXED
        and body.get("limit") == limit
        and "allowed" in body
    )


class FlowRuns:
    """Stands in for ``supervisor.api.start_run``: records the keywords of each start."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(run_id=f"run-{len(self.calls)}")


@pytest.fixture()
def flow_runs(monkeypatch) -> FlowRuns:
    started = FlowRuns()
    monkeypatch.setattr("pathly_orchestrator.supervisor.api.start_run", started)
    return started


def start_flow(client, chief, project, **extra):
    """``POST /runs`` of a flow, with the keys its entry lists."""
    body = {
        "kind": "flow",
        "scope": "demo",
        "flow": "team",
        "project_root": str(project),
        **extra,
    }
    return client.post("/runs", json=body, headers=chief.headers)


def post_raw(client, path, text: str, headers):
    """POST JSON text as it is written (Python's parser takes ``NaN`` and ``Infinity``)."""
    return client.post(
        path, data=text, content_type="application/json", headers=headers
    )


def flow_text(project, cost_json: str) -> str:
    """The text of a ``POST /runs`` flow body whose ``max_cost_usd`` is the JSON ``cost_json``."""
    return (
        '{"kind": "flow", "scope": "demo", "flow": "team", "project_root": "%s",'
        ' "max_cost_usd": %s}' % (project, cost_json)
    )


def retry_text(project, cost_json: str) -> str:
    return (
        '{"flow": "team", "max_iterations": 3, "project_root": "%s",'
        ' "max_cost_usd": %s}' % (project, cost_json)
    )


@pytest.fixture()
def finished_run(project):
    """``register()`` puts a finished run of the chief's project in the registry (a retry pops
    it); the entry is removed again when the test ends.
    """
    from pathly_orchestrator.supervisor import registry

    def register() -> str:
        registry._registry["retry-topic"] = SimpleNamespace(
            run_id="run-own-1", status="done", project_root=str(project)
        )
        return "run-own-1"

    yield register
    registry._registry.pop("retry-topic", None)


def retry(client, chief, project, **extra):
    """``POST /runs/run-own-1/retry``; it states no cost unless ``max_cost_usd`` is passed."""
    body = {"project_root": str(project), **RETRY_FIELDS, **extra}
    return client.post("/runs/run-own-1/retry", json=body, headers=chief.headers)


# --- one call per route that starts work, each answered 200 --------------------------------


def _flow(client, chief, project, finished_run):
    return start_flow(client, chief, project)


def _goal_kind(client, chief, project, finished_run):
    goal = project_row(project, "goal")
    body = {"kind": "goal", "goal_id": goal, "project_root": str(project)}
    return client.post("/runs", json=body, headers=chief.headers)


def _goal_run(client, chief, project, finished_run):
    goal = project_row(project, "goal")
    body = {"goal_id": goal, "project_root": str(project)}
    return client.post("/comms/goals/run", json=body, headers=chief.headers)


def _board_run(client, chief, project, finished_run):
    body = {"scope": "demo", "project_root": str(project)}
    return client.post("/comms/run", json=body, headers=chief.headers)


def _task_run(client, chief, project, finished_run):
    task = project_row(project, "task")
    body = {"message_id": task, "project_root": str(project)}
    return client.post("/comms/tasks/run", json=body, headers=chief.headers)


def _retry(client, chief, project, finished_run):
    finished_run()
    return retry(client, chief, project, max_cost_usd=1)


STARTS = {
    "POST /runs flow": _flow,
    "POST /runs goal": _goal_kind,
    "/comms/goals/run": _goal_run,
    "/comms/run": _board_run,
    "/comms/tasks/run": _task_run,
    "retry": _retry,
}
