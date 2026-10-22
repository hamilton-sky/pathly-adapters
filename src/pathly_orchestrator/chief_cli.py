"""``pathly``: the command a chief runs to reach the Pathly server (chief-agent 17).

The chief is an interactive agent in a tab. Its settings allow it ``Bash(pathly *)`` and deny
``curl`` and ``wget`` (``runner/chief_argv.py``), so this command is its only door to the server.
It is a thin door on purpose: ``pathly api METHOD PATH [JSON]`` sends one request with the tab's
run token and prints what came back. What the chief may do is not decided here but by the chief
gate on the server, which answers a refusal with a 403 body that this command prints as it came.

Exit codes: 0 for a 2xx answer, 1 for any other status or an unreachable server, 2 for a usage
error (nothing is sent: the token goes to this machine's server and to no other address, and a
body that is not JSON never reaches a route that could spend a citation on it). The token is
read from ``PATHLY_RUN_TOKEN``, sent in ``X-Pathly-Run-Token`` and never printed. A token or
server secret an HTTP header cannot carry, a body nested too deeply to parse and a body read from
standard input over ``MAX_BODY_BYTES`` are usage errors too, one line each that names the problem
and never the value. At most ``MAX_ANSWER_BYTES`` of an answer are read and printed.
"""

from __future__ import annotations

import codecs
import http.client
import json
import os
import sys
from typing import NamedTuple
from urllib.parse import quote

from pathly_orchestrator.config import fsm_port
from pathly_orchestrator.fsm_http_client import DEFAULT_HOST, _load_secret

TOKEN_ENV = "PATHLY_RUN_TOKEN"
TOKEN_HEADER = "X-Pathly-Run-Token"
SECRET_HEADER = "X-Pathly-Secret"
METHODS = ("GET", "POST", "PUT", "DELETE")
MISSING_TOKEN = (
    f"{TOKEN_ENV} is not set: open the chief from Pathly "
    "(a codex shell_environment_policy can also filter it)"
)
USAGE = (
    "usage: pathly api GET <path>\n"
    "       pathly api POST|PUT|DELETE <path> [<json> | -]\n"
    "       pathly help"
)
# The longest the server may take to answer (a route that starts a run waits for the start).
TIMEOUT = 120.0
REDACTED = "[redacted]"
# Bytes of a body read from standard input, and of an answer read and printed. A chief's
# transcript carries what the command prints, so neither is left unbounded.
MAX_BODY_BYTES = 1024 * 1024
MAX_ANSWER_BYTES = 256 * 1024

HELP = f"""\
pathly sends one request to the Pathly server as this chief and prints the answer.

{USAGE}

A path starts with / and may carry a query string: quote the path in the shell, or an & ends the
command. A JSON body is one argument (quote it too), or - to read it from standard input. The
answer is printed as the server sent it.
Exit 0: a 2xx answer. Exit 1: any other status (the printed body says why) or no server.
Exit 2: a usage error, and nothing was sent.

Routes a chief uses most (a refusal is a 403 whose body lists what your tier allows).
<root> is your project root, as the last line of your prompt gives it; in a query string write a
+, & or % of it as %2B, %26 or %25. A route that is left without what it needs answers 400, or,
for /runs, an empty list.
  GET /comms?board=project&scope=<root>&feature=project   the project board's messages (add &type= and &status=)
  GET /runs?project_root=<root>                           the runs of the project
  GET /chief/session?project_root=<root>                  this session: tier, runs started, the run and cost limits
  POST /comms/post          a message, goal or task on the project board: {{"from": "chief", "type", "text", "board": "project", "scope": "<root>", "feature": "project"}}
  POST /runs                start a run: {{"kind", "goal_id", "project_root": "<root>"}}
  POST /comms/answer        answer a board question: send {{"question_id", "cite"}} only
  POST /runner/agent-answer answer a waiting run: send {{"topic", "cite"}} only
  POST /comms/directives    a standing order for every agent of the project: {{"project_root": "<root>", "to_agent", "text"}}
  POST /comms/acknowledge   close an escalation addressed to the human (operator tier): {{"message_id", "agent": "chief", "cite"}}

cite is the number Pathly printed when it recorded the user's message in this tab. Pathly
relays that message's own words; never send an answer of your own.
"""


def _usage(message: str) -> int:
    print(f"pathly: {message}\n{USAGE}", file=sys.stderr)
    return 2


def _refuse(message: str) -> int:
    """A usage error that needs no reminder of the usage: one line, and nothing was sent."""
    print(f"pathly: {message}", file=sys.stderr)
    return 2


def _use_utf8() -> None:
    """Read and print UTF-8 whatever the console's code page is (a no-op for a stream that
    cannot be reconfigured)."""
    for stream, errors in (
        (sys.stdin, "strict"),
        (sys.stdout, "replace"),
        (sys.stderr, "replace"),
    ):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=errors)


def _bad_target(target: str) -> str | None:
    """Why ``target`` is not a path on the server, or None. A path starts with one ``/``: a full
    URL or an authority would be a request to somewhere else. A space or a non-ASCII character
    is allowed and sent percent-encoded (a project root often holds one); a control character
    is not (it would end the request line).
    """
    if not target.startswith("/") or target.startswith("//"):
        return "the path must start with a single /, not a URL"
    if any(ch < " " or ch == "\x7f" for ch in target):
        return "the path must not hold a control character"
    try:
        target.encode("utf-8")
    except UnicodeError:
        return "the path is not valid UTF-8"
    return None


def _json_object(text: str) -> str | None:
    """Why ``text`` is not a JSON object, or None. A ``RecursionError`` (a body nested deeper than
    the parser goes) is for the caller."""
    if not text.strip():
        return "the body is empty: leave it out, or give a JSON object"
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        return f"the body is not valid JSON: {exc}"
    return None if isinstance(parsed, dict) else "the body must be a JSON object"


class BodyTooLarge(Exception):
    """The body on standard input is over ``MAX_BODY_BYTES``."""


def _body_text(argument: str) -> str:
    """The body: ``argument``, or standard input for ``-``, of which at most ``MAX_BODY_BYTES``
    are read (``BodyTooLarge`` past that: one character more than the limit is asked for, so
    standard input is never read whole). A ``UnicodeError`` when it is not UTF-8 (a stream that
    cannot decode it, or an argument the shell passed as raw bytes).
    """
    text = sys.stdin.read(MAX_BODY_BYTES + 1) if argument == "-" else argument
    size = len(text.encode("utf-8"))
    if argument == "-" and size > MAX_BODY_BYTES:
        raise BodyTooLarge
    return text


def _header_unfit(value: str) -> bool:
    """True when ``value`` cannot be an HTTP header value: ``http.client`` refuses a newline it
    does not fold and encodes a value as latin-1. Any line break is refused here."""
    try:
        value.encode("latin-1")
    except UnicodeEncodeError:
        return True
    return "\r" in value or "\n" in value


class Answer(NamedTuple):
    """What the server answered: the status and at most ``MAX_ANSWER_BYTES`` + 1 bytes of body."""

    status: int
    data: bytes


def _send(
    method: str, target: str, body: str | None, token: str, secret: str
) -> Answer:
    headers = {TOKEN_HEADER: token}
    if method != "GET":
        headers["Content-Type"] = "application/json"
    if secret:
        headers[SECRET_HEADER] = secret
    connection = http.client.HTTPConnection(DEFAULT_HOST, fsm_port(), timeout=TIMEOUT)
    try:
        connection.request(
            method,
            quote(target, safe="/?&=%+:;,@!$'()*[]~"),
            body=None if body is None else body.encode("utf-8"),
            headers=headers,
        )
        answer = connection.getresponse()
        data = b""
        while len(data) <= MAX_ANSWER_BYTES:  # one byte past the limit says it was cut
            piece = answer.read(MAX_ANSWER_BYTES + 1 - len(data))
            if not piece:
                break
            data += piece
        return Answer(answer.status, data)
    finally:
        connection.close()


def _redact(text: str, hide: tuple[str, ...]) -> str:
    for secret in hide:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def _printable(data: bytes, hide: tuple[str, ...]) -> tuple[str, int | None]:
    """The text of an answer to print, and, when ``data`` held more than ``MAX_ANSWER_BYTES``,
    how many of its bytes that text is (else None).

    A cut never ends inside a character, and never inside a secret: ``_redact`` finds only a
    whole one, so the start of one that the limit cut in half is dropped as well.
    """
    if len(data) <= MAX_ANSWER_BYTES:
        return data.decode("utf-8", errors="replace"), None
    kept = data[:MAX_ANSWER_BYTES]
    for secret in filter(None, hide):
        for size in range(len(secret) - 1, 0, -1):
            part = secret[:size].encode("utf-8")
            if kept.endswith(part):
                kept = kept[: -len(part)]
                break
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    text = decoder.decode(kept)
    return text, len(kept) - len(decoder.getstate()[0])


def _print_body(text: str, hide: tuple[str, ...]) -> None:
    text = _redact(text, hide)
    if text:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _api(args: list[str]) -> int:
    if len(args) < 2:
        return _usage("api needs a method and a path")
    method, target, extra = args[0].upper(), args[1], args[2:]
    if method not in METHODS:
        return _usage(f"the method must be one of {', '.join(METHODS)}")
    problem = _bad_target(target)
    if problem is None and method == "GET" and extra:
        problem = "a GET has no body"
    if problem is None and len(extra) > 1:
        problem = "give at most one body"
    if problem is not None:
        return _usage(problem)
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(MISSING_TOKEN, file=sys.stderr)
        return 2
    if _header_unfit(token):
        return _refuse(f"{TOKEN_ENV} holds a character an HTTP header cannot carry")
    body = None
    if extra:
        try:
            body = _body_text(extra[0])
        except BodyTooLarge:
            return _refuse(
                f"the body from standard input is over {MAX_BODY_BYTES} bytes"
            )
        except UnicodeError:
            return _usage("the body is not valid UTF-8")
        try:
            problem = _json_object(body)
        except RecursionError:
            return _refuse("the body is nested too deeply")
        if problem is not None:
            return _usage(problem)
    try:
        secret = _load_secret()
    except UnicodeError:  # a secret file that is not text
        return _refuse("the server secret cannot be read as text")
    if _header_unfit(secret):
        return _refuse(
            "the server secret holds a character an HTTP header cannot carry"
        )
    try:
        answer = _send(method, target, body, token, secret)
    except (OSError, http.client.HTTPException) as exc:
        print(
            _redact(
                f"pathly: no answer from the Pathly server at {DEFAULT_HOST}:{fsm_port()}: "
                f"{exc}",
                (token, secret),
            ),
            file=sys.stderr,
        )
        return 1
    text, shown = _printable(answer.data, (token, secret))
    _print_body(text, (token, secret))
    if shown is not None:
        print(
            f"pathly: the answer was cut: its first {shown} bytes are shown "
            f"(the limit is {MAX_ANSWER_BYTES})",
            file=sys.stderr,
        )
    if 200 <= answer.status < 300:
        return 0
    print(f"pathly: HTTP {answer.status}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """The ``pathly`` console script; returns the exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    _use_utf8()
    if not args:
        return _usage("a command is required")
    command, rest = args[0], args[1:]
    if command in ("help", "-h", "--help"):
        print(HELP, end="")
        return 0
    if command == "api":
        return _api(rest)
    return _usage(f"unknown command {command!r}")


if __name__ == "__main__":
    sys.exit(main())
