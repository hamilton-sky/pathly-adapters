"""chief-autopilot 07: the Operator text, where the spike's chief misread it (S8, S9, S10).

A live Operator chief guessed `from_agent` and `agent` for a goal post the text never showed, said
a goal run was "capped at $10", and after a denied `curl` offered `! curl` and a change to its
permission settings. After ticket 04 a flow a chief starts runs headless, and after ticket 06 a
task can wait for an answer. Each of those is pinned here by what the text must say, read after
``norm`` has flattened it; the examples themselves are held to the gate's tables by
``test_chief_prompt_text.py``, and the one body that is shown without ``pathly api`` (a flow
start, which would really start a run there) is held to the same tables here.
"""

from __future__ import annotations

import json
import re

from chief_gate_support import (
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    project,
)
from chief_text_support import norm, text_of
from test_chief_prompt_text import examples, problems

COST = re.compile(r"\bmax_cost_usd\b")


def _operator() -> str:
    return text_of("operator")


def _bodies_of(route: str) -> list[dict]:
    """The JSON body of each ``pathly api POST <route>`` example of the Operator text."""
    return [
        json.loads(words[4])
        for words in examples(_operator())
        if words[2:4] == ["POST", route] and len(words) > 4
    ]


def _sentences(text: str) -> list[str]:
    """``text`` flattened and cut at each full stop that ends a sentence."""
    return [s for s in re.split(r"(?<=\.)\s+", norm(text)) if s]


# --- S8: the post bodies, and the 403 that names the author ------------------------------------


def test_the_operator_text_shows_a_goal_post_body_from_the_chief():
    goals = [b for b in _bodies_of("/comms/post") if b.get("type") == "goal"]

    assert goals, "the Operator text shows no goal post"
    assert all(b["from"] == "chief" for b in goals)
    assert all(
        b.get("board") == "project" and b.get("feature") == "project" for b in goals
    )
    assert '"from": "chief"' in _operator()


def test_the_operator_text_shows_a_task_post_body_that_names_its_goal():
    tasks = [b for b in _bodies_of("/comms/post") if b.get("type") == "task"]

    assert tasks, "the Operator text shows no task post"
    assert all(b["from"] == "chief" and "goal_id" in b for b in tasks)


def test_a_post_from_another_author_is_refused_with_the_field_to_send(client, project):
    chief = _chief("operator", project)
    body = {
        "feature": "project",
        "board": "project",
        "scope": str(project),
        "from_agent": "chief",
        "from": "operator",
        "type": "goal",
        "text": "ship it",
    }

    resp = client.post("/comms/post", json=body, headers=chief.headers)

    assert _gated(resp)
    assert '"from": "chief"' in resp.get_json()["error"]


# --- S9: which runs take a cost, and where the limits are ---------------------------------------


def test_the_operator_text_names_max_cost_usd_only_with_a_flow_start_or_retry():
    named = [s for s in _sentences(_operator()) if COST.search(s)]

    assert named, "the Operator text does not say which runs take max_cost_usd"
    for sentence in named:
        assert "flow" in sentence and "retry" in sentence, sentence


def test_the_operator_text_says_goal_board_and_task_runs_are_bounded_by_the_count():
    text = norm(_operator())

    assert "a goal, board or task run" in text
    assert "only the number of runs" in text
    assert not re.search(r"\$\s*\d", text)


def test_the_operator_text_says_to_read_the_session_again_before_quoting_a_limit():
    text = norm(_operator())

    assert "before you quote a limit" in text
    quoted = text.index("before you quote a limit")
    assert "get /chief/session" in text[quoted - 200 : quoted + 200]


# --- S10: a refusal is reported, never worked around --------------------------------------------


def test_the_operator_text_forbids_suggesting_a_way_around_a_deny():
    text = norm(_operator())

    assert "tell the user what was refused and stop" in text
    assert "never suggest a way around a deny" in text
    assert "a different token" in text
    assert "permission settings" in text


# --- after ticket 04: a flow runs the full pipeline headless ------------------------------------


def test_the_operator_text_names_team_and_team_build_as_the_full_pipeline():
    text = norm(_operator())

    assert "team-build" in text
    assert re.search(r"\bteam\b(?!-)", text)
    assert "headless" in text
    for role in ("planner", "designer", "builder", "reviewer", "tester"):
        assert role in text, role


def test_the_flow_start_body_the_text_shows_is_one_the_gate_lets_an_operator_send(app):
    shown = re.findall(r"`(\{[^`]*\"kind\": \"flow\"[^`]*\})`", _operator())

    assert shown, "the Operator text shows no flow start body"
    for body in shown:
        words = ["pathly", "api", "POST", "/runs", body]
        assert problems(words, "operator", app) == []
        parsed = json.loads(re.sub(r"<[^<>\n]*>", "1", body))
        assert parsed["flow"] in ("team", "team-build")
        assert "max_cost_usd" in parsed


# --- after ticket 06: a task waits for an answer -------------------------------------------------


def test_the_operator_text_says_how_to_find_and_free_a_task_waiting_for_an_answer():
    text = norm(_operator())

    assert "waiting_for_answer" in text
    assert "fail_reason" in text
    assert "blocked" in text
    assert "answering" in text and "frees the task" in text
    assert "start the goal again" in text
    reads = [
        words[3]
        for words in examples(_operator())
        if words[2] == "GET" and words[3].startswith("/comms/tasks?")
    ]
    assert reads, "the Operator text shows no read of the tasks"


# --- pathly help: the post types, as the gate classes them --------------------------------------


def test_the_help_line_of_a_post_names_each_type_the_gate_classes_above_post():
    from pathly_orchestrator.chief_cli import HELP
    from pathly_orchestrator.http_server.chief_routes import POST_TYPE_ACTIONS

    line = next(
        line
        for line in HELP.splitlines()
        if line.strip().startswith("POST /comms/post")
    )

    assert "a message, goal or task" not in line
    for kind, action in POST_TYPE_ACTIONS.items():
        assert f'"{kind}"' in line, kind
        assert action in line, action
    assert "any other" in line
