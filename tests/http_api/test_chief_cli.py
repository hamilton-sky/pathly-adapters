"""chief-agent 17: `pathly api`, the three built-in styles and the `chief-connect` fragment.

Without this ticket nobody can use the chief: the claude chief may run only ``Bash(pathly *)``
(ticket 06, which also denies curl), no ``pathly`` command exists and no style has a text. The
tests run the real command against the real app on a free port (``server``), with the real chief
gate in front of every route, and read what the server was sent from the wrapper that records it.

The prompt a chief is pasted is two parts: the style (built in, or the user's own file) and the
``chief-connect`` fragment the server appends to every chief prompt, so a saved style cannot drop
its rules. The last tests read the texts: they may name only ``pathly`` commands (the chief is
denied the rest) and the fragment carries the prompt-injection paragraph.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import pytest
from chief_cli_support import (
    MISSING_TOKEN,
    NO_TOKEN,
    Host,
    fragment_text,
    host,
    pathly,
    server,
)
from chief_gate_support import _chief, app, client, project

STYLES = ["status", "planner", "operator"]


def _presets():
    from pathly_orchestrator.supervisor import chief_presets

    return chief_presets


def _open(client, project, **body):
    fields = {"project_root": str(project), "engine": "claude", "preset": "operator"}
    fields.update(body)
    return client.post("/chief/open", json=fields)


def _expected_start(style: str) -> str:
    """The pasted prompt up to the part that names the project: the style, then the fragment."""
    from pathly_orchestrator.supervisor.chief_tiers import strip_front_matter

    return strip_front_matter(style).strip() + "\n\n" + fragment_text().strip()


# --- the command, against a running server ------------------------------------------------------


def test_get_the_chief_session_with_an_operator_token_exits_0_and_prints_the_session(
    server, pathly, project
):
    chief = _chief("operator", project)
    target = f"/chief/session?project_root={quote(str(project))}"

    ran = pathly("api", "GET", target, token=chief.token)

    assert ran.code == 0, ran
    session = json.loads(ran.out)
    assert session["open"] is True
    assert session["run_id"] == chief.run_id
    assert session["tier"] == "operator"
    assert [(s.method, s.target) for s in server.requests] == [("GET", target)]
    assert server.requests[0].run_token == chief.token


def test_a_status_chiefs_post_exits_1_and_prints_the_gates_403_body(
    server, pathly, project
):
    chief = _chief("status", project)
    body = json.dumps(
        {"feature": "demo", "from": "chief", "type": "note", "text": "hi"}
    )

    ran = pathly("api", "POST", "/comms/post", body, token=chief.token)

    assert ran.code == 1, ran
    refusal = json.loads(ran.out)
    assert refusal["tier"] == "status"
    assert refusal["action"] == "post"
    assert refusal["allowed"] == ["read"]
    assert refusal["error"]
    assert [(s.method, s.target) for s in server.requests] == [("POST", "/comms/post")]


@pytest.mark.parametrize(
    "token", [NO_TOKEN, "", "   "], ids=["unset", "empty", "blank"]
)
def test_without_a_token_it_exits_2_names_the_variable_and_the_server_sees_nothing(
    server, pathly, token
):
    ran = pathly("api", "GET", "/comms", token=token)

    assert ran.code == 2, ran
    assert ran.out == ""
    assert ran.err.strip() == MISSING_TOKEN
    assert "PATHLY_RUN_TOKEN" in ran.err
    assert server.requests == []


def test_the_token_never_reaches_stdout_or_stderr(server, pathly, project):
    chief = _chief("status", project)
    session = f"/chief/session?project_root={quote(str(project))}"

    runs = [
        pathly("api", "GET", session, token=chief.token),
        pathly("api", "GET", "/no/such/route", token=chief.token),
        pathly("api", "POST", "/comms/post", "{}", token=chief.token),
        pathly("api", "GET", "/comms", token=NO_TOKEN),
        pathly("help", token=chief.token),
        pathly("api", token=chief.token),
    ]

    assert [ran.code for ran in runs] == [0, 1, 1, 2, 0, 2]
    assert len(server.requests) == 3
    for ran in runs:
        assert chief.token not in ran.out + ran.err, ran


# --- POST /chief/open: the style, then the fragment ---------------------------------------------


@pytest.mark.parametrize("preset", STYLES)
def test_open_without_a_prompt_pastes_the_built_in_text_then_the_fragment(
    client, host: Host, project, preset
):
    response = _open(client, project, preset=preset)

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["tier"] == preset
    prompt = host.spawn["prompt"]
    assert prompt.startswith(_expected_start(_presets().BUILT_IN[preset]))


def test_the_operator_prompt_ends_with_the_root_exactly_as_the_session_stores_it(
    client, host: Host, project
):
    _open(client, str(project) + "/")

    prompt = host.spawn["prompt"]
    tail = prompt[len(_expected_start(_presets().BUILT_IN["operator"])) :]
    assert tail.rstrip().endswith(str(project))
    assert str(project) + "/" not in tail


def test_open_with_a_custom_preset_and_no_prompt_is_400_and_opens_nothing(
    client, host: Host, project
):
    response = _open(client, project, preset="custom")

    assert response.status_code == 400
    assert "prompt" in response.get_json()["error"]
    assert host.sent == []
    assert client.get(
        "/chief/session", query_string={"project_root": str(project)}
    ).get_json() == {"open": False}


USER_STYLE = "You are a terse chief. Do what the user says and nothing else."


def test_a_user_style_file_is_used_without_a_prompt_and_still_gets_the_fragment(
    client, host: Host, project
):
    from pathly_orchestrator.skills.prompt_files import write_prompt_file

    write_prompt_file(
        "chief",
        "operator",
        f"---\ntier: operator\n---\n{USER_STYLE}",
        project_root=str(project),
    )

    response = _open(client, project)

    assert response.status_code == 201, response.get_json()
    prompt = host.spawn["prompt"]
    assert prompt.startswith(_expected_start(USER_STYLE))
    assert _presets().BUILT_IN["operator"].strip() not in prompt


def test_a_prompt_in_the_body_still_gets_the_fragment(client, host: Host, project):
    response = _open(client, project, prompt=f"---\ntier: operator\n---\n{USER_STYLE}")

    assert response.status_code == 201, response.get_json()
    assert host.spawn["prompt"].startswith(_expected_start(USER_STYLE))


def test_a_style_that_lacks_the_cite_and_injection_rules_gets_them_from_the_fragment(
    client, host: Host, project
):
    assert "cite" not in USER_STYLE and "artifact" not in USER_STYLE

    _open(client, project, prompt=USER_STYLE)

    prompt = host.spawn["prompt"]
    assert "cite=<id>" in prompt
    assert re.search(r"never run `?/clear", prompt, re.IGNORECASE)
    assert _injection_paragraph(prompt)


# --- the texts ------------------------------------------------------------------------------------

FORBIDDEN = ("curl", "wget", "python", "git", "bash", "sudo", "npm", "node")
SUBCOMMANDS = {"api", "help"}


def _texts() -> dict[str, str]:
    return {
        **{name: _presets().BUILT_IN[name] for name in STYLES},
        "chief-connect": fragment_text(),
    }


def _fenced_lines(text: str) -> list[str]:
    lines, inside = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
        elif inside and line.strip():
            lines.append(line.strip().removeprefix("$ "))
    return lines


@pytest.mark.parametrize("name", [*STYLES, "chief-connect"])
def test_a_text_names_only_pathly_commands(name):
    text = _texts()[name]

    assert set(re.findall(r"\bpathly ([a-z][\w-]*)", text)) <= SUBCOMMANDS
    for word in FORBIDDEN:
        assert not re.search(rf"\b{word}\b", text, re.IGNORECASE), word
    for line in _fenced_lines(text):
        assert line.startswith("pathly "), line


def test_the_fragment_teaches_the_command_and_its_help():
    text = fragment_text()

    assert "pathly help" in text
    assert re.search(r"\bpathly api (GET|POST) '?/", text)
    assert (
        '`pathly api` sends `-H "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"` for you'
        in text
    )


def _injection_paragraph(text: str) -> str | None:
    """The paragraph that says who may give the chief orders: it names the places text can come
    from (the board, artifacts, agent output) and says only the user, in this tab, orders.
    """
    for paragraph in re.split(r"\n\s*\n", text):
        lowered = paragraph.lower()
        if all(
            word in lowered
            for word in ("board", "artifact", "agent output", "only the user")
        ):
            return paragraph
    return None


def test_the_fragment_contains_the_prompt_injection_paragraph():
    paragraph = _injection_paragraph(fragment_text())

    assert paragraph is not None
    assert "tab" in paragraph.lower()


@pytest.mark.parametrize("name", STYLES)
def test_a_built_in_style_is_short_plain_text_that_starts_without_front_matter(name):
    text = _presets().BUILT_IN[name]

    assert text.strip() and not text.lstrip().startswith("---")
    assert len(text) < 4000
