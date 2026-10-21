"""``pathly``: the command a chief runs to reach the Pathly server (chief-agent 17).

The chief is an interactive agent in a tab. Its settings allow it ``Bash(pathly *)`` and deny
``curl`` and ``wget`` (``runner/chief_argv.py``), so this command is its only door to the server.
It is a thin door on purpose: ``pathly api METHOD PATH [JSON]`` sends one request with the tab's
run token and prints what came back. What the chief may do is not decided here but by the chief
gate on the server, which answers a refusal with a 403 body that this command prints as it came.

Exit codes: 0 for a 2xx answer, 1 for any other status or an unreachable server, 2 for a usage
error (nothing is sent: the token goes to this machine's server and to no other address, and a
body that is not JSON never reaches a route that could spend a citation on it). The token is
read from ``PATHLY_RUN_TOKEN``, sent in ``X-Pathly-Run-Token`` and never printed.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
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

cite is the number Pathly printed when it recorded the user's message in this tab. Pathly
relays that message's own words; never send an answer of your own.
"""


def _usage(message: str) -> int:
    print(f"pathly: {message}\n{USAGE}", file=sys.stderr)
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
    """Why ``text`` is not a JSON object, or None."""
    if not text.strip():
        return "the body is empty: leave it out, or give a JSON object"
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        return f"the body is not valid JSON: {exc}"
    return None if isinstance(parsed, dict) else "the body must be a JSON object"


def _body_text(argument: str) -> str:
    """The body: ``argument``, or standard input for ``-``. A ``UnicodeError`` when it is not
    UTF-8 (a stream that cannot decode it, or an argument the shell passed as raw bytes).
    """
    text = sys.stdin.read() if argument == "-" else argument
    text.encode("utf-8")
    return text


def _send(
    method: str, target: str, body: str | None, token: str, secret: str
) -> tuple[int, str]:
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
        return answer.status, answer.read().decode("utf-8", errors="replace")
    finally:
        connection.close()


def _redact(text: str, hide: tuple[str, ...]) -> str:
    for secret in hide:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


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
    body = None
    if extra:
        try:
            body = _body_text(extra[0])
        except UnicodeError:
            return _usage("the body is not valid UTF-8")
        problem = _json_object(body)
        if problem is not None:
            return _usage(problem)
    secret = _load_secret()
    try:
        status, text = _send(method, target, body, token, secret)
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
    _print_body(text, (token, secret))
    if 200 <= status < 300:
        return 0
    print(f"pathly: HTTP {status}", file=sys.stderr)
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
