"""chief-agent 17, round 2: `pathly help` and the texts show each route in the form that works.

A bare ``GET /runs`` answers 200 ``[]`` without ``project_root`` (the route returns an empty list
for a project it was not told), so a chief that followed the help line to the letter would conclude
that its project has no runs; a bare ``GET /comms`` and ``GET /chief/session`` are 400s, and a
``GET /comms`` that names ``feature`` alone reads the feature board called ``project``, not the
project board. The help and every text must therefore print each such route with what it needs.
``NEEDS`` is the table of that; the behaviour test checks it against the real routes, so the table
cannot drift from them, and the other tests hold the help and the texts to the table.

A project root that holds ``+``, ``&`` or ``%`` has to be percent-encoded in a query string: the
gate compares what the server decoded, spelled as the root it stored. A JSON body keeps it as is.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import pytest
from chief_bind_support import project_row, record_run
from chief_cli_support import NO_TOKEN, pathly, server
from chief_gate_support import _chief, app, project
from chief_text_support import TEXT_NAMES, norm, text_of

ROOT = "<root>"
BOARD = ("board=project", f"scope={ROOT}", "feature=project")
BODY_BOARD = ('"board": "project"', f'"scope": "{ROOT}"', '"feature": "project"')

# What each route `pathly help` lists needs besides its path, as the help prints it. A route that
# needs nothing is listed with ().
NEEDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("GET", "/comms"): BOARD,
    ("GET", "/runs"): (f"project_root={ROOT}",),
    ("GET", "/chief/session"): (f"project_root={ROOT}",),
    ("POST", "/comms/post"): BODY_BOARD,
    ("POST", "/runs"): (f'"project_root": "{ROOT}"',),
    ("POST", "/comms/directives"): (f'"project_root": "{ROOT}"',),
    ("POST", "/comms/answer"): (),
    ("POST", "/comms/acknowledge"): ('"agent": "chief"',),
    ("POST", "/runner/agent-answer"): (),
}


def _help_lines(pathly) -> dict[tuple[str, str], str]:
    """Each route line of ``pathly help`` by (method, path without its query)."""
    lines = {}
    for line in pathly("help", token=NO_TOKEN).out.splitlines():
        found = re.match(r"\s*(GET|POST|PUT|DELETE) (/\S*)", line)
        if found:
            lines[(found.group(1), found.group(2).split("?")[0])] = line
    return lines


def test_every_route_help_lists_is_in_the_table_of_what_a_route_needs(pathly):
    assert set(_help_lines(pathly)) == set(NEEDS)


def test_a_help_line_names_what_its_route_needs(pathly):
    lines = _help_lines(pathly)

    for route, needs in NEEDS.items():
        for need in needs:
            assert need in lines[route], (route, need, lines[route])


# The keys the help shows for the two routes that take a cited answer, and no others: a key for
# words of the chief's own is the one thing a line there must never show.
ANSWER_KEYS = {
    ("POST", "/comms/answer"): {"question_id", "cite"},
    ("POST", "/runner/agent-answer"): {"topic", "cite"},
}


@pytest.mark.parametrize("route", sorted(ANSWER_KEYS), ids=lambda r: r[1])
def test_the_help_line_of_an_answer_route_shows_exactly_the_keys_of_a_cited_answer(
    pathly, route
):
    line = _help_lines(pathly)[route]

    assert set(re.findall(r'"(\w+)"', line)) == ANSWER_KEYS[route], line
    assert line.rstrip().endswith("only"), line


def test_the_help_says_a_chief_never_sends_an_answer_of_its_own(pathly):
    help_text = norm(pathly("help", token=NO_TOKEN).out)

    assert "never send an answer of your own" in help_text
    assert "relays that message's own words" in help_text


# --- the table, against the routes ---------------------------------------------------------------


def _get(pathly, chief, target):
    return pathly("api", "GET", target, token=chief.token)


def test_a_bare_get_route_fails_or_misleads_and_the_form_help_prints_works(
    server, pathly, project
):
    chief = _chief("operator", project)
    root = quote(str(project), safe="")
    record_run(project, "run-1")
    goal = project_row(project, "goal")

    # GET /comms: no feature is a 400, and the feature alone reads another board.
    assert _get(pathly, chief, "/comms").code == 1
    assert json.loads(_get(pathly, chief, "/comms?feature=project").out) == []
    board = _get(
        pathly, chief, f"/comms?board=project&scope={root}&feature=project&type=goal"
    )
    assert [row["id"] for row in json.loads(board.out)] == [goal]

    # GET /runs: no project_root is 200 and an empty list, which reads as "no runs".
    bare = _get(pathly, chief, "/runs")
    assert (bare.code, json.loads(bare.out)) == (0, [])
    runs = _get(pathly, chief, f"/runs?project_root={root}")
    assert [run["run_id"] for run in json.loads(runs.out)] == ["run-1"]

    # GET /chief/session: no project_root is a 400.
    assert _get(pathly, chief, "/chief/session").code == 1
    session = _get(pathly, chief, f"/chief/session?project_root={root}")
    assert json.loads(session.out)["open"] is True


def test_the_get_forms_in_the_help_run_and_answer_with_what_the_project_holds(
    server, pathly, project
):
    chief = _chief("operator", project)
    record_run(project, "run-1")
    project_row(project, "goal")
    root = quote(str(project), safe="")

    for (method, path), line in _help_lines(pathly).items():
        if method != "GET":
            continue
        target = re.search(r"(/\S*)", line).group(1).replace(ROOT, root)
        ran = _get(pathly, chief, target)
        assert ran.code == 0, (target, ran)
        assert json.loads(ran.out) not in ([], {}, {"open": False}), (target, ran)


def test_the_post_routes_that_need_a_root_refuse_a_body_without_one(
    server, pathly, project
):
    chief = _chief("operator", project)

    run = pathly(
        "api", "POST", "/runs", '{"kind": "goal", "goal_id": "g"}', token=chief.token
    )
    order = pathly(
        "api", "POST", "/comms/directives", '{"text": "x"}', token=chief.token
    )

    assert run.code == 1 and "project_root" in json.loads(run.out)["error"]
    assert order.code == 1 and "project_root" in json.loads(order.out)["error"]


def test_a_post_needs_a_feature_and_one_that_names_no_board_lands_on_a_feature_board(
    server, pathly, project
):
    chief = _chief("planner", project)
    root = str(project)
    post = {"from": "chief", "type": "goal", "text": "g", "board": "project"}

    def posted(**more):
        body = json.dumps({**post, "scope": root, **more})
        return pathly("api", "POST", "/comms/post", body, token=chief.token)

    def on_project_board():
        target = f"/comms?board=project&scope={quote(root, safe='')}&feature=project"
        return [row["text"] for row in json.loads(_get(pathly, chief, target).out)]

    assert posted().code == 1
    assert on_project_board() == []
    only_feature = pathly(
        "api",
        "POST",
        "/comms/post",
        json.dumps(
            {"from": "chief", "type": "goal", "text": "g", "feature": "project"}
        ),
        token=chief.token,
    )
    assert only_feature.code == 0, only_feature
    assert on_project_board() == []
    assert posted(feature="project").code == 0
    assert on_project_board() == ["g"]


def test_the_keys_a_help_line_shows_are_keys_the_gate_lets_a_chief_send(pathly, app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    for (method, path), line in _help_lines(pathly).items():
        rule, _ = app.url_map.bind("localhost").match(
            path, method=method, return_rule=True
        )
        shown = set(re.findall(r'(?<!: )"(\w+)"', line))
        shown |= set(re.findall(r"[?&](\w+)=", line))
        allowed = ROUTE_FIELDS[(rule.rule, method)].allowed(rule.rule)
        assert shown <= allowed, (method, path, sorted(shown - allowed))


# --- the texts ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", TEXT_NAMES)
def test_a_text_that_names_a_get_route_which_needs_something_shows_it_with_it(name):
    for found in re.finditer(
        r"\bGET '?(/comms|/runs|/chief/session)(?![\w/<-])(\S*)", text_of(name)
    ):
        for need in NEEDS[("GET", found.group(1))]:
            assert need in found.group(0), (name, found.group(0), need)


# --- a project root with a character the query string reads for itself -----------------------


ODD_ROOT = "a+b&c%d e"


@pytest.fixture()
def odd(tmp_path):
    root = tmp_path / ODD_ROOT
    root.mkdir()
    return root


def test_a_root_with_a_plus_an_ampersand_or_a_percent_is_named_percent_encoded_in_a_query(
    server, pathly, odd
):
    chief = _chief("operator", odd)
    raw = f"/chief/session?project_root={odd}"
    encoded = f"/chief/session?project_root={quote(str(odd), safe='/')}"

    for given in (raw, raw.replace("&", "%26")):
        refused = _get(pathly, chief, given)
        assert refused.code == 1, (given, refused)
        assert json.loads(refused.out)["error"]
    worked = _get(pathly, chief, encoded)

    assert worked.code == 0, worked
    assert json.loads(worked.out)["run_id"] == chief.run_id
    assert "%2B" in encoded and "%26" in encoded and "%25" in encoded


def test_a_space_in_a_root_may_stay_in_a_query_because_the_command_encodes_it(
    server, pathly, tmp_path
):
    root = tmp_path / "my proj"
    root.mkdir()
    chief = _chief("operator", root)

    plain = _get(pathly, chief, f"/chief/session?project_root={root}")
    encoded = _get(pathly, chief, f"/chief/session?project_root={quote(str(root))}")

    assert (plain.code, encoded.code) == (0, 0), (plain, encoded)


def test_a_json_body_keeps_such_a_root_exactly_as_written(server, pathly, odd):
    chief = _chief("operator", odd)
    body = json.dumps({"project_root": str(odd), "to_agent": "*", "text": "an order"})

    ran = pathly("api", "POST", "/comms/directives", body, token=chief.token)

    assert ran.code == 0, ran
