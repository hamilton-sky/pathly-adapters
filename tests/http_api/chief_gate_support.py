"""Shared fixtures and helpers of the chief gate tests (chief-agent 08).

``_chief`` makes a chief session and its live token through the queries, the way
``open_chief`` does, so a test needs no spawn host. ``_gated`` and ``_passed`` tell the
gate's own 403 (it always carries ``allowed``) from an answer of the route. The three
autouse fixtures keep a stream, a re-index and a code backend from running in a test; every
``test_chief_gate*.py`` imports them (and ``app``, which the first needs).
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import NamedTuple

import pytest

# Rules the table lists before a later ticket adds the route (ticket 12 adds the directives
# route, and the table already maps it to ``decide``). A rule listed here may be missing from
# ``app.url_map``; any other listed rule that is missing fails the test.
PLANNED = {("/comms/directives", "POST")}

TIERS = ("status", "planner", "operator")


class Chief(NamedTuple):
    token: str
    run_id: str

    @property
    def headers(self) -> dict:
        return {"X-Pathly-Run-Token": self.token}


@pytest.fixture()
def app():
    from pathly_orchestrator.http_server import app as flask_app

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(autouse=True)
def _streams_do_not_block(app, monkeypatch):
    """Swap each ``/events/*`` view for a stub that answers at once.

    The real views stream until the client goes away and the test client waits for their first
    chunk, so a call the gate failed to refuse would hang the run instead of failing the test.
    The stub's answer has no ``allowed`` key, so a call that reaches it fails ``_gated``.
    """
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/events/"):
            monkeypatch.setitem(
                app.view_functions, rule.endpoint, lambda **_: ("stream ran", 200)
            )


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj-a"
    root.mkdir()
    return root


@pytest.fixture()
def other_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj-b"
    root.mkdir()
    return root


def _chief(tier: str, root: Path) -> Chief:
    """A chief session of ``tier`` on ``root`` and its live token, made through the queries
    the way ``open_chief`` makes them (the spawn host is not needed to test the gate).
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries import chief as sessions
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    conn = get_db()
    run_id = "chief-" + secrets.token_hex(6)
    sessions.create_session(
        conn,
        run_id=run_id,
        project_root=str(root),
        preset=tier,
        tier=tier,
        engine="claude",
        tab_id=run_id,
        cli_session_id=None,
        hook_secret_hash=None,
        settings_dir=None,
    )
    token = mint_run_token(conn, run_id, "chief", None, str(root), "project", str(root))
    return Chief(token, run_id)


def _msg(type_, **extra) -> dict:
    body = {"feature": "demo", "from": "chief", "type": type_, "text": "hello"}
    body.update(extra)
    return body


def _gated(resp) -> bool:
    """True when this is the chief gate's own 403."""
    body = resp.get_json(silent=True) or {}
    return resp.status_code == 403 and "allowed" in body


def _passed(resp) -> bool:
    """True when the gate let the call through: the route (or Flask) answered it."""
    body = resp.get_json(silent=True) or {}
    return "allowed" not in body and resp.status_code != 401


def _count(sql: str, *params) -> int:
    from pathly_orchestrator.db.connection import get_db

    return get_db().execute(sql, params).fetchone()[0]


# --- the gate reads the body the way the route will ---------------------------------------
#
# The comms routes read the body with ``read_json_body`` (UTF-8, then cp1252, whatever the
# content type); ``/runs``, ``/runner/agent-answer``, ``/code/query`` and ``/runs/<id>/<verb>``
# read it with ``get_json``, which hands the raw bytes to ``json.loads`` (a BOM, UTF-16 and
# UTF-32 are all understood). A body only the second reader understands used to look like ``{}``
# to the gate, so the project binding never ran.

ENCODINGS = [
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-32",
    "utf-32-le",
    "utf-32-be",
]


def _send(client, path, payload, encoding, headers):
    """POST ``payload`` as plain JSON, or as JSON text in ``encoding`` (BOM, UTF-16, UTF-32)."""
    if encoding is None:
        return client.post(path, json=payload, headers=headers)
    return client.post(
        path,
        data=json.dumps(payload).encode(encoding),
        content_type="application/json",
        headers=headers,
    )


@pytest.fixture()
def started(monkeypatch):
    """Record the board runs the routes start, instead of starting any."""
    calls: list[dict] = []

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return {"ok": True, "run_id": "r-1"}

    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.board_run.start_board_run", fake
    )
    return calls


@pytest.fixture(autouse=True)
def _no_reindex(monkeypatch):
    """``/code/query`` fires a background re-index of the project it names; keep it off."""
    monkeypatch.setattr(
        "pathly_orchestrator.runner.code_context.maybe_reindex", lambda root: None
    )


@pytest.fixture(autouse=True)
def _no_code_backend(monkeypatch):
    """Resolve the code-intelligence backend to ``none``: no Serena session starts in a test."""
    monkeypatch.setattr(
        "pathly_orchestrator.runner.code_context._resolve_backend", lambda: "none"
    )


def _code_query(client, chief, project, **fields):
    body = {
        "op": "impact",
        "target": "a.py",
        "role": "architect",
        "project_root": str(project),
        **fields,
    }
    return client.post("/code/query", json=body, headers=chief.headers)


# --- a run or decompose route needs the project named -------------------------------------
#
# Left out, the routes fall back to the server's working directory, which can be another
# project. The chief names its own project on every route that starts an agent.

NAMES_A_PROJECT = [
    ("/runs", {"kind": "bogus"}),
    ("/comms/goals/run", {"goal_id": "x"}),
    ("/comms/run", {"scope": "demo"}),
    ("/comms/tasks/run", {"message_id": "x"}),
    ("/comms/goals/decompose", {"mode": "planner"}),
    ("/comms/features/decompose", {"rigor": "light"}),
    ("/comms/project/decompose", {"rigor": "bogus"}),
]


# Reads whose project filter is optional and falls back to the server's own project, or to every
# project: the chief names its project on each.
NAMES_A_PROJECT_READS = [
    "/db/features",
    "/db/stats",
    "/db/stats/trends",
    "/db/recent",
    "/db/rollup",
    "/db/features/<feature>/agents",
    "/db/features/<feature>/events",
    "/db/features/<feature>/otel",
    "/db/features/<feature>/runs",
    "/status",
    "/comms/artifacts/section",
    "/comms/artifacts/<artifact_id>/section",
]
