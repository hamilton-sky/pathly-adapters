"""chief-agent 20, B3 to B5: `pathly api` never ends in a traceback, reads and prints a bounded
amount, and `pathly help` lists the acknowledge route.

* B3: a token or server secret `http.client` refuses as a header value (a newline, a character
  outside latin-1), and a body nested deep enough to overflow the JSON parser, were tracebacks and
  exit 1 (the code for "the server answered with an error or is not there"). Each is now exit 2,
  nothing sent, one line that names the problem and never the value.
* B4: a body read from standard input over 1 MiB is a usage error; an answer is read only up to
  256 KiB (the read itself bounded) and what was cut is said on stderr. The exit code still
  follows the status.
* B5: `POST /comms/acknowledge` is the way an operator chief closes an escalation addressed to
  the human, so the help lists it, with the keys the gate lets through.
"""

from __future__ import annotations

import http.client
import io
import json
import re
import sys
from pathlib import Path

import pytest
from chief_cite_support import (
    Session,
    _demo_is_a_feature_of_the_chiefs_project,
    acknowledged_by,
    later,
    post_row,
)
from chief_cli_support import (
    NO_TOKEN,
    _no_watcher_outlives_its_test,
    pathly,
    server,
    stub,
)
from chief_gate_support import project

from pathly_orchestrator import chief_cli

MAX_BODY = 1_048_576
MAX_ANSWER = 262_144
TOKEN = "tok-SECRETVALUE_123"
OBJECT = '{"text": "hello"}'


def _sent_nothing(ran, stub) -> None:
    assert ran.code == 2, ran
    assert ran.out == ""
    assert "Traceback" not in ran.err, ran
    assert stub.got == []


# --- B3: a header value that cannot be sent ------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    ["tok-SECRETVALUE\nX-Evil: 1", "tok-SECRETVALUE\r\n", "tok-SECRET€VALUE", "日本語"],
    ids=["newline", "crlf", "euro-sign", "cjk"],
)
def test_a_token_a_header_cannot_carry_is_a_usage_error_that_never_shows_it(
    stub, pathly, token
):
    ran = pathly("api", "POST", "/comms/post", OBJECT, token=token + "x")

    _sent_nothing(ran, stub)
    assert ran.err.strip().splitlines() == [
        "pathly: PATHLY_RUN_TOKEN holds a character an HTTP header cannot carry"
    ]
    assert "SECRET" not in ran.err and "Evil" not in ran.err


@pytest.mark.parametrize(
    "secret",
    ["hide-me\nrest", "hide-me\rrest", "hide-me\u20acrest", "hide-me日本語"],
    ids=["newline", "carriage-return", "euro-sign", "cjk"],
)
def test_a_server_secret_a_header_cannot_carry_is_a_usage_error_that_never_shows_it(
    stub, pathly, monkeypatch, secret
):
    monkeypatch.setenv("PATHLY_API_SECRET", secret)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    _sent_nothing(ran, stub)
    assert ran.err.strip().splitlines() == [
        "pathly: the server secret holds a character an HTTP header cannot carry"
    ]
    assert "hide-me" not in ran.err


def test_a_secret_file_that_is_not_text_is_a_usage_error_not_a_traceback(stub, pathly):
    secret_file = Path.home() / ".pathly" / "server_secret.txt"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_bytes(b"\xff\xfe\x80 not utf-8")

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    _sent_nothing(ran, stub)
    assert ran.err.strip().splitlines() == [
        "pathly: the server secret cannot be read as text"
    ]


def test_an_ordinary_token_and_secret_and_a_latin_1_letter_are_sent_as_before(
    stub, pathly, monkeypatch
):
    monkeypatch.setenv("PATHLY_API_SECRET", "s3cr3t-é-value")

    ran = pathly("api", "POST", "/comms/post", OBJECT, token="tok-abc_DEF-123")

    assert ran.code == 0, ran
    headers = stub.got[0]["headers"]
    assert headers["x-pathly-run-token"] == "tok-abc_DEF-123"
    assert headers["x-pathly-secret"] == "s3cr3t-é-value"
    assert stub.got[0]["body"] == OBJECT.encode()


DEEP = '{"a": ' + "[" * 20_000 + "]" * 20_000 + "}"


def test_a_body_nested_too_deeply_is_a_usage_error_given_as_an_argument(stub, pathly):
    ran = pathly("api", "POST", "/comms/post", DEEP, token=TOKEN)

    _sent_nothing(ran, stub)
    assert ran.err.strip().splitlines() == ["pathly: the body is nested too deeply"]


def test_a_body_nested_too_deeply_is_a_usage_error_read_from_standard_input(
    stub, pathly
):
    ran = pathly("api", "POST", "/comms/post", "-", token=TOKEN, stdin=DEEP)

    _sent_nothing(ran, stub)
    assert ran.err.strip().splitlines() == ["pathly: the body is nested too deeply"]


def test_a_body_nested_a_few_levels_is_still_sent(stub, pathly):
    body = '{"a": ' + "[" * 50 + "]" * 50 + "}"

    ran = pathly("api", "POST", "/comms/post", body, token=TOKEN)

    assert ran.code == 0, ran
    assert stub.got[0]["body"] == body.encode()


# --- B4: a bounded read and a bounded print ------------------------------------------------------


def _object_of(size: int, filler: str = "x") -> str:
    """A JSON object that is exactly ``size`` bytes in UTF-8 (``filler`` is one byte)."""
    frame = '{"a":""}'
    return '{"a":"' + filler * (size - len(frame)) + '"}'


def test_the_limits_are_named_constants_with_the_documented_values():
    assert chief_cli.MAX_BODY_BYTES == MAX_BODY == 1024 * 1024
    assert chief_cli.MAX_ANSWER_BYTES == MAX_ANSWER == 256 * 1024


def test_a_body_from_standard_input_over_1_mib_is_a_usage_error_and_sends_nothing(
    stub, pathly
):
    ran = pathly(
        "api", "POST", "/comms/post", "-", token=TOKEN, stdin=_object_of(MAX_BODY + 1)
    )

    _sent_nothing(ran, stub)
    assert str(MAX_BODY) in ran.err and "standard input" in ran.err


def test_a_body_from_standard_input_of_exactly_1_mib_is_sent(stub, pathly):
    body = _object_of(MAX_BODY)
    assert len(body.encode()) == MAX_BODY

    ran = pathly("api", "POST", "/comms/post", "-", token=TOKEN, stdin=body)

    assert ran.code == 0, ran
    assert stub.got[0]["body"] == body.encode()


def test_the_limit_counts_bytes_not_characters(stub, pathly):
    text = _object_of(MAX_BODY // 2 + 100, filler="é")
    assert len(text) <= MAX_BODY < len(text.encode())

    ran = pathly("api", "POST", "/comms/post", "-", token=TOKEN, stdin=text)

    _sent_nothing(ran, stub)


class _Counting(io.StringIO):
    """A standard input that records how much each ``read`` asked for."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.asked: list[int | None] = []

    def read(self, size: int | None = -1) -> str:
        self.asked.append(size)
        return super().read(size)


def test_standard_input_is_read_up_to_the_limit_and_not_whole(
    stub, monkeypatch, capsys
):
    stream = _Counting(_object_of(3 * MAX_BODY))
    monkeypatch.setenv("PATHLY_RUN_TOKEN", TOKEN)
    monkeypatch.setattr(sys, "stdin", stream)

    code = chief_cli.main(["api", "POST", "/comms/post", "-"])

    assert code == 2
    assert stream.asked, "the body was never read from standard input"
    assert all(size is not None and 0 < size <= MAX_BODY + 1 for size in stream.asked)
    assert stub.got == []


def _answered(stub, size: int, status: int = 200, filler: bytes = b"y") -> None:
    stub.status = status
    stub.body = filler * size


def _shown(ran) -> bytes:
    return ran.out.encode().rstrip(b"\n")


def test_an_answer_over_256_kib_is_printed_up_to_256_kib_and_the_cut_is_said(
    stub, pathly
):
    _answered(stub, MAX_ANSWER + 5_000)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert ran.code == 0, ran
    assert _shown(ran) == b"y" * MAX_ANSWER
    lines = ran.err.strip().splitlines()
    assert len(lines) == 1, ran
    assert "cut" in lines[0] and str(MAX_ANSWER) in lines[0]


def test_an_answer_of_exactly_256_kib_is_printed_whole_and_not_called_cut(stub, pathly):
    _answered(stub, MAX_ANSWER)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert ran.code == 0, ran
    assert _shown(ran) == b"y" * MAX_ANSWER
    assert ran.err == ""


def test_an_answer_one_byte_over_the_limit_loses_that_byte(stub, pathly):
    _answered(stub, MAX_ANSWER + 1)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert _shown(ran) == b"y" * MAX_ANSWER
    assert "cut" in ran.err


@pytest.mark.parametrize("status, code", [(200, 0), (404, 1), (500, 1)])
def test_a_cut_answer_still_exits_by_its_status(stub, pathly, status, code):
    _answered(stub, 2 * MAX_ANSWER, status=status)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert ran.code == code, ran
    assert "cut" in ran.err
    assert (f"HTTP {status}" in ran.err) == (code == 1)


def test_the_answer_is_read_in_bounded_pieces_and_never_whole(
    stub, pathly, monkeypatch
):
    asked: list[int | None] = []
    got: list[int] = []
    original = http.client.HTTPResponse.read

    def read(self, amt=None):
        asked.append(amt)
        data = original(self, amt)
        got.append(len(data))
        return data

    monkeypatch.setattr(http.client.HTTPResponse, "read", read)
    _answered(stub, 3 * MAX_ANSWER)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert ran.code == 0, ran
    assert asked and all(a is not None and 0 < a <= MAX_ANSWER + 1 for a in asked)
    assert sum(got) <= MAX_ANSWER + 1


def test_a_multibyte_answer_is_cut_by_bytes_and_says_how_many_were_shown(stub, pathly):
    _answered(stub, MAX_ANSWER, filler="日".encode())

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    shown = _shown(ran)
    assert ran.code == 0, ran
    assert MAX_ANSWER - 3 < len(shown) <= MAX_ANSWER
    assert shown.decode("utf-8") == "日" * (len(shown) // 3)
    assert f"{len(shown)} bytes" in ran.err


def test_a_token_cut_in_half_by_the_limit_is_not_printed_in_part(stub, pathly):
    stub.body = b"y" * (MAX_ANSWER - 6) + TOKEN.encode() + b"z" * 1_000

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert "cut" in ran.err
    assert TOKEN[:3] not in _shown(ran).decode()[-12:]
    assert _shown(ran).startswith(b"y" * 100)


def test_a_whole_token_inside_a_cut_answer_is_redacted(stub, pathly):
    stub.body = b"head " + TOKEN.encode() + b" " + b"y" * (2 * MAX_ANSWER)

    ran = pathly("api", "GET", "/runs?project_root=/p", token=TOKEN)

    assert TOKEN not in ran.out and "[redacted]" in ran.out


# --- B5: the help lists the acknowledge route ----------------------------------------------------

ACKNOWLEDGE = "/comms/acknowledge"


def _help_line(pathly, route: str) -> str:
    for line in pathly("help", token=NO_TOKEN).out.splitlines():
        if line.strip().startswith(route):
            return line
    raise AssertionError(f"`pathly help` has no line for {route}")


def _body_of(line: str, **given) -> dict:
    """The body a help line shows: ``"key": "value"`` as written, a bare ``"key"`` from ``given``."""
    shown = re.search(r"\{(.*)\}", line).group(1)
    body = {}
    for key, value in re.findall(r'"(\w+)"(?:: "([^"]*)")?', shown):
        body[key] = value if value else given[key]
    return body


def test_the_help_has_a_line_for_the_acknowledge_route_with_its_three_keys(pathly):
    line = _help_line(pathly, "POST " + ACKNOWLEDGE)

    assert set(_body_of(line, message_id=1, cite=1)) == {"message_id", "agent", "cite"}
    assert '"agent": "chief"' in line


def test_the_body_the_help_line_shows_closes_an_escalation_as_an_operator_chief(
    server, pathly, project
):
    chief = Session("operator", project)
    escalation = post_row("escalation", to_agent="human")
    later()
    typed = chief.type("go ahead with the migration")
    body = _body_of(
        _help_line(pathly, "POST " + ACKNOWLEDGE), message_id=escalation, cite=typed
    )

    ran = pathly("api", "POST", ACKNOWLEDGE, json.dumps(body), token=chief.chief.token)

    assert ran.code == 0, ran
    assert acknowledged_by(escalation) == ["chief"]
