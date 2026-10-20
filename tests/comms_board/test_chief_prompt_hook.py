"""chief-agent 09: the chief's UserPromptSubmit hook, its edge cases and as a real process.

``test_chief_human_messages.py`` holds the cases the ticket lists. Here: which prompts count as
not typed by the human (the ``<cross-session-message`` and ``<task-notification`` wrappers
measured on claude 2.1.304; the notification text is the shape claude delivers when a background
task ends, and its summary holds words the chief chose), what the hook does with an odd server
reply, bad arguments, every kind of error and a stdout nobody reads, and the hook command
``open_chief`` wrote into ``settings.json`` run as a real process against a real server thread
(and with nothing listening).
"""

from __future__ import annotations

import http.server
import json
import os
import shlex
import socket
import subprocess
import sys
import threading
from pathlib import Path
from urllib.error import URLError

import pytest
from _paths import SRC
from chief_human_support import (
    FAILED_NOTIFICATION,
    SESSION_ID,
    STALL_NOTIFICATION,
    TASK_NOTIFICATION,
    TIMEOUT_NOTIFICATION,
    WRAPPED,
    FakeServer,
    _no_watcher_outlives_its_test,
    argv_for,
    chief_root,
    open_session,
    project,
    rows_of,
    run_hook,
    secret_file,
    stdin_of,
)

from pathly_orchestrator.db import get_db


@pytest.mark.parametrize(
    "prompt",
    [
        WRAPPED,
        "  \n" + WRAPPED,
        "typed first\n" + WRAPPED,
        WRAPPED + "\ntyped after",
        "<cross-session-message>\nhi\n</cross-session-message>",
    ],
    ids=["exact", "leading blank", "text before", "text after", "no attributes"],
)
def test_the_marker_anywhere_in_the_prompt_marks_it_relayed(
    monkeypatch, secret_file, prompt
):
    server = FakeServer({"id": 4, "kind": "relayed"})

    run_hook(monkeypatch, stdin_of(prompt=prompt), server, argv_for(secret_file))

    assert server.calls[0][2]["relayed"] is True


@pytest.mark.parametrize(
    "prompt",
    [
        TASK_NOTIFICATION,
        FAILED_NOTIFICATION,
        TIMEOUT_NOTIFICATION,
        STALL_NOTIFICATION,
        "  \n" + TASK_NOTIFICATION,
        "typed first\n" + TASK_NOTIFICATION,
        TASK_NOTIFICATION + "\ntyped after",
        "<task-notification>\n</task-notification>",
    ],
    ids=[
        "completed",
        "failed",
        "timeout",
        "stall",
        "leading blank",
        "text before",
        "text after",
        "no fields",
    ],
)
def test_a_background_task_notification_is_marked_relayed(
    monkeypatch, secret_file, capsys, prompt
):
    """The chief picks the words in <summary>, so claude's own message must never pass as typed."""
    server = FakeServer({"id": 4, "kind": "relayed"})

    code = run_hook(monkeypatch, stdin_of(prompt=prompt), server, argv_for(secret_file))

    assert code == 0
    assert server.calls[0][2]["relayed"] is True
    assert server.calls[0][2]["text"] == prompt
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "prompt",
    [
        "use CSV",
        "what is a cross-session message?",
        "<cross-session notes",
        "<b>x</b>",
        "what does a task-notification mean?",
        "<task-notes>keep</task-notes>",
        "<tasks>3</tasks>",
    ],
)
def test_a_typed_prompt_is_not_marked_relayed(monkeypatch, secret_file, prompt):
    server = FakeServer({"id": 4, "kind": "human"})

    run_hook(monkeypatch, stdin_of(prompt=prompt), server, argv_for(secret_file))

    assert "relayed" not in server.calls[0][2]


@pytest.mark.parametrize(
    "stdin",
    ['"x"', stdin_of(prompt=""), stdin_of(prompt=7), stdin_of(session_id=7)]
    + [stdin_of(session_id=""), '{"prompt": ["a"], "session_id": "s"}'],
)
def test_more_bad_stdin_sends_nothing(monkeypatch, secret_file, capsys, stdin):
    server = FakeServer({"id": 1, "kind": "human"})

    code = run_hook(monkeypatch, stdin, server, argv_for(secret_file))

    assert code == 0
    assert server.calls == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "error",
    [
        OSError("down"),
        TimeoutError("slow"),
        URLError("no route"),
        RuntimeError("fsm-call error (403): not this chief's claude session"),
        ValueError("not json"),
        KeyError("x"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_every_kind_of_post_error_is_swallowed(monkeypatch, secret_file, capsys, error):
    code = run_hook(
        monkeypatch, stdin_of(), FakeServer(error=error), argv_for(secret_file)
    )

    assert code == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "reply",
    [None, [], {}, {"id": "x"}, {"kind": "human"}, "ok", 5, {"id": 2, "kind": 9}],
)
def test_an_odd_reply_prints_nothing(monkeypatch, secret_file, capsys, reply):
    code = run_hook(monkeypatch, stdin_of(), FakeServer(reply), argv_for(secret_file))

    assert code == 0
    assert capsys.readouterr().out == ""


def test_a_relayed_reply_prints_nothing(monkeypatch, secret_file, capsys):
    server = FakeServer({"id": 9, "kind": "relayed"})

    code = run_hook(monkeypatch, stdin_of(), server, argv_for(secret_file))

    assert code == 0
    assert capsys.readouterr().out == ""


class _ClosedStdout:
    """A stdout whose reader has gone away."""

    def write(self, text):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


def test_a_closed_stdout_still_exits_0(monkeypatch, secret_file):
    server = FakeServer({"id": 9, "kind": "human"})
    monkeypatch.setattr(sys, "stdout", _ClosedStdout())

    code = run_hook(monkeypatch, stdin_of(), server, argv_for(secret_file))

    assert code == 0
    assert len(server.calls) == 1


def test_bad_arguments_and_a_missing_secret_file_exit_0(monkeypatch, tmp_path, capsys):
    server = FakeServer({"id": 1, "kind": "human"})
    nope = tmp_path / "nope"
    missing = ["--run-id", "chief-a", "--secret-file", str(nope), "--port", "8123"]

    for argv in ([], ["--port", "x"], ["--bogus"], missing):
        assert run_hook(monkeypatch, stdin_of(), server, argv) == 0

    assert server.calls == []
    assert capsys.readouterr().out == ""


# ── the hook command open_chief wrote, as a real process ─────────────────────────


def _hook_process(command: str, stdin: str, home: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PATHLY_API_SECRET"}
    env.update(PYTHONPATH=str(SRC), HOME=str(home), USERPROFILE=str(home))
    return subprocess.run(
        shlex.split(command),
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_the_written_hook_command_records_over_http(
    tmp_path, project, chief_root, monkeypatch
):
    from werkzeug.serving import make_server

    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", str(server.server_port))
        opened = open_session(project, chief_root)
        settings = json.loads(
            (chief_root / opened.run_id / "settings.json").read_text()
        )
        command = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        sid = opened.cli_session_id

        style = _hook_process(command, stdin_of("the style", sid), tmp_path)
        typed = _hook_process(command, stdin_of("use CSV", sid), tmp_path)
        wrapped = _hook_process(command, stdin_of(WRAPPED, sid), tmp_path)
        notified = _hook_process(command, stdin_of(TASK_NOTIFICATION, sid), tmp_path)
        foreign = _hook_process(command, stdin_of("use XML", SESSION_ID), tmp_path)
    finally:
        server.shutdown()
        thread.join(timeout=10)

    runs = (style, typed, wrapped, notified, foreign)
    assert [p.returncode for p in runs] == [0] * 5, [p.stderr for p in runs]
    rows = rows_of(opened.run_id)
    assert [kind for kind, _ in rows] == ["style_prompt", "human", "relayed", "relayed"]
    assert rows[1][1] == "use CSV"
    assert rows[3][1] == TASK_NOTIFICATION
    human = (
        get_db()
        .execute(
            "SELECT id FROM chief_human_messages WHERE run_id = ? AND kind = 'human'",
            (opened.run_id,),
        )
        .fetchone()[0]
    )
    assert typed.stdout == (
        f"Pathly recorded this as human message {human}; "
        f"cite it with cite={human} when you relay an answer.\n"
    )
    assert (style.stdout, wrapped.stdout, notified.stdout, foreign.stdout) == ("",) * 4


def test_the_module_is_silent_and_exits_0_when_nothing_listens(tmp_path, secret_file):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command = (
        f"{shlex.quote(sys.executable)} -m pathly_hooks.chief_prompt"
        f" --run-id chief-aaaaaaaaaaaa --secret-file {shlex.quote(str(secret_file))}"
        f" --port {port}"
    )

    done = _hook_process(command, stdin_of(), tmp_path)

    assert done.returncode == 0, done.stderr
    assert done.stdout == ""


class _CannedReply(http.server.BaseHTTPRequestHandler):
    """Answers every POST with a stored ``human`` message, as the real route would."""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        body = json.dumps({"id": 7, "kind": "human"}).encode()
        self.send_response(201)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


@pytest.mark.parametrize("unbuffered", ["", "1"], ids=["buffered", "unbuffered"])
def test_the_module_exits_0_when_nobody_reads_its_stdout(
    tmp_path, secret_file, unbuffered
):
    """A hook whose stdout pipe has no reader prints into the void and still exits 0."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CannedReply)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    env.update(PYTHONPATH=str(SRC), HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    if unbuffered:
        env["PYTHONUNBUFFERED"] = unbuffered
    argv = [sys.executable, "-m", "pathly_hooks.chief_prompt"] + argv_for(secret_file)
    argv[argv.index("--port") + 1] = str(server.server_port)
    try:
        child = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        child.stdout.close()
        child.stdin.write(stdin_of().encode("utf-8"))
        child.stdin.close()
        code = child.wait(timeout=60)
        stderr = child.stderr.read().decode("utf-8", "replace")
        child.stderr.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)

    assert code == 0, stderr
    assert stderr == ""
