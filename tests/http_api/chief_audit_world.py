"""The sandbox of the chief gate audit (chief-agent 08, round 6): three directories, a board
with something on it, and a spawn host that spawns nothing.

``World`` seeds the board as a human would (no token), and ``variants`` gives, for each route, the
requests a chief can send that get past the view's own validation: the audit overrides one key of
one of them with a hostile value. A route reached with no valid request would stop at its first
check, so the baselines are what make the audit look at the sinks and not just at the 400s.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from chief_gate_support import _msg

DEMO = "demo"


@dataclass
class Variant:
    """One valid request: the values of the URL's variables and the body (or query string)."""

    label: str
    data: dict = field(default_factory=dict)
    url: dict = field(default_factory=dict)
    # Run before each request of the variant, for a request that uses up what it needs (a run
    # the registry forgets, a task that is claimed). A value of ``data`` that is a function is
    # called at the same moment, for a name that must be new each time.
    prepare: Callable[[], None] | None = None
    # The key of ``data`` whose value (the hostile one, when that key is under test) is the
    # scope of the feature board a run is holding when the request arrives: a stop route does
    # its work only for a board someone holds.
    holds: str = ""


def settle(timeout: float = 5.0) -> None:
    """Wait for the runs a request started: a board run holds its board, an FSM run is a thread."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        busy = [
            t
            for t in threading.enumerate()
            if t.name.startswith(("board-run-", "supervisor-")) and t.is_alive()
        ]
        if not busy:
            return
        time.sleep(0.01)


class World:
    """The seeded board of one test. Everything is posted by a human (no token) in ``DEMO``."""

    def __init__(self, client, project: Path, other: Path, server: Path):
        self.client = client
        self.project = project
        self.other = other
        self.server = server
        (project / "pathly" / "features" / DEMO).mkdir(parents=True)
        self.plan = project / "pathly" / "features" / DEMO / "PLAN.md"
        self.plan.write_text("# Plan\n\n## Scope\nSomething.\n")
        self.counter = itertools.count(1)
        self.foreign_id = ""
        self.goal = self.post("goal", text="Ship the export")
        self.empty_goal = self.post("goal", text="Nothing planned yet")
        self.task = self.post("task", text="Write it", goal_id=self.goal)
        self.note = self.post("status", text="a note")
        (project / "src").mkdir()
        (project / "src" / "x.py").write_text("def a_function():\n    return 1\n")
        self.project_decision = self.post(
            "decision", board="project", scope=str(project), text="use the project way"
        )
        self.decision_a = self.post("decision", text="use A")
        self.decision_b = self.post("decision", text="use B")
        self.question = self.post(
            "question",
            text="A or B?",
            options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        )
        self.artifact = self.post(
            "artifact",
            text="the plan",
            artifact_path=str(self.plan),
            artifact_type="PLAN",
        )
        self.foreign_id = self.foreign_artifact_id()

    def foreign_artifact_id(self) -> str:
        """The id of an artifact row another project's file was stored under, posted by a human
        (a chief may not post one): the row a chief that knows its id could ask to read.
        """
        theirs = self.other / "pathly" / "features" / DEMO / "PLAN.md"
        message = self.post(
            "artifact",
            text="their plan",
            artifact_path=str(theirs),
            artifact_type="PLAN",
        )
        return self.artifact_id(message)

    def post(self, type_: str, **extra) -> str:
        body = _msg(type_, **extra)
        body["from"] = "human"
        resp = self.client.post("/comms/post", json=body)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()["message_id"]

    def artifact_id(self, message: str | None = None) -> str:
        resp = self.client.get(
            "/comms/artifacts",
            query_string={"scope": DEMO, "message_id": message or self.artifact},
        )
        rows = (resp.get_json() or {}).get("artifacts") or []
        assert rows, "the seeded artifact should be listed"
        return rows[0]["id"]

    def fresh_task(self) -> str:
        return self.post("task", text="Write it again", goal_id=self.goal)

    def fresh_project_decision(self) -> str:
        """A decision on the chief's own project board, which nothing has superseded."""
        return self.post(
            "decision", board="project", scope=str(self.project), text="an old way"
        )

    def fresh_name(self, stem: str) -> str:
        return f"{stem}-{next(self.counter)}"

    def register_run(self, status: str) -> None:
        """A run of the registry with the id ``run-audit`` (a retry pops it, so each request
        registers it again)."""
        from pathly_orchestrator.supervisor import registry
        from pathly_orchestrator.supervisor.state import RunnerState

        registry._registry["audit-topic"] = RunnerState(
            topic="audit-topic",
            flow="team",
            project_root=str(self.project),
            model="m",
            timeout=60,
            run_id="run-audit",
            status=status,
        )

    def hold_board(self, scope: str = DEMO, run_id: str = "run-audit") -> None:
        """Make ``run_id`` the holder of the feature board ``scope`` and of no other."""
        from pathly_orchestrator.supervisor import board_lock

        board_lock._held.clear()
        board_lock.acquire("feature", scope, run_id)

    def register_asking_run(self) -> None:
        """A run of the registry that has asked its human a question and waits for the answer."""
        from pathly_orchestrator.supervisor import registry
        from pathly_orchestrator.supervisor.state import RunnerState

        registry._registry["audit-asking"] = RunnerState(
            topic="audit-asking",
            flow="team",
            project_root=str(self.project),
            model="m",
            timeout=60,
            run_id="run-asking",
            status="running",
        )
        registry._registry["audit-asking"]._awaiting_agent_answer = True

    def forget_code_answers(self) -> None:
        """The query cache would answer a repeated query without calling the backend."""
        from pathly_orchestrator.http_server.blueprints.code import query
        from pathly_orchestrator.runner import code_context_cli

        query._QUERY_CACHE.clear()
        code_context_cli._CLI_CACHE.clear()

    def root(self) -> dict:
        return {"project_root": str(self.project)}

    # --- the valid requests of each route ------------------------------------------------

    def variants(self, rule: str, method: str) -> list[Variant]:
        root = self.root()
        from chief_audit_calls import POST_VARIANTS
        from chief_audit_reads import GET_VARIANTS

        maker = POST_VARIANTS.get(rule) if method == "POST" else GET_VARIANTS.get(rule)
        if maker is None:
            return [Variant("default", dict(root))]
        return [
            Variant(v.label, {**root, **v.data}, v.url, v.prepare, v.holds)
            for v in maker(self)
        ]

    def request(self, rule: str, method: str, variant: Variant, key, value, headers):
        """Send ``variant`` with ``key`` set to ``value`` (a URL variable or a body key)."""
        if variant.prepare is not None:
            variant.prepare()
        data = {k: (v() if callable(v) else v) for k, v in variant.data.items()}
        url = dict(variant.url)
        variables = _variables(rule)
        for name in variables:
            url.setdefault(name, "x")
        if key in variables:
            url[key] = value
        else:
            data[key] = _SHAPES.get(key, _plain)(value)
        path = rule
        for name, val in url.items():
            text = quote(str(val), safe="")
            path = path.replace(f"<path:{name}>", text).replace(f"<{name}>", text)
        if variant.holds:
            self.hold_board(str(data.get(variant.holds)))
        if method == "GET":
            return self.client.get(
                path, query_string=_query(data), headers=headers or {}
            )
        return self.client.post(path, json=data, headers=headers or {})


def _variables(rule: str) -> list[str]:
    from pathly_orchestrator.http_server.chief_field_types import url_variables

    return sorted(url_variables(rule))


def _query(data: dict) -> dict:
    return {
        k: (v if isinstance(v, (str, int, float)) else str(v)) for k, v in data.items()
    }


def _plain(value):
    return value


# How a hostile string is put into a key whose value is a list or a map.
_SHAPES = {
    "context_refs": lambda v: [{"artifact": v, "anchor": v}],
    "files": lambda v: [v],
    "depends_on": lambda v: [v],
    "supersedes": lambda v: [v],
    "options": lambda v: [{"id": v, "label": v}],
    "stage_overrides": lambda v: {v: v},
    "no_refs": lambda v: v,
}
