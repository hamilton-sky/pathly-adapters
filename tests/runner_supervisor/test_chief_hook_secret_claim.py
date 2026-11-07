"""chief-autopilot-round-two 15: the chief's hook secret is in no file, and is claimed once.

``open_chief`` writes no ``hook_secret`` file: for a claude chief the server keeps the plaintext
in memory (``supervisor/chief_secret_claim``) and stores only its sha256. Studio's main process
(a tokenless caller) claims it once with ``POST /chief/hook-secret``; a second claim closes the
chief (ticket 13, question 2 = A). The hook reads it from ``PATHLY_CHIEF_HOOK_SECRET`` in claude's
environment, so the settings deny the chief the tools that would print that environment.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys

import pytest
from chief_open_support import (
    Host,
    _no_watcher_outlives_its_test,
    chief_root,
    open_with,
    project,
)

from pathly_hooks import chief_prompt
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as chief_queries
from pathly_orchestrator.db.queries.run_tokens import mint_run_token
from pathly_orchestrator.db.secret_scan import contains_secret_hash
from pathly_orchestrator.http_server import sse
from pathly_orchestrator.runner.chief_argv import claude_settings
from pathly_orchestrator.supervisor import chief_secret_claim

ROUTE = "/chief/hook-secret"
TOKEN_HEADER = "X-Pathly-Run-Token"
ENV = "PATHLY_CHIEF_HOOK_SECRET"


@pytest.fixture()
def client(monkeypatch):
    from pathly_orchestrator.http_server import app

    monkeypatch.setattr(sse, "_broadcast_runner", Host())
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _hash(run_id: str) -> str | None:
    return chief_queries.get_session(get_db(), run_id)["hook_secret_hash"]


def _is_closed(run_id: str) -> bool:
    return chief_queries.get_session(get_db(), run_id)["closed_at"] is not None


def _files(folder):
    return [p for p in folder.rglob("*") if p.is_file()]


def test_no_file_of_the_session_and_no_spawn_payload_holds_the_secret(
    project, chief_root, client
):
    host = Host()
    run_id = open_with(project, host)["run_id"]
    stored = _hash(run_id)
    assert stored

    folder = chief_root / run_id
    assert not (folder / "hook_secret").exists()
    for path in _files(folder):
        text = path.read_text(encoding="utf-8")
        assert not contains_secret_hash(text, stored), path.name
    (_, payload), *_ = host.sent
    assert not contains_secret_hash(json.dumps(payload), stored)

    claimed = client.post(ROUTE, json={"run_id": run_id})
    assert claimed.status_code == 200, claimed.get_data(as_text=True)
    secret = claimed.get_json()["hook_secret"]
    assert secret not in json.dumps(payload)
    for path in _files(folder):
        assert secret not in path.read_text(encoding="utf-8")


def test_the_first_claim_hands_on_the_secret_whose_hash_is_stored(
    project, chief_root, client
):
    run_id = open_with(project, Host())["run_id"]

    resp = client.post(ROUTE, json={"run_id": run_id})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    secret = resp.get_json()["hook_secret"]
    assert len(secret) >= 32
    assert hashlib.sha256(secret.encode("utf-8")).hexdigest() == _hash(run_id)
    assert not _is_closed(run_id)


def test_a_second_claim_is_409_and_closes_the_chief(project, chief_root, client):
    run_id = open_with(project, Host())["run_id"]
    assert client.post(ROUTE, json={"run_id": run_id}).status_code == 200

    again = client.post(ROUTE, json={"run_id": run_id})

    assert again.status_code == 409, again.get_data(as_text=True)
    assert "hook_secret" not in again.get_json()
    assert _is_closed(run_id)
    session = chief_queries.get_session(get_db(), run_id)
    assert session["close_reason"] == "hook secret claimed twice"
    assert client.post(ROUTE, json={"run_id": run_id}).status_code == 404


def test_claim_in_the_supervisor_returns_the_secret_once(project, chief_root):
    run_id = open_with(project, Host())["run_id"]

    first = chief_secret_claim.claim(run_id)
    second = chief_secret_claim.claim(run_id)

    assert first and hashlib.sha256(first.encode()).hexdigest() == _hash(run_id)
    assert second is None
    assert _is_closed(run_id)


@pytest.mark.parametrize("role", ["builder", "chief"])
def test_a_caller_with_a_run_token_is_403(project, chief_root, client, role):
    from pathly_orchestrator.fsm_compose import resolve_board_scope

    host = Host()
    run_id = open_with(project, host)["run_id"]
    if role == "chief":
        token = host.sent[0][1]["run_token"]
    else:
        scope = resolve_board_scope("project", project, "")
        token = mint_run_token(
            get_db(), "sched-t#1", "builder", None, project, "project", scope
        )

    resp = client.post(ROUTE, json={"run_id": run_id}, headers={TOKEN_HEADER: token})

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert "hook_secret" not in (resp.get_json() or {})
    # The refusal spent nothing: the tokenless claim still gets the secret.
    assert client.post(ROUTE, json={"run_id": run_id}).status_code == 200


@pytest.mark.parametrize("run_id", ["chief-000000000000", "", None, 7, "../x"], ids=str)
def test_an_unknown_session_is_404(client, run_id):
    assert client.post(ROUTE, json={"run_id": run_id}).status_code == 404


def test_a_closed_session_is_404(project, chief_root, client):
    from pathly_orchestrator.supervisor.chief_session import close_chief

    run_id = open_with(project, Host())["run_id"]
    close_chief(run_id, "test")

    assert client.post(ROUTE, json={"run_id": run_id}).status_code == 404
    assert chief_secret_claim.claim(run_id) is None


def test_a_body_that_is_not_an_object_is_400(client):
    assert client.post(ROUTE, json=["chief-000000000000"]).status_code == 400


def test_a_codex_chief_has_no_hash_and_its_claim_is_404(project, chief_root, client):
    run_id = open_with(project, Host(), engine="codex", preset="status")["run_id"]

    assert _hash(run_id) is None
    assert list((chief_root / run_id).iterdir()) == []
    assert client.post(ROUTE, json={"run_id": run_id}).status_code == 404
    assert not _is_closed(run_id)


def test_the_settings_deny_printing_the_environment():
    deny = claude_settings("hook")["permissions"]["deny"]
    for rule in ("Bash(env*)", "Bash(printenv*)", "Read(/proc/**)"):
        assert rule in deny
    # A single leading slash anchors at the settings source; `//` is the filesystem root.
    for tool in ("Read", "Grep", "Glob"):
        assert f"{tool}(//proc/**)" in deny


def test_the_hook_command_names_no_secret_file(project, chief_root):
    run_id = open_with(project, Host())["run_id"]
    settings = json.loads((chief_root / run_id / "settings.json").read_text("utf-8"))
    command = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "--secret-file" not in command
    assert "hook_secret" not in command


def _run_hook(monkeypatch, client, run_id: str, prompt: str, session_id: str) -> int:
    """The hook as claude runs it, its post going to the real route."""

    def post(method, path, payload, **kwargs):
        resp = client.open(path, method=method, json=payload)
        return resp.get_json()

    event = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    event["session_id"] = session_id
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(event)))
    monkeypatch.setattr(chief_prompt, "_request_json", post)
    return chief_prompt.main(["--run-id", run_id, "--port", "8123"])


def _rows(run_id: str) -> list[tuple[str, str]]:
    cur = get_db().execute(
        "SELECT kind, text FROM chief_human_messages WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def test_the_hook_records_with_the_secret_in_its_environment_and_not_without(
    project, chief_root, client, monkeypatch, capsys
):
    run_id = open_with(project, Host())["run_id"]
    sid = chief_queries.get_session(get_db(), run_id)["cli_session_id"]
    secret = client.post(ROUTE, json={"run_id": run_id}).get_json()["hook_secret"]

    monkeypatch.delenv(ENV, raising=False)
    assert _run_hook(monkeypatch, client, run_id, "the style", sid) == 0
    assert _rows(run_id) == []
    assert capsys.readouterr().out == ""

    monkeypatch.setenv(ENV, secret)
    assert _run_hook(monkeypatch, client, run_id, "the style", sid) == 0
    assert _run_hook(monkeypatch, client, run_id, "use CSV", sid) == 0
    assert _rows(run_id) == [("style_prompt", "the style"), ("human", "use CSV")]
    assert "cite=" in capsys.readouterr().out

    monkeypatch.setenv(ENV, "   ")
    assert _run_hook(monkeypatch, client, run_id, "use XML", sid) == 0
    assert len(_rows(run_id)) == 2
