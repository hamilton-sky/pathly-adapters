"""chief-agent 17, round 2: input to `pathly api` that is not valid text, and the server secret.

* A body, a path or a standard input that is not valid UTF-8 is a usage error (exit 2, nothing
  sent), never a traceback: ``pathly api POST /x $'{"a":"\\xff"}'`` and ``printf '\\xff{}' |
  pathly api POST /x -`` used to die with a UnicodeError and exit 1, the code that means "the
  server answered with an error or is not there".
* The server secret is read once per command and, like the run token, never printed: not in the
  answer, and not in the text of a connection error either.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from _paths import SRC
from chief_cli_support import pathly, stub

NOT_UTF8 = os.fsdecode(b'{"a":"\xff"}')


def _no_traceback(ran) -> None:
    assert "Traceback" not in ran.err, ran


def test_a_body_argument_that_is_not_valid_utf8_is_a_usage_error_and_sends_nothing(
    stub, pathly
):
    assert "\udcff" in NOT_UTF8

    ran = pathly("api", "POST", "/comms/post", NOT_UTF8, token="tok")

    assert ran.code == 2, ran
    assert ran.out == ""
    assert "UTF-8" in ran.err and "usage: pathly" in ran.err
    _no_traceback(ran)
    assert stub.got == []


def test_a_path_that_is_not_valid_utf8_is_a_usage_error_and_sends_nothing(stub, pathly):
    ran = pathly(
        "api", "GET", "/runs?project_root=/home/" + os.fsdecode(b"\xff"), token="tok"
    )

    assert ran.code == 2, ran
    assert "UTF-8" in ran.err
    _no_traceback(ran)
    assert stub.got == []


def test_a_standard_input_that_is_not_valid_utf8_is_a_usage_error_and_sends_nothing(
    stub, pathly
):
    ran = pathly("api", "POST", "/comms/post", "-", token="tok", stdin=b"\xff{}")

    assert ran.code == 2, ran
    assert ran.out == ""
    assert "UTF-8" in ran.err and "usage: pathly" in ran.err
    _no_traceback(ran)
    assert stub.got == []


def test_a_standard_input_that_is_valid_utf8_still_goes_through_as_it_is(stub, pathly):
    given = '{"text": "café"}'

    ran = pathly(
        "api", "POST", "/comms/post", "-", token="tok", stdin=given.encode("utf-8")
    )

    assert ran.code == 0, ran
    assert stub.got[0]["body"] == given.encode("utf-8")


def _process(
    args: list[str], stdin: bytes, port: int, tmp_path
) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PATHLY_")}
    env.update(
        PYTHONPATH=str(SRC),
        HOME=str(tmp_path),
        USERPROFILE=str(tmp_path),
        PATHLY_FSM_HTTP_PORT=str(port),
        PATHLY_RUN_TOKEN="tok",
    )
    return subprocess.run(
        [sys.executable, "-m", "pathly_orchestrator.chief_cli", *args],
        input=stdin,
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize(
    "args,stdin",
    [
        pytest.param(["api", "POST", "/x", NOT_UTF8], b"", id="argument"),
        pytest.param(["api", "POST", "/x", "-"], b"\xff{}", id="standard-input"),
    ],
)
def test_the_two_commands_that_used_to_traceback_exit_2_as_a_process(
    stub, tmp_path, args, stdin
):
    port = int(os.environ["PATHLY_FSM_HTTP_PORT"])

    done = _process(args, stdin, port, tmp_path)

    assert done.returncode == 2, done
    assert b"Traceback" not in done.stderr
    assert b"UTF-8" in done.stderr
    assert stub.got == []


# --- the server secret ----------------------------------------------------------------------


def test_an_error_that_holds_the_server_secret_is_printed_without_it(
    pathly, monkeypatch
):
    from pathly_orchestrator import chief_cli

    monkeypatch.setenv("PATHLY_API_SECRET", "the-server-secret-9876")

    def refuse(*_args):
        raise OSError("refused for the-server-secret-9876 and tok-in-error")

    monkeypatch.setattr(chief_cli, "_send", refuse)

    ran = pathly("api", "GET", "/comms", token="tok-in-error")

    assert ran.code == 1, ran
    assert "refused for" in ran.err
    assert "the-server-secret-9876" not in ran.err + ran.out
    assert "tok-in-error" not in ran.err + ran.out


def test_an_answer_that_holds_the_server_secret_is_printed_without_it(
    stub, pathly, monkeypatch
):
    monkeypatch.setenv("PATHLY_API_SECRET", "the-server-secret-9876")
    stub.body = b'{"echo": "the-server-secret-9876"}'

    ran = pathly("api", "GET", "/comms", token="tok")

    assert ran.code == 0
    assert "the-server-secret-9876" not in ran.out + ran.err
    assert "[redacted]" in ran.out


@pytest.mark.parametrize("reachable", [True, False], ids=["answered", "unreachable"])
def test_the_server_secret_is_read_once_per_command(
    stub, pathly, monkeypatch, reachable
):
    from pathly_orchestrator import chief_cli

    reads: list[int] = []

    def counted() -> str:
        reads.append(1)
        return "the-server-secret-9876"

    monkeypatch.setattr(chief_cli, "_load_secret", counted)
    if not reachable:
        monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "1")

    ran = pathly("api", "GET", "/comms", token="tok")

    assert ran.code == (0 if reachable else 1), ran
    assert len(reads) == 1
    if reachable:
        assert stub.got[0]["headers"]["x-pathly-secret"] == "the-server-secret-9876"
