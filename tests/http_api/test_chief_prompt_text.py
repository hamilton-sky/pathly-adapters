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
from urllib.parse import parse_qsl, quote

import pytest
from chief_bind_support import record_run
from chief_cite_support import db
from chief_cli_support import (
    _no_watcher_outlives_its_test,
    fragment_text,
    host,
    pathly,
    server,
)
from chief_gate_support import _chief, app, client, project
from chief_text_support import norm
from werkzeug.exceptions import HTTPException

TIER_OF = {
    "status": "status",
    "planner": "planner",
    "operator": "operator",
    "chief-connect": "status",
}
SPAN = re.compile(r"`([^`\n]+)`")
PLACEHOLDER = re.compile(r"<[^<>\n]*>")
METHODS = ("GET", "POST", "PUT", "DELETE")
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
            # `pathly api METHOD /path` in prose is the shape of the command, not a call.
            if len(words) >= 4 and words[2] in METHODS:
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


# --- what a style says its tier may and may not do, against the tier table ---------------------

# The opening of the sentence that names what the tier may do, and of the one that names what it
# may not, in each style (the operator style names no refusal: it holds every action).
MAY = {
    "status": "you may read",
    "planner": "your tier may",
    "operator": "your tier may",
}
MAY_NOT = {"status": "you may not", "planner": "you may not"}
# `run` is "start" in a sentence of refusals.
REFUSED_WORD = {"run": "start"}


def _sentence(name: str, opening: str) -> set[str]:
    """The words of the sentence of a style that opens with ``opening``, up to its full stop or
    colon."""
    text = norm(_text(name))
    return set(
        re.findall(r"[a-z']+", re.match(r"[^.:]*", text[text.index(opening) :])[0])
    )


@pytest.mark.parametrize("name", list(MAY))
def test_the_actions_a_style_says_its_tier_may_do_are_the_ones_the_tier_table_holds(
    name,
):
    from pathly_orchestrator.supervisor.chief_tiers import ACTIONS, TIERS

    said = {action for action in ACTIONS if action in _sentence(name, MAY[name])}

    assert said == TIERS[TIER_OF[name]]


@pytest.mark.parametrize("name", list(MAY_NOT))
def test_the_actions_a_style_says_its_tier_may_not_do_are_the_ones_the_tier_table_lacks(
    name,
):
    from pathly_orchestrator.supervisor.chief_tiers import ACTIONS, TIERS

    words = _sentence(name, MAY_NOT[name])
    said = {action for action in ACTIONS if REFUSED_WORD.get(action, action) in words}

    assert said == set(ACTIONS) - TIERS[TIER_OF[name]]


def test_the_tier_table_gives_the_operator_every_action_so_its_style_names_no_refusal():
    from pathly_orchestrator.supervisor.chief_tiers import ACTIONS, TIERS

    assert TIERS["operator"] == frozenset(ACTIONS)
    assert "operator" not in MAY_NOT


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


# --- the examples, run: the gate lets each one through, and the texts' claims about the answers ---

NOT_CITED = "cite a human message from this chief session"


def _filled(words: list[str], project, run_id: str) -> list[str]:
    """An example with its placeholders filled: the real root and run, a number where a cite goes,
    an id that no row has everywhere else."""
    out = []
    for word in words[1:]:
        word = word.replace("<root>", str(project)).replace("<run_id>", run_id)
        word = re.sub(r'("cite": )<id>', r"\g<1>1", word)
        out.append(PLACEHOLDER.sub("x", word))
    return out


def _refused_by_the_gate(ran) -> bool:
    try:
        body = json.loads(ran.out)
    except ValueError:
        return False
    return ran.code == 1 and isinstance(body, dict) and "allowed" in body


@pytest.fixture()
def nothing_starts(host):
    """The examples name goals and runs that do not exist, so no agent may start: the spawn host
    (``host`` records what a start would send it) must have been sent no spawn at the end.
    """
    yield host
    assert [p for _, p in host.sent if p.get("type") == "TERMINAL_SPAWN"] == []


@pytest.mark.parametrize("name", list(TIER_OF))
def test_no_example_is_refused_by_the_gate_when_run_by_a_chief_of_its_tier(
    server, pathly, project, nothing_starts, name
):
    chief = _chief(TIER_OF[name], project)
    run_id = record_run(project, "run-1")

    refused = []
    for words in examples(_text(name)):
        ran = pathly(*_filled(words, project, run_id), token=chief.token)
        if _refused_by_the_gate(ran) and json.loads(ran.out)["error"] != NOT_CITED:
            refused.append((" ".join(words), ran.out))

    assert refused == []


def test_a_goal_posted_the_way_the_planner_style_says_is_listed_and_a_task_can_name_it(
    server, pathly, project
):
    chief = _chief("planner", project)
    goal, task, _ = [
        words
        for words in examples(_text("planner"))
        if words[3] in ("/comms/post", "/comms/goals/decompose")
    ]

    posted = pathly(*_filled(goal, project, "run-1"), token=chief.token)
    goal_id = json.loads(posted.out)["message_id"]
    filled = _filled(task, project, "run-1")
    body = json.loads(filled[-1])
    body["goal_id"] = goal_id
    body["depends_on"] = []
    tasked = pathly(*filled[:-1], json.dumps(body), token=chief.token)
    listed = pathly(
        "api",
        "GET",
        f"/comms/goals?board=project&scope={quote(str(project))}&feature=project",
        token=chief.token,
    )

    assert (posted.code, tasked.code, listed.code) == (0, 0, 0), (
        posted,
        tasked,
        listed,
    )
    goals = json.loads(listed.out)
    assert [g["id"] for g in goals] == [goal_id]
    assert goals[0]["tasks"]["total"] == 1


def test_a_standing_order_given_the_way_the_operator_style_says_is_listed_as_binding(
    server, pathly, project
):
    chief = _chief("operator", project)
    order = next(w for w in examples(_text("operator")) if w[3] == "/comms/directives")

    given = pathly(*_filled(order, project, "run-1"), token=chief.token)
    listed = pathly(
        "api",
        "GET",
        f"/comms?board=project&scope={quote(str(project))}&feature=project&type=decision",
        token=chief.token,
    )

    assert given.code == 0, given
    rows = json.loads(listed.out)
    assert [(r["id"], r["binding"]) for r in rows] == [(json.loads(given.out)["id"], 1)]


def test_the_supersede_example_retires_a_standing_order_when_given_real_ids(
    server, pathly, project
):
    chief = _chief("operator", project)
    shown = examples(_text("operator"))
    order = next(w for w in shown if w[3] == "/comms/directives")
    supersede = next(w for w in shown if w[3] == "/comms/supersede")

    def give(text: str) -> str:
        words = _filled(order, project, "run-1")
        words[-1] = json.dumps({**json.loads(words[-1]), "text": text})
        given = pathly(*words, token=chief.token)
        assert given.code == 0, given
        return json.loads(given.out)["id"]

    old, new = give("Run the formatter."), give("Run the formatter and the linter.")
    body = supersede[-1]
    assert "<old order id>" in body and "<new order id>" in body, supersede
    body = body.replace("<old order id>", old).replace("<new order id>", new)

    ran = pathly(*_filled(supersede[:-1], project, "run-1"), body, token=chief.token)

    assert ran.code == 0, ran

    def retired_by(message_id: str):
        row = (
            db()
            .execute(
                "SELECT superseded_by FROM comms_messages WHERE id = ?", (message_id,)
            )
            .fetchone()
        )
        return row[0]

    assert retired_by(old) == new
    assert retired_by(new) in (None, "")


def test_a_run_started_for_a_goal_that_does_not_exist_is_a_404_and_costs_no_slot(
    server, pathly, project, nothing_starts
):
    chief = _chief("operator", project)
    start = next(w for w in examples(_text("operator")) if w[3] == "/runs")

    ran = pathly(*_filled(start, project, "run-1"), token=chief.token)

    assert ran.code == 1
    assert "not found" in ran.out
    session = pathly(
        "api",
        "GET",
        f"/chief/session?project_root={quote(str(project))}",
        token=chief.token,
    )
    assert json.loads(session.out)["runs_started"] == 0
