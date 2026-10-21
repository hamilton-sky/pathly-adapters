"""chief-agent 17, round 2: the rules in the chief's prompt texts, pinned.

The texts are the only guide a live chief has, and a test that reads only their commands lets a
sentence that carries a rule be deleted unnoticed. Each rule the ticket requires is therefore
pinned by a short phrase, found in the text after ``norm`` has flattened it (lower case, no
backticks, one space between words), so re-wrapping a paragraph or moving a word into backticks
does not break a test; deleting or rewording the sentence does.

Round two of ticket 17 also fixed what a reader of round one found: the operator text invited a
poll loop and named a decompose with no word about its cost, the fragment said nothing about
quoting a path that has a query string or about one command per call, and its start-up reads
listed the questions waiting but not the escalations to the person.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote

import pytest
from chief_bind_support import project_row
from chief_cli_support import pathly, server
from chief_gate_support import _chief, project
from chief_text_support import (
    TEXT_NAMES,
    fenced_blocks,
    norm,
    pathly_commands,
    text_of,
)

# (text, a phrase of the sentence that carries the rule)
PINS = [
    ("chief-connect", "before you do anything else, read"),
    ("chief-connect", "tell the user in a few lines where things stand"),
    ("chief-connect", "do not retry in a loop"),
    ("chief-connect", "check the question and the id first"),
    ("chief-connect", "can be cited once"),
    ("chief-connect", "even when the route then answers 404 or 409"),
    ("chief-connect", "never edit files"),
    ("chief-connect", "never run an agent cli yourself"),
    ("chief-connect", "gave you no number"),
    ("chief-connect", "cannot answer for the user"),
    ("chief-connect", "do not look for another route around it"),
    ("operator", "never on your own idea"),
    ("operator", "in the user's words"),
    ("planner", "ask the user first"),
]


@pytest.mark.parametrize("name,phrase", PINS, ids=[phrase for _, phrase in PINS])
def test_a_rule_the_ticket_requires_is_in_its_text(name, phrase):
    assert phrase in norm(text_of(name))


# --- the operator does not poll, and does not decompose without asking ------------------------


def test_the_operator_checks_when_the_user_writes_or_asks_and_never_in_a_loop():
    operator = norm(text_of("operator"))

    assert "keep watching" not in operator
    assert "when the user writes or asks" in operator
    assert "never check in a loop" in operator
    assert "if pathly refuses a call, tell the user and stop" in operator


@pytest.mark.parametrize("name", ["planner", "operator"])
def test_a_text_that_offers_a_decompose_says_after_it_that_it_costs_money_and_to_ask_first(
    name,
):
    text = norm(text_of(name))
    offered = text.index("goals/decompose")

    assert "an agent costs money, so ask the user first" in text[offered:]


def test_the_operator_style_shows_how_to_list_the_standing_orders():
    reads = [
        target
        for method, target in pathly_commands(text_of("operator"))
        if method == "GET"
    ]

    assert any("type=decision" in target for target in reads)


# --- quoting, one command per call, and a root in a query string ------------------------------


def test_the_fragment_tells_the_chief_to_quote_a_path_that_has_a_query_string():
    fragment = norm(text_of("chief-connect"))

    assert "quote a path that has a query string" in fragment
    assert "an & ends the command" in fragment


def test_the_fragment_tells_the_chief_to_run_one_pathly_command_per_call():
    fragment = norm(text_of("chief-connect"))

    assert "one pathly command per call" in fragment
    assert "no pipe" in fragment and "$(...)" in fragment
    assert "approved for you ahead of time" in fragment


def test_the_fragment_offers_standard_input_only_when_quoting_a_body_is_awkward():
    fragment = norm(text_of("chief-connect"))

    assert "reads it from standard input" in fragment
    assert "only when quoting" in fragment


def test_the_fragment_says_to_percent_encode_a_root_in_a_query_and_not_in_a_body():
    fragment = norm(text_of("chief-connect"))

    for escape in ("%2b", "%26", "%25", "%20"):
        assert escape in fragment, escape
    assert "in a query string" in fragment
    assert "a json body keeps it exactly as written" in fragment


def test_the_last_line_of_the_prompt_does_not_contradict_the_encoding_rule():
    # It says "send the root as written"; the fragment before it says a query string is the one
    # place that is not true, so the line must carry the exception.
    from pathly_orchestrator.supervisor.chief_presets import ROOT_LINE

    assert "apart from the percent-encoding a query string needs" in norm(ROOT_LINE)


@pytest.mark.parametrize("name", TEXT_NAMES)
def test_every_path_with_a_query_string_in_a_text_is_quoted(name):
    commands = pathly_commands(text_of(name))

    assert commands
    for method, target in commands:
        if "?" in target or "&" in target:
            assert target[0] in "'\"", (name, method, target)


# --- the start-up reads ---------------------------------------------------------------------

ESCALATIONS = "type=escalation&status=pending"


def _start_reads() -> list[str]:
    """The commands of the fragment's first fenced block: what a chief reads before anything."""
    return fenced_blocks(text_of("chief-connect"))[0]


def test_the_start_up_reads_cover_the_session_the_goals_the_questions_the_escalations_and_runs():
    reads = "\n".join(_start_reads())

    assert "/chief/session?project_root=<root>" in reads
    assert "/comms/goals?" in reads
    assert "type=question&status=pending" in reads
    assert ESCALATIONS in reads
    assert "/runs?project_root=<root>" in reads


def test_the_fragment_and_the_status_style_list_the_open_escalations_by_one_query():
    fragment = [line for line in _start_reads() if ESCALATIONS in line]
    status = [
        line
        for block in fenced_blocks(text_of("status"))
        for line in block
        if ESCALATIONS in line
    ]

    assert fragment and fragment == status


def test_the_fragment_says_an_escalation_is_the_users_when_it_is_addressed_to_human():
    fragment = norm(text_of("chief-connect"))

    assert "escalations" in fragment and "to_agent is human" in fragment


def test_the_start_up_escalation_read_lists_a_pending_escalation_to_the_person(
    server, pathly, project
):
    chief = _chief("status", project)
    mine = project_row(project, "escalation", to_agent="human")
    other = project_row(project, "escalation", to_agent="builder")
    command = next(line for line in _start_reads() if ESCALATIONS in line)
    target = re.search(r"'([^']+)'", command).group(1)

    ran = pathly(
        "api",
        "GET",
        target.replace("<root>", quote(str(project), safe="")),
        token=chief.token,
    )

    assert ran.code == 0, ran
    rows = {row["id"]: row for row in json.loads(ran.out)}
    assert rows[mine]["to_agent"] == "human"
    assert rows[other]["to_agent"] == "builder"
