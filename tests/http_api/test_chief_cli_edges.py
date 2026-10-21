"""chief-agent 17: the edges of `pathly api`.

* A usage error is exit 2 and sends nothing: the token goes to this machine's Pathly server and
  to no other address, and a body that is not JSON is stopped before it can burn a citation.
* Every status is a number: 2xx is exit 0, anything else exit 1, and the body is printed as the
  server sent it either way, so the chief reads the gate's refusal and does not guess.
* ``pathly help`` lists only routes that exist and that a chief may call.
* The command is the chief's only door (curl is denied to it): a cited answer goes through it
  end to end, and it runs as a process with the token in its environment only.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tomllib
from urllib.parse import quote

import pytest
from _paths import REPO_ROOT, SRC
from chief_cite_support import Session, ask, db
from chief_cli_support import NO_TOKEN, fragment_text, host, pathly, server, stub
from chief_gate_support import _chief, app, project

USAGE = "usage: pathly"

BAD_USAGE = [
    pytest.param((), id="nothing"),
    pytest.param(("bogus",), id="unknown-command"),
    pytest.param(("api",), id="api-alone"),
    pytest.param(("api", "GET"), id="no-path"),
    pytest.param(("api", "FETCH", "/comms"), id="unknown-method"),
    pytest.param(("api", "GET", "comms"), id="path-without-slash"),
    pytest.param(("api", "GET", "http://127.0.0.1:1/comms"), id="full-url"),
    pytest.param(("api", "GET", "//other.example/comms"), id="authority"),
    pytest.param(("api", "GET", "/comms\r\nX-Evil: 1"), id="newline-in-path"),
    pytest.param(("api", "GET", "/comms", "{}"), id="get-with-a-body"),
    pytest.param(("api", "POST", "/comms/post", "{}", "extra"), id="extra-argument"),
    pytest.param(("api", "POST", "/comms/post", "not json"), id="body-not-json"),
    pytest.param(("api", "POST", "/comms/post", "[1, 2]"), id="body-a-list"),
    pytest.param(("api", "POST", "/comms/post", '"text"'), id="body-a-string"),
    pytest.param(("api", "POST", "/comms/post", ""), id="empty-body"),
]


@pytest.mark.parametrize("args", BAD_USAGE)
def test_a_usage_error_exits_2_with_the_usage_on_stderr_and_sends_nothing(
    server, pathly, project, args
):
    chief = _chief("operator", project)

    ran = pathly(*args, token=chief.token)

    assert ran.code == 2, ran
    assert ran.out == ""
    assert "pathly" in ran.err
    assert server.requests == []


def test_an_empty_standard_input_for_a_dash_body_is_a_usage_error(
    server, pathly, project
):
    chief = _chief("operator", project)

    ran = pathly("api", "POST", "/comms/post", "-", token=chief.token, stdin="  \n")

    assert ran.code == 2
    assert server.requests == []


def test_a_space_or_a_non_ascii_character_in_the_path_is_sent_percent_encoded(
    stub, pathly
):
    ran = pathly("api", "GET", "/runs?project_root=/home/zo\u00eb/my proj", token="tok")

    assert ran.code == 0
    assert stub.got[0]["target"] == "/runs?project_root=/home/zo%C3%AB/my%20proj"


def test_a_lowercase_method_is_accepted(server, pathly, project):
    chief = _chief("operator", project)

    ran = pathly("api", "get", "/runs", token=chief.token)

    assert ran.code == 0, ran
    assert server.requests[0].method == "GET"


# --- pathly help ----------------------------------------------------------------------------

LISTED_ROUTES = [
    ("GET", "/comms"),
    ("GET", "/runs"),
    ("POST", "/comms/post"),
    ("POST", "/runs"),
    ("POST", "/comms/answer"),
    ("POST", "/runner/agent-answer"),
    ("POST", "/comms/directives"),
    ("GET", "/chief/session"),
]


def _routes_in(text: str) -> list[tuple[str, str]]:
    import re

    return re.findall(r"^\s*(GET|POST|PUT|DELETE) (/\S*)", text, re.MULTILINE)


@pytest.mark.parametrize("args", [("help",), ("--help",), ("-h",)])
def test_help_lists_the_commands_and_the_main_routes_without_a_token_or_a_request(
    server, pathly, args
):
    ran = pathly(*args, token=NO_TOKEN)

    assert ran.code == 0, ran
    assert ran.err == ""
    assert "pathly api" in ran.out and "pathly help" in ran.out
    routes = _routes_in(ran.out)
    for route in LISTED_ROUTES:
        assert route in routes, route
    assert "cite" in ran.out
    assert server.requests == []


def test_every_route_help_lists_exists_and_a_chief_may_call_it(pathly, app):
    from pathly_orchestrator.http_server.chief_routes import action_for

    ran = pathly("help", token=NO_TOKEN)

    rules = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
    }
    for method, path in _routes_in(ran.out):
        assert (path, method) in rules, (method, path)
        assert action_for(path, method, {}, {}, lambda _id: False) is not None, path


# --- bodies and statuses (against a stub, so each status is one the test chooses) ---------------


def test_a_body_comes_from_the_argument_or_from_standard_input_and_is_sent_as_given(
    stub, pathly
):
    given = '{"text": "café \\"quoted\\" and it\'s fine"}'

    by_argument = pathly("api", "POST", "/comms/post", given, token="tok")
    by_stdin = pathly(
        "api", "POST", "/comms/post", "-", token="tok", stdin=given + "\n"
    )

    assert (by_argument.code, by_stdin.code) == (0, 0)
    first, second = stub.got
    assert first["body"] == given.encode("utf-8")
    assert second["body"].strip() == given.encode("utf-8")
    for got in (first, second):
        assert got["method"] == "POST" and got["target"] == "/comms/post"
        assert got["headers"]["content-type"] == "application/json"
        assert got["headers"]["x-pathly-run-token"] == "tok"


def test_an_apostrophe_is_written_as_u0027_inside_the_quoted_body_and_stored_as_one(
    server, pathly, project
):
    # The shell ends a single-quoted argument at the first apostrophe, so the fragment tells the
    # chief to write the JSON escape; the command sends it as given and the server decodes it.
    assert "\\u0027" in fragment_text()
    chief = _chief("planner", project)
    body = json.dumps(
        {
            "from": "chief",
            "type": "goal",
            "text": "make it's way",
            "board": "project",
            "scope": str(project),
            "feature": "project",
            "project_root": str(project),
        }
    ).replace("'", "\\u0027")
    assert "\\u0027" in body and "'" not in body

    posted = pathly("api", "POST", "/comms/post", body, token=chief.token)
    listed = pathly(
        "api",
        "GET",
        f"/comms?board=project&scope={quote(str(project))}&feature=project&type=goal",
        token=chief.token,
    )

    assert (posted.code, listed.code) == (0, 0), (posted, listed)
    assert [row["text"] for row in json.loads(listed.out)] == ["make it's way"]


def test_a_post_without_a_body_sends_none(stub, pathly):
    ran = pathly("api", "POST", "/runs/abc/pause", token="tok")

    assert ran.code == 0
    assert stub.got[0]["body"] == b""
    assert stub.got[0]["headers"]["content-length"] == "0"


@pytest.mark.parametrize(
    "status,code",
    [
        (200, 0),
        (201, 0),
        (204, 0),
        (299, 0),
        (301, 1),
        (400, 1),
        (401, 1),
        (404, 1),
        (500, 1),
    ],
)
def test_a_status_is_exit_0_for_2xx_and_1_for_any_other(stub, pathly, status, code):
    stub.status = status
    stub.body = b"" if status == 204 else b'{"why": "because"}'

    ran = pathly("api", "GET", "/comms", token="tok")

    assert ran.code == code, ran
    assert ran.out.strip() == ("" if status == 204 else '{"why": "because"}')


def test_a_body_that_is_not_json_is_printed_as_it_came(stub, pathly):
    stub.status = 502
    stub.body = "Bad gateway — try later\n".encode("utf-8")

    ran = pathly("api", "GET", "/comms", token="tok")

    assert ran.code == 1
    assert ran.out == "Bad gateway — try later\n"
    assert "502" in ran.err


def test_a_response_that_holds_the_token_is_printed_without_it(stub, pathly):
    stub.echo_token = True

    ran = pathly("api", "GET", "/comms", token="tok-very-secret-1234")

    assert ran.code == 0
    assert "tok-very-secret-1234" not in ran.out + ran.err
    assert "[redacted]" in ran.out


# --- the server's secret and the port ---------------------------------------------------------


def test_the_server_secret_is_sent_when_one_is_set_and_not_otherwise(
    server, pathly, project, monkeypatch
):
    chief = _chief("operator", project)

    pathly("api", "GET", "/comms", token=chief.token)
    monkeypatch.setenv("PATHLY_API_SECRET", "the-secret")
    pathly("api", "GET", "/comms", token=chief.token)

    assert [s.secret for s in server.requests] == [None, "the-secret"]
    assert [s.run_token for s in server.requests] == [chief.token, chief.token]


def test_a_server_that_is_not_there_is_exit_1_with_a_message_not_a_traceback(
    pathly, monkeypatch
):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", str(port))

    ran = pathly("api", "GET", "/comms", token="tok-not-printed")

    assert ran.code == 1, ran
    assert ran.out == ""
    assert str(port) in ran.err
    assert "Traceback" not in ran.err
    assert "tok-not-printed" not in ran.err


def test_an_error_that_holds_the_token_is_printed_without_it(pathly, monkeypatch):
    from pathly_orchestrator import chief_cli

    def refuse(*_args):
        raise OSError("refused for tok-in-error")

    monkeypatch.setattr(chief_cli, "_send", refuse)

    ran = pathly("api", "GET", "/comms", token="tok-in-error")

    assert ran.code == 1, ran
    assert "refused for" in ran.err
    assert "tok-in-error" not in ran.err


# --- what a chief may not do, and what it may -------------------------------------------------


REFUSED_VERBS = [
    pytest.param("PUT", "/db/settings/verify.build", ['{"value": "make"}'], id="put"),
    pytest.param("DELETE", "/catalog/item", [], id="delete"),
]


@pytest.mark.parametrize("method,path,body", REFUSED_VERBS)
def test_put_and_delete_are_sent_as_asked_and_the_gate_refuses_a_chief_them(
    server, pathly, project, method, path, body
):
    chief = _chief("operator", project)

    ran = pathly("api", method, path, *body, token=chief.token)

    assert ran.code == 1, ran
    assert server.requests[0].method == method
    refusal = json.loads(ran.out)
    assert refusal["error"] == "the chief may not call this route"
    assert refusal["tier"] == "operator"


def test_a_cited_answer_goes_through_the_command_and_the_agent_gets_the_persons_words(
    server, pathly, project, ask
):
    session = Session("operator", project)
    asker = ask("t-1")
    said = session.type("CSV, with a header row")
    body = json.dumps({"topic": "t-1", "cite": said})

    answered = pathly(
        "api", "POST", "/runner/agent-answer", body, token=session.chief.token
    )

    assert answered.code == 0, answered
    assert asker.answer() == "CSV, with a header row"

    again = pathly(
        "api", "POST", "/runner/agent-answer", body, token=session.chief.token
    )
    assert again.code == 1
    assert "already cited" in json.loads(again.out)["error"]


def test_an_answer_with_words_of_the_chiefs_own_is_refused_through_the_command(
    server, pathly, project, ask
):
    session = Session("operator", project)
    asker = ask("t-1")
    said = session.type("CSV")
    body = json.dumps({"topic": "t-1", "answer": "JSON", "cite": said})

    ran = pathly("api", "POST", "/runner/agent-answer", body, token=session.chief.token)

    assert ran.code == 1
    assert "cite only" in json.loads(ran.out)["error"]
    assert asker.still_waiting()
    assert db().execute("SELECT COUNT(*) FROM chief_citations").fetchone()[0] == 0


# --- the entry point and the process ----------------------------------------------------------


def test_pathly_is_a_console_script_of_the_package():
    declared = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert (
        declared["project"]["scripts"]["pathly"] == "pathly_orchestrator.chief_cli:main"
    )


def _process(args: list[str], env_more: dict, tmp_path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PATHLY_")}
    env.update(PYTHONPATH=str(SRC), HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    env.update(env_more)
    return subprocess.run(
        [sys.executable, "-m", "pathly_orchestrator.chief_cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_the_command_runs_as_a_process_with_the_token_in_its_environment(
    server, project, tmp_path
):
    chief = _chief("operator", project)
    target = f"/chief/session?project_root={quote(str(project))}"
    env = {"PATHLY_FSM_HTTP_PORT": str(server.port), "PATHLY_RUN_TOKEN": chief.token}

    done = _process(["api", "GET", target], env, tmp_path)

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["run_id"] == chief.run_id
    assert chief.token not in done.stdout + done.stderr
    assert server.requests[0].run_token == chief.token

    missing = _process(
        ["api", "GET", target], {"PATHLY_FSM_HTTP_PORT": str(server.port)}, tmp_path
    )
    assert missing.returncode == 2
    assert "PATHLY_RUN_TOKEN" in missing.stderr
    assert len(server.requests) == 1
