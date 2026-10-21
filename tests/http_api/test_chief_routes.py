"""chief-agent 07: POST /chief/open, POST /chief/close and GET /chief/session.

The routes are a thin layer over ``supervisor/chief_session.py`` (ticket 06): they refuse an
agent run, turn its exceptions into 400 / 409, hand ``open_chief`` the runner broadcaster and,
on close, tell the spawn host to kill the tab. A fake broadcaster stands in for the spawn host
(it only records what it is sent), swapped in by replacing ``sse._broadcast_runner``, the name
the routes import when they run.

``chief_startup_cleanup`` is what ``app.main()`` calls before the server serves: a chief that
was open when the last process died has no watcher left, so its token must not outlive it.

The tests never patch the global ``time.sleep`` (the WAL checkpoint daemon shares it); a chief
a test leaves open has a watcher thread, which is closed while the test's DB is still patched.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from _paths import SRC

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as chief_queries
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, resolve_run_token
from pathly_orchestrator.http_server import sse
from pathly_orchestrator.supervisor import chief_session
from pathly_orchestrator.supervisor.chief_session import close_chief

PROMPT = "---\ntier: operator\n---\nYou are the chief of this project."
RUN_ID = re.compile(r"chief-[0-9a-f]{12}")


class Host:
    """The spawn host's side of the contract: it only records what it was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def __call__(self, topic: str, payload: dict) -> None:
        self.sent.append((topic, payload))

    def of_type(self, kind: str) -> list[dict]:
        return [p for _, p in self.sent if p.get("type") == kind]

    @property
    def spawn(self) -> dict:
        spawns = self.of_type("TERMINAL_SPAWN")
        assert len(spawns) == 1, self.sent
        return spawns[0]


@pytest.fixture()
def host(monkeypatch: pytest.MonkeyPatch) -> Host:
    fake = Host()
    monkeypatch.setattr(sse, "_broadcast_runner", fake)
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8123")
    return fake


@pytest.fixture()
def client(host: Host):
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _no_watcher_outlives_its_test():
    """A chief a test leaves open has a watcher waiting; close it while this test's DB and
    sessions folder are still patched in, so it cannot wake up in a later test."""
    yield
    prefix = "chief-watch-"
    for thread in threading.enumerate():
        if thread.name.startswith(prefix):
            close_chief(thread.name[len(prefix) :], "test over")
    assert _wait(
        lambda: not [t for t in threading.enumerate() if t.name.startswith(prefix)]
    )


@pytest.fixture()
def project(tmp_path: Path) -> str:
    root = tmp_path / "proj"
    root.mkdir()
    return str(root)


def _wait(done, seconds: float = 5.0) -> bool:
    """A bounded poll on the monotonic clock (not a patched sleep)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if done():
            return True
        time.sleep(0.01)
    return done()


def _body(project: str, **overrides) -> dict:
    body = {
        "project_root": project,
        "engine": "claude",
        "preset": "operator",
        "prompt": PROMPT,
    }
    body.update(overrides)
    return body


def _open(client, project: str, **overrides):
    return client.post("/chief/open", json=_body(project, **overrides))


def _session(client, project: str) -> dict:
    response = client.get("/chief/session", query_string={"project_root": project})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _builder_token() -> str:
    return mint_run_token(
        get_db(), "run-builder", "builder", "feat", "/tmp/p", "feature", "feat"
    )


def _no_session(project: str) -> bool:
    return chief_queries.open_session_for_project(get_db(), project) is None


# ── POST /chief/open ─────────────────────────────────────────────────────────────


def test_open_returns_201_with_the_operator_tier_and_sends_one_terminal_spawn(
    client, host: Host, project: str
):
    response = _open(client, project)
    assert response.status_code == 201, response.get_json()
    result = response.get_json()
    assert RUN_ID.fullmatch(result["run_id"])
    assert result == {
        "run_id": result["run_id"],
        "tab_id": result["run_id"],
        "tier": "operator",
        "engine": "claude",
    }

    assert len(host.sent) == 1
    topic, payload = host.sent[0]
    assert topic == "chief:" + result["run_id"]
    assert payload["type"] == "TERMINAL_SPAWN"
    assert payload["run_id"] == result["run_id"]
    assert payload["tab_id"] == result["tab_id"]
    assert payload["interactive"] is True
    assert payload["submit"] is False
    assert resolve_run_token(get_db(), payload["run_token"])["role"] == "chief"


def test_a_second_open_for_the_project_is_409_with_the_first_run_id(
    client, host: Host, project: str
):
    first = _open(client, project).get_json()

    second = _open(client, project)
    assert second.status_code == 409
    body = second.get_json()
    assert body["run_id"] == first["run_id"]
    assert body["tab_id"] == first["tab_id"]
    assert body["error"]
    assert set(body) == {"error", "run_id", "tab_id"}
    assert len(host.of_type("TERMINAL_SPAWN")) == 1


def test_a_trailing_slash_does_not_get_a_second_chief_for_the_same_project(
    client, host: Host, project: str
):
    first = _open(client, project).get_json()

    second = _open(client, project + "/")
    assert second.status_code == 409
    assert second.get_json()["run_id"] == first["run_id"]
    assert len(host.of_type("TERMINAL_SPAWN")) == 1


def test_a_project_opened_with_a_trailing_slash_is_found_without_one(
    client, host: Host, project: str
):
    opened = _open(client, project + "/").get_json()

    assert _session(client, project)["run_id"] == opened["run_id"]
    assert _open(client, project).status_code == 409


def test_open_with_a_live_builder_token_is_403_and_opens_nothing(
    client, host: Host, project: str
):
    response = client.post(
        "/chief/open",
        json=_body(project),
        headers={"X-Pathly-Run-Token": _builder_token()},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]
    assert host.sent == []
    assert _no_session(project)


def test_open_with_a_revoked_or_unknown_token_is_not_refused_as_an_agent(
    client, host: Host, project: str
):
    response = client.post(
        "/chief/open",
        json=_body(project),
        headers={"X-Pathly-Run-Token": "not-a-token"},
    )
    assert response.status_code == 201, response.get_json()


def test_open_with_engine_copilot_is_400_and_names_the_supported_engines(
    client, host: Host, project: str
):
    response = _open(client, project, engine="copilot")
    assert response.status_code == 400
    message = response.get_json()["error"]
    assert "claude" in message and "codex" in message
    assert host.sent == []
    assert _no_session(project)


def test_open_passes_on_the_message_of_a_value_error(
    client, host: Host, tmp_path: Path
):
    missing = str(tmp_path / "no-such-dir")
    response = _open(client, missing)
    assert response.status_code == 400
    assert "project_root" in response.get_json()["error"]
    assert host.sent == []


@pytest.mark.parametrize("field", ["project_root", "engine", "preset", "prompt"])
def test_open_with_a_missing_field_is_400_naming_it(
    client, host: Host, project: str, field: str
):
    body = _body(project)
    del body[field]
    response = client.post("/chief/open", json=body)
    assert response.status_code == 400
    assert field in response.get_json()["error"]
    assert host.sent == []


@pytest.mark.parametrize(
    "field", ["project_root", "engine", "preset", "prompt", "model"]
)
@pytest.mark.parametrize("value", [None, 7, ["x"], {"a": 1}, True])
def test_open_with_a_field_that_is_not_a_string_is_400_naming_it(
    client, host: Host, project: str, field: str, value
):
    response = _open(client, project, **{field: value})
    assert response.status_code == 400
    assert field in response.get_json()["error"]
    assert host.sent == []
    assert _no_session(project)


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", ""])
def test_open_with_a_body_that_is_not_a_json_object_is_400(
    client, host: Host, raw: str
):
    response = client.post("/chief/open", data=raw, content_type="application/json")
    assert response.status_code == 400
    assert host.sent == []


def test_open_passes_the_model_on_to_the_argv(client, host: Host, project: str):
    response = _open(client, project, model="opus")
    assert response.status_code == 201, response.get_json()
    assert host.spawn["argv"][-2:] == ["--model", "opus"]


# ── GET /chief/session ───────────────────────────────────────────────────────────


def test_session_is_not_open_before_a_chief_is(client, project: str):
    assert _session(client, project) == {"open": False}


def test_session_shows_the_open_chief(client, host: Host, project: str):
    opened = _open(client, project).get_json()

    session = _session(client, project)
    assert session == {
        "open": True,
        "run_id": opened["run_id"],
        "tab_id": opened["tab_id"],
        "tier": "operator",
        "engine": "claude",
        "opened_at": session["opened_at"],
        "runs_started": 0,
        "max_runs_per_session": 20,
        "max_cost_usd_per_run": 10.0,
    }
    row = chief_queries.get_session(get_db(), opened["run_id"])
    assert session["opened_at"] == row["opened_at"]


def test_session_of_another_project_is_not_open(
    client, host: Host, project: str, tmp_path: Path
):
    _open(client, project)
    other = tmp_path / "other"
    other.mkdir()

    assert _session(client, str(other)) == {"open": False}


@pytest.mark.parametrize("query", [{}, {"project_root": ""}])
def test_session_without_a_project_root_is_400(client, query: dict):
    response = client.get("/chief/session", query_string=query)
    assert response.status_code == 400
    assert "project_root" in response.get_json()["error"]


# ── POST /chief/close ────────────────────────────────────────────────────────────


def test_close_ends_the_session_revokes_the_token_and_kills_the_tab(
    client, host: Host, project: str
):
    opened = _open(client, project).get_json()
    token = host.spawn["run_token"]
    assert resolve_run_token(get_db(), token) is not None

    response = client.post("/chief/close", json={"project_root": project})
    assert response.status_code == 200
    assert response.get_json() == {"closed": True}

    assert _session(client, project) == {"open": False}
    assert resolve_run_token(get_db(), token) is None
    row = chief_queries.get_session(get_db(), opened["run_id"])
    assert row["close_reason"] == "closed from Studio"
    assert row["closed_at"] is not None

    kills = host.of_type("TERMINAL_KILL")
    assert kills == [
        {
            "type": "TERMINAL_KILL",
            "tab_id": opened["tab_id"],
            "run_id": opened["run_id"],
        }
    ]
    assert host.sent[-1][1] is kills[0]


def test_close_removes_the_session_folder(client, host: Host, project: str):
    opened = _open(client, project).get_json()
    folder = chief_session._chief_root() / opened["run_id"]
    assert folder.is_dir()

    client.post("/chief/close", json={"project_root": project})

    assert not folder.exists()


def test_close_with_a_trailing_slash_closes_the_same_session(
    client, host: Host, project: str
):
    _open(client, project)

    response = client.post("/chief/close", json={"project_root": project + "/"})
    assert response.get_json() == {"closed": True}
    assert _session(client, project) == {"open": False}


def test_close_with_nothing_open_is_closed_false_and_kills_nothing(
    client, host: Host, project: str
):
    response = client.post("/chief/close", json={"project_root": project})
    assert response.status_code == 200
    assert response.get_json() == {"closed": False}
    assert host.sent == []


def test_a_second_close_is_closed_false_and_kills_the_tab_once(
    client, host: Host, project: str
):
    _open(client, project)
    assert client.post("/chief/close", json={"project_root": project}).get_json() == {
        "closed": True
    }

    again = client.post("/chief/close", json={"project_root": project})
    assert again.status_code == 200
    assert again.get_json() == {"closed": False}
    assert len(host.of_type("TERMINAL_KILL")) == 1


def test_close_does_not_touch_another_projects_chief(
    client, host: Host, project: str, tmp_path: Path
):
    _open(client, project)
    other = tmp_path / "other"
    other.mkdir()

    response = client.post("/chief/close", json={"project_root": str(other)})
    assert response.get_json() == {"closed": False}
    assert _session(client, project)["open"] is True


def test_close_with_a_live_run_token_is_403_and_closes_nothing(
    client, host: Host, project: str
):
    _open(client, project)

    response = client.post(
        "/chief/close",
        json={"project_root": project},
        headers={"X-Pathly-Run-Token": _builder_token()},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]
    assert _session(client, project)["open"] is True
    assert host.of_type("TERMINAL_KILL") == []


@pytest.mark.parametrize("value", [None, 7, ["x"], ""])
def test_close_without_a_string_project_root_is_400(client, host: Host, value):
    response = client.post("/chief/close", json={"project_root": value})
    assert response.status_code == 400
    assert "project_root" in response.get_json()["error"]


def test_close_with_a_body_that_is_not_a_json_object_is_400(client, host: Host):
    response = client.post("/chief/close", data="[1]", content_type="application/json")
    assert response.status_code == 400


def test_a_project_can_open_a_new_chief_after_closing_the_old_one(
    client, host: Host, project: str
):
    first = _open(client, project).get_json()
    client.post("/chief/close", json={"project_root": project})

    second = _open(client, project)
    assert second.status_code == 201, second.get_json()
    assert second.get_json()["run_id"] != first["run_id"]


# ── chief_startup_cleanup ────────────────────────────────────────────────────────


def test_startup_cleanup_closes_an_open_session_and_revokes_its_token(
    client, host: Host, project: str
):
    opened = _open(client, project).get_json()
    token = host.spawn["run_token"]
    folder = chief_session._chief_root() / opened["run_id"]
    assert resolve_run_token(get_db(), token) is not None
    assert folder.is_dir()

    closed = chief_session.chief_startup_cleanup()

    assert closed == [opened["run_id"]]
    assert _session(client, project) == {"open": False}
    assert resolve_run_token(get_db(), token) is None
    row = chief_queries.get_session(get_db(), opened["run_id"])
    assert row["close_reason"] == "server restart"
    assert not folder.exists()


def test_startup_cleanup_with_nothing_open_closes_nothing(client, host: Host):
    assert chief_session.chief_startup_cleanup() == []


def test_startup_cleanup_leaves_a_session_that_is_already_closed_alone(
    client, host: Host, project: str
):
    opened = _open(client, project).get_json()
    client.post("/chief/close", json={"project_root": project})

    assert chief_session.chief_startup_cleanup() == []
    row = chief_queries.get_session(get_db(), opened["run_id"])
    assert row["close_reason"] == "closed from Studio"


def test_startup_cleanup_never_removes_a_folder_outside_the_sessions_root():
    chief_session._chief_root().mkdir(parents=True)
    outside = chief_session._chief_root().parent / "keep"
    outside.mkdir()
    chief_queries.create_session(
        get_db(),
        run_id="../keep",
        project_root="/odd",
        preset=None,
        tier="status",
        engine="claude",
        tab_id=None,
        cli_session_id=None,
        hook_secret_hash=None,
        settings_dir=None,
    )

    assert chief_session.chief_startup_cleanup() == ["../keep"]
    assert chief_queries.open_session_for_project(get_db(), "/odd") is None
    assert outside.is_dir()


# ── app.main() calls the cleanup before the server serves ────────────────────────

# main() resets the root logger, the middleware globals and starts threads, so it runs in its
# own process with its own home: a stale session is seeded, main() runs with Flask's run()
# replaced by a recorder, and the script reports what is left.
MAIN_SCRIPT = """
import importlib, json, sys
app_module = importlib.import_module("pathly_orchestrator.http_server.app")
import pathly_orchestrator.runner.embeddings as embeddings
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as queries
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, resolve_run_token
from pathly_orchestrator.supervisor import chief_session

embeddings.warm = lambda: None
served = []
app_module.app.run = lambda *a, **k: served.append(True)

conn = get_db()
queries.create_session(
    conn, run_id="chief-0123456789ab", project_root="/p", preset="status", tier="status",
    engine="claude", tab_id="chief-0123456789ab", cli_session_id=None,
    hook_secret_hash=None, settings_dir=None,
)
token = mint_run_token(conn, "chief-0123456789ab", "chief", None, "/p", "project", "/p")
if sys.argv[1] == "fail":
    def explode():
        raise RuntimeError("cleanup exploded")
    chief_session.chief_startup_cleanup = explode
app_module.main()
print(json.dumps({
    "served": bool(served),
    "open": queries.open_session_for_project(conn, "/p") is not None,
    "token_live": resolve_run_token(conn, token) is not None,
}))
"""


def _run_main(tmp_path: Path, mode: str) -> tuple[dict, str]:
    home = tmp_path / "main-home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": str(SRC),
    }
    done = subprocess.run(
        [sys.executable, "-c", MAIN_SCRIPT, mode],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1]), done.stderr


def test_main_closes_a_session_the_last_process_left_open_before_serving(tmp_path):
    report, _ = _run_main(tmp_path, "ok")
    assert report == {"served": True, "open": False, "token_live": False}


def test_main_still_serves_when_the_chief_cleanup_fails(tmp_path):
    report, stderr = _run_main(tmp_path, "fail")
    assert report == {"served": True, "open": True, "token_live": True}
    assert "chief startup cleanup failed" in stderr
