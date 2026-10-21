"""chief-agent 17: what the chief's prompt texts tell it to do, against the real gate tables.

The texts are the only guide a live chief has, and ``pathly api`` its only door to the server, so
an example that the gate refuses sends the chief into a 403 on its first call. Every
``pathly api METHOD /path 'json'`` example in a text is therefore read the way the gate reads a
request: the route must exist, the action must be one the text's tier holds, every key must be on
the route's list, a route that falls back to another project must be told the project, a post must
come ``from`` the chief, and an answer must carry ``cite`` and nothing the chief worded. The
``chief-connect`` fragment goes to every tier, so its examples must be reads.
"""

from __future__ import annotations

import json
import re
import shlex
from urllib.parse import parse_qsl

import pytest
from chief_cli_support import fragment_text
from chief_gate_support import _chief, app, client, project
from werkzeug.exceptions import HTTPException

TIER_OF = {
    "status": "status",
    "planner": "planner",
    "operator": "operator",
    "chief-connect": "status",
}
SPAN = re.compile(r"`([^`\n]+)`")
PLACEHOLDER = re.compile(r"<[^<>\n]*>")
ANSWER_TARGETS = {"/runner/agent-answer": "topic", "/comms/answer": "question_id"}


def _text(name: str) -> str:
    if name == "chief-connect":
        return fragment_text()
    from pathly_orchestrator.supervisor import chief_presets

    return chief_presets.BUILT_IN[name]


def examples(text: str) -> list[list[str]]:
    """Each ``pathly api METHOD TARGET [BODY]`` of a text, split the way a shell splits it."""
    spans = SPAN.findall(text)
    fenced, inside = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
        elif inside:
            fenced.append(line.strip().removeprefix("$ "))
    found = []
    for span in [*spans, *fenced]:
        if span.startswith("pathly api "):
            words = shlex.split(span)
            if len(words) >= 4:
                found.append(words)
    return found


def problems(words: list[str], tier: str, app) -> list[str]:
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS
    from pathly_orchestrator.http_server.chief_routes import action_for
    from pathly_orchestrator.supervisor.chief_tiers import actions_for

    _, _, method, target, *rest = words
    shown = " ".join(words)
    path, _, query = PLACEHOLDER.sub("1", target).partition("?")
    try:
        body = json.loads(PLACEHOLDER.sub("1", rest[0])) if rest else {}
    except ValueError:
        return [f"{shown}: the body is not JSON"]
    try:
        rule, view_args = app.url_map.bind("localhost").match(
            path, method=method, return_rule=True
        )
    except HTTPException:
        return [f"{shown}: no such route"]
    keys = {key for key, _ in parse_qsl(query)} if method == "GET" else set(body)
    action = action_for(rule.rule, method, view_args, body, lambda _id: True)
    if action is None:
        return [f"{shown}: a chief may not call this route"]
    found = []
    if action not in actions_for(tier):
        found.append(f"{shown}: {action} is not a {tier} action")
    fields = ROUTE_FIELDS[(rule.rule, method)]
    for key in sorted(keys - fields.allowed(rule.rule)):
        found.append(f"{shown}: {key} is not a key a chief may send")
    must_name = (
        fields.names_root
        or any(key in keys for key in fields.names_root_when)
        or view_args.get("action") in fields.names_root_verbs
    )
    if must_name and "project_root" not in keys:
        found.append(f"{shown}: the route needs project_root")
    if rule.rule == "/comms/post" and body.get("from") != "chief":
        found.append(f"{shown}: a post is from 'chief'")
    if rule.rule in ANSWER_TARGETS and keys != {ANSWER_TARGETS[rule.rule], "cite"}:
        found.append(f"{shown}: an answer carries its target and cite only")
    if rule.rule == "/comms/acknowledge" and (
        body.get("agent") != "chief" or "cite" not in body
    ):
        found.append(f"{shown}: an acknowledgement is from 'chief' and cites")
    return found


@pytest.mark.parametrize("name", list(TIER_OF))
def test_every_example_in_a_text_is_a_call_the_gate_lets_that_tier_make(app, name):
    found = examples(_text(name))

    assert found, "a text with no example teaches nothing"
    assert [p for words in found for p in problems(words, TIER_OF[name], app)] == []


def test_the_fragment_goes_to_every_tier_so_its_examples_are_reads(app):
    for words in examples(fragment_text()):
        assert words[2] == "GET", " ".join(words)


@pytest.mark.parametrize(
    "name,powers",
    [
        ("status", {"read"}),
        ("planner", {"post", "plan"}),
        ("operator", {"run", "stop", "answer", "decide"}),
    ],
)
def test_a_style_shows_the_powers_of_its_tier(app, name, powers):
    from pathly_orchestrator.http_server.chief_routes import action_for

    shown = set()
    for _, _, method, target, *rest in examples(_text(name)):
        path = PLACEHOLDER.sub("1", target).partition("?")[0]
        rule, view_args = app.url_map.bind("localhost").match(
            path, method=method, return_rule=True
        )
        body = json.loads(PLACEHOLDER.sub("1", rest[0])) if rest else {}
        shown.add(action_for(rule.rule, method, view_args, body, lambda _id: True))

    assert shown & powers, (name, shown)


def test_the_operator_style_shows_a_cited_answer():
    shown = [" ".join(words) for words in examples(_text("operator"))]

    assert any("/runner/agent-answer" in line and "cite" in line for line in shown)
    assert not any('"answer"' in line for line in shown)


def test_the_fragment_names_the_limits_by_the_fields_the_session_route_reports(
    client, project
):
    # Limits are read from the session, not written into a text where they could go stale.
    chief = _chief("operator", project)
    reported = client.get(
        "/chief/session",
        query_string={"project_root": str(project)},
        headers=chief.headers,
    ).get_json()

    named = set(re.findall(r"\b(max_[a-z_]+|runs_started)\b", fragment_text()))

    assert {"max_runs_per_session", "max_cost_usd_per_run", "runs_started"} <= named
    assert named <= set(reported)
