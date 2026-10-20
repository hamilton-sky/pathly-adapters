"""chief-agent 09: record what the human types in a claude chief tab.

``POST /chief/human-messages`` (``blueprints/chief/human.py``) stores a prompt for an open
chief session, only for a caller that holds the session's hook secret and names the session's
own claude session id; ``pathly_hooks.chief_prompt`` is the UserPromptSubmit hook the chief's
claude settings run: it posts the hook's JSON, prints the cite line for a ``human`` message and
always exits 0. ``chief_human_support.py`` opens the sessions; ``test_chief_prompt_hook.py``
holds the hook's edge cases and the real-process check.

Measured on claude 2.1.304 (learnings.md): a message another session sends into a chief reaches
the hook with its ``prompt`` wrapped in ``<cross-session-message ...>`` and a finished background
task as ``<task-notification>``; a typed prompt has no wrapper (neither has a scheduled one).
"""

from __future__ import annotations

import hashlib

import pytest
from chief_human_support import (
    RUN_ID,
    SESSION_ID,
    WRAPPED,
    FakeServer,
    _no_watcher_outlives_its_test,
    argv_for,
    body_of,
    chief_root,
    client,
    host,
    open_session,
    project,
    rows_of,
    run_hook,
    secret_file,
    stdin_of,
)

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as chief_queries
from pathly_orchestrator.supervisor.chief_session import close_chief

ROUTE = "/chief/human-messages"


def test_first_text_is_the_style_prompt_and_the_next_is_human(
    client, project, chief_root
):
    opened = open_session(project, chief_root)

    first = client.post(ROUTE, json=body_of(opened, text="pasted style"))
    second = client.post(ROUTE, json=body_of(opened, text="use CSV"))

    assert first.status_code == second.status_code == 201
    assert first.get_json()["kind"] == "style_prompt"
    assert second.get_json()["kind"] == "human"
    assert second.get_json()["id"] != first.get_json()["id"]
    assert rows_of(opened.run_id) == [
        ("style_prompt", "pasted style"),
        ("human", "use CSV"),
    ]
    stored = chief_queries.get_human_message(get_db(), second.get_json()["id"])
    assert stored["project_root"] == project


def test_wrong_secret_is_403_and_stores_nothing(client, project, chief_root):
    opened = open_session(project, chief_root)

    for secret in ("wrong", "", None, 7, opened.secret + "x", opened.secret.upper()):
        resp = client.post(ROUTE, json=body_of(opened, hook_secret=secret))
        assert resp.status_code == 403, secret
    no_secret = body_of(opened)
    del no_secret["hook_secret"]
    assert client.post(ROUTE, json=no_secret).status_code == 403
    assert rows_of(opened.run_id) == []


@pytest.mark.parametrize("session_id", [None, "", 7, ["x"], SESSION_ID])
def test_other_claude_session_is_403_and_stores_nothing(
    client, project, chief_root, session_id
):
    opened = open_session(project, chief_root)

    resp = client.post(ROUTE, json=body_of(opened, session_id=session_id))

    assert resp.status_code == 403
    assert resp.get_json() == {"error": "not this chief's claude session"}
    assert rows_of(opened.run_id) == []


def test_missing_session_id_key_is_403(client, project, chief_root):
    opened = open_session(project, chief_root)
    body = body_of(opened)
    del body["session_id"]

    resp = client.post(ROUTE, json=body)

    assert resp.status_code == 403
    assert resp.get_json() == {"error": "not this chief's claude session"}
    assert rows_of(opened.run_id) == []


@pytest.mark.parametrize(
    "stored_hash", [None, "", hashlib.sha256(b"s3cret").hexdigest()]
)
@pytest.mark.parametrize("cli_session_id", [None, "", SESSION_ID])
def test_a_session_without_a_secret_or_a_claude_session_records_nothing(
    client, project, stored_hash, cli_session_id
):
    """A codex chief has no claude session id, and a row may hold no secret hash: neither may
    be satisfied by a request that leaves the field out, empty or made up."""
    run_id = "chief-bbbbbbbbbbbb"
    chief_queries.create_session(
        get_db(),
        run_id=run_id,
        project_root=project,
        preset=None,
        tier="status",
        engine="codex",
        tab_id=run_id,
        cli_session_id=cli_session_id,
        hook_secret_hash=stored_hash,
        settings_dir=None,
    )
    complete = bool(stored_hash) and bool(cli_session_id)

    for secret in ("s3cret", "", None, "x"):
        for session_id in (SESSION_ID, "", None, "x"):
            body = {
                "run_id": run_id,
                "hook_secret": secret,
                "text": "hi",
                "session_id": session_id,
            }
            resp = client.post(ROUTE, json=body)
            if (secret, session_id) == ("s3cret", SESSION_ID) and complete:
                assert resp.status_code == 201
            else:
                assert resp.status_code == 403, (secret, session_id)
    assert rows_of(run_id) == ([("style_prompt", "hi")] if complete else [])


def test_relayed_true_stores_kind_relayed(client, project, chief_root):
    opened = open_session(project, chief_root)
    client.post(ROUTE, json=body_of(opened, text="style"))

    resp = client.post(ROUTE, json=body_of(opened, text="x", relayed=True))

    assert resp.status_code == 201
    assert resp.get_json()["kind"] == "relayed"
    assert rows_of(opened.run_id)[-1] == ("relayed", "x")


def test_closed_or_unknown_session_is_404(client, project, chief_root):
    opened = open_session(project, chief_root)
    assert close_chief(opened.run_id, "test") is True

    closed = client.post(ROUTE, json=body_of(opened))
    unknown = client.post(ROUTE, json=body_of(opened, run_id="chief-0123456789ab"))
    not_text = client.post(ROUTE, json=body_of(opened, run_id=["x"]))

    assert closed.status_code == unknown.status_code == not_text.status_code == 404
    assert rows_of(opened.run_id) == []


def test_70_kib_text_is_400_and_64_kib_is_stored(client, project, chief_root):
    opened = open_session(project, chief_root)

    too_big = client.post(ROUTE, json=body_of(opened, text="x" * (70 * 1024)))
    limit = client.post(ROUTE, json=body_of(opened, text="x" * (64 * 1024)))

    assert too_big.status_code == 400
    assert limit.status_code == 201
    assert len(rows_of(opened.run_id)) == 1


@pytest.mark.parametrize(
    "text",
    ["", "   \n", None, 5, ["a"], "\ud800", "é" * (32 * 1024 + 1)],
    ids=["empty", "blank", "null", "number", "list", "surrogate", "over 64 KiB bytes"],
)
def test_bad_text_is_400(client, project, chief_root, text):
    opened = open_session(project, chief_root)

    resp = client.post(ROUTE, json=body_of(opened, text=text))

    assert resp.status_code == 400
    assert rows_of(opened.run_id) == []


@pytest.mark.parametrize("raw", [b"", b"[1]", b"not json", b'"x"'])
def test_body_that_is_not_an_object_is_400(client, raw):
    resp = client.post(ROUTE, data=raw, content_type="application/json")

    assert resp.status_code == 400


@pytest.mark.parametrize("preset", ["status", "planner", "operator"])
def test_a_chief_token_on_the_route_is_403_at_every_tier(
    client, project, chief_root, preset
):
    """The hook holds the secret and the chief only its token: the gate refuses the route to
    the token even with a correct body, so no chief token can write a message."""
    opened = open_session(project, chief_root, preset)

    resp = client.post(
        ROUTE,
        json=body_of(opened),
        headers={"X-Pathly-Run-Token": opened.run_token},
    )

    assert resp.status_code == 403
    refusal = resp.get_json()
    assert (refusal["tier"], refusal["action"]) == (preset, None)
    assert "allowed" in refusal
    assert rows_of(opened.run_id) == []


# ── pathly_hooks.chief_prompt ────────────────────────────────────────────────────


def test_hook_posts_prompt_and_session_id_and_prints_the_id(
    monkeypatch, secret_file, capsys
):
    server = FakeServer({"id": 7, "kind": "human"})

    code = run_hook(monkeypatch, stdin_of(), server, argv_for(secret_file))

    assert code == 0
    assert capsys.readouterr().out == (
        "Pathly recorded this as human message 7; "
        "cite it with cite=7 when you relay an answer.\n"
    )
    ((method, path, payload, kwargs),) = server.calls
    assert (method, path) == ("POST", "/chief/human-messages")
    assert payload == {
        "run_id": RUN_ID,
        "hook_secret": "s3cret",
        "text": "use CSV",
        "session_id": SESSION_ID,
    }
    assert (kwargs["host"], kwargs["port"]) == ("127.0.0.1", 8123)
    assert 0 < kwargs["timeout"] <= 10


def test_hook_prints_nothing_for_the_style_prompt(monkeypatch, secret_file, capsys):
    server = FakeServer({"id": 3, "kind": "style_prompt"})

    code = run_hook(monkeypatch, stdin_of(), server, argv_for(secret_file))

    assert code == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "stdin",
    [
        "",
        "not json",
        "[]",
        "null",
        "{}",
        stdin_of(prompt=None),
        stdin_of(session_id=None),
    ],
)
def test_hook_sends_nothing_prints_nothing_and_exits_0_for_bad_stdin(
    monkeypatch, secret_file, capsys, stdin
):
    server = FakeServer({"id": 1, "kind": "human"})

    code = run_hook(monkeypatch, stdin, server, argv_for(secret_file))

    assert code == 0
    assert server.calls == []
    assert capsys.readouterr().out == ""


def test_hook_exits_0_and_prints_nothing_when_the_post_raises(
    monkeypatch, secret_file, capsys
):
    server = FakeServer(error=ConnectionRefusedError("refused"))

    code = run_hook(monkeypatch, stdin_of(), server, argv_for(secret_file))

    assert code == 0
    assert len(server.calls) == 1
    assert capsys.readouterr().out == ""


def test_hook_sends_relayed_for_a_cross_session_message(
    monkeypatch, secret_file, capsys
):
    server = FakeServer({"id": 4, "kind": "relayed"})

    code = run_hook(
        monkeypatch, stdin_of(prompt=WRAPPED), server, argv_for(secret_file)
    )

    assert code == 0
    payload = server.calls[0][2]
    assert payload["relayed"] is True
    assert payload["text"] == WRAPPED
    assert capsys.readouterr().out == ""
