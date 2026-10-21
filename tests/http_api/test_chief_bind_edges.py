"""chief-agent 14 (edges): where an id is placed from, and what a malformed one does.

``test_chief_bind.py`` holds the cases the ticket names. These are the rest of the rule: a run is
placed by its history first, then by the registry, then by the board it holds; a message by the
board and scope of its row, which must be a plain folder name off the project board; an id the gate
cannot read as one is refused, never a 500; and the table says what is bound and what is not.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest
from chief_bind_support import (
    DEMO,
    _boards_are_free,
    acknowledge,
    feature_dir,
    feature_row,
    hold,
    is_refused,
    project_row,
    record_run,
    row,
    rows_named,
    run_call,
    shown,
    stubs,
)
from chief_cite_support import (
    Session,
    acknowledged_by,
    answer_rows,
    citations,
    db,
    idle,
    later,
)
from chief_gate_support import (
    _chief,
    _passed,
    app,
    client,
    other_project,
    project,
    started,
)

# --- a run is placed by its history, then the registry, then the board it holds -------------


def test_a_run_only_the_registry_knows_is_placed_by_its_state(
    client, project, other_project, idle
):
    chief = _chief("operator", project)
    idle("ours")
    idle("theirs", other_project)

    ours = run_call(client, chief, project, "run-ours", "pause")
    theirs = run_call(client, chief, project, "run-theirs", "pause")

    assert _passed(ours), shown(ours)
    assert is_refused(theirs), shown(theirs)


def test_a_run_only_the_board_lock_knows_is_placed_by_its_board(
    client, project, other_project
):
    chief = _chief("operator", project)
    feature_dir(project)
    hold("project", str(project), "run-ours")
    hold("project", str(other_project), "run-theirs")
    hold("feature", DEMO, "run-feature")
    hold("global", "global", "run-global")

    def stop(run_id):
        return run_call(client, chief, project, run_id, "stop")

    assert _passed(stop("run-ours")) and _passed(stop("run-feature"))
    assert is_refused(stop("run-theirs"))
    assert is_refused(stop("run-global"))


def test_the_history_decides_when_it_and_the_registry_disagree(
    client, project, other_project, idle
):
    chief = _chief("operator", project)
    idle("both")
    record_run(other_project, "run-both")

    resp = run_call(client, chief, project, "run-both", "pause")

    assert is_refused(resp), shown(resp)


# --- a message is in the project by the board and scope of its row --------------------------


def _folders_that_would_pass_without_the_name_rule(project) -> None:
    """Make the folder each odd scope below would name exist under the project, so only the rule
    that a feature is one plain folder name refuses it."""
    features = project / "pathly" / "features"
    for name in (DEMO, ".archive", "demo\\x", "C:", "a/b"):
        (features / name).mkdir(parents=True, exist_ok=True)
    (project / "pathly" / "proj-b").mkdir()


@pytest.mark.parametrize(
    "board,scope",
    [
        ("feature", "../proj-b"),
        ("feature", "a/b"),
        ("feature", "."),
        ("feature", ".."),
        ("feature", ".archive"),
        ("feature", ""),
        ("feature", "demo\\x"),
        ("feature", "C:"),
        ("bogus", DEMO),
    ],
)
def test_a_feature_row_with_a_scope_that_is_not_a_plain_folder_name_is_refused(
    client, project, board, scope
):
    chief = _chief("operator", project)
    _folders_that_would_pass_without_the_name_rule(project)
    assert _passed(acknowledge(client, chief, feature_row(DEMO))), "the control passes"

    resp = acknowledge(client, chief, row(board, scope))

    assert is_refused(resp), shown(resp)


def test_a_feature_row_scoped_by_the_chiefs_root_is_refused(client, project):
    """A scope that is a path is not a feature name, even when it is the chief's own root."""
    chief = _chief("operator", project)

    resp = acknowledge(client, chief, feature_row(str(project)))

    assert is_refused(resp), shown(resp)


def test_a_project_row_is_the_chiefs_when_its_scope_spells_the_root(
    client, project, other_project
):
    chief = _chief("operator", project)

    assert _passed(acknowledge(client, chief, row("project", str(project) + "/")))
    assert is_refused(acknowledge(client, chief, row("project", str(project) + "-b")))
    assert is_refused(acknowledge(client, chief, row("project", "project")))
    assert is_refused(acknowledge(client, chief, row("project", "")))
    assert is_refused(acknowledge(client, chief, row("project", str(other_project))))


def test_a_row_that_was_deleted_is_still_the_other_projects(
    client, project, other_project
):
    chief = _chief("operator", project)
    theirs = project_row(other_project)
    db().execute(
        "UPDATE comms_messages SET deleted_at = ? WHERE id = ?", ("then", theirs)
    )
    db().commit()

    resp = acknowledge(client, chief, theirs)

    assert is_refused(resp), shown(resp)


def test_the_gate_and_the_route_read_an_id_the_same_way(client, project, other_project):
    """A padded id is not the row's id to the route either (it finds no row and does nothing),
    so the gate does not have to read it as the other project's."""
    chief = _chief("operator", project)
    theirs = project_row(other_project)

    for padded in (f" {theirs}", f"{theirs} ", theirs.upper()):
        resp = acknowledge(client, chief, padded)

        assert resp.status_code in (200, 403), shown(resp)
    assert acknowledged_by(theirs) == []


# --- an answer to a question of another project is refused before a message is spent --------


def test_an_answer_to_a_question_of_another_project_is_refused(
    client, project, other_project
):
    chief = Session("operator", project)
    theirs = row("project", str(other_project), "question")
    ours = row("project", str(project), "question")
    later()
    typed = chief.type("CSV, please")

    def answer(question_id):
        body = {"question_id": question_id, "cite": typed}
        return client.post("/comms/answer", json=body, headers=chief.headers)

    refused = answer(theirs)

    assert is_refused(refused), shown(refused)
    assert citations() == [] and answer_rows(theirs) == []
    allowed = answer(ours)
    assert allowed.status_code == 200, shown(allowed)
    assert answer_rows(ours) == ["CSV, please"]


# --- the run id a post carries is a stamp: another project's is refused, an unknown one is not


def _post(client, chief, words, **extra):
    body = {"feature": DEMO, "from": "chief", "type": "status", "text": words, **extra}
    return client.post("/comms/post", json=body, headers=chief.headers)


def test_a_post_stamped_with_a_run_of_another_project_is_refused(
    client, project, other_project, idle
):
    chief = _chief("operator", project)
    record_run(other_project, "run-theirs")
    record_run(project, "run-ours")
    idle("registered")

    refused = _post(client, chief, "stamped theirs", run_id="run-theirs")

    assert is_refused(refused), shown(refused)
    assert rows_named("stamped theirs") == 0
    for words, run_id in (
        ("stamped ours", "run-ours"),
        ("stamped by the registry", "run-registered"),
        ("stamped by the chief itself", chief.run_id),
        ("stamped by a run that is gone", "run-gone"),
        ("stamped blank", ""),
        ("stamped null", None),
    ):
        resp = _post(client, chief, words, run_id=run_id)

        assert resp.status_code == 200, (words, shown(resp))
        assert rows_named(words) == 1


# --- an id the gate cannot read is refused, and never a 500 ---------------------------------

WEIRD = [
    ("number", 7),
    ("true", True),
    ("list", ["a"]),
    ("map", {"a": 1}),
    ("long", "x" * 10_000),
    ("nul", "a\x00b"),
    ("newline", "a\nb"),
    ("delete", "a\x7fb"),
    ("surrogate", "\ud800"),
]
# (route, the key that names an id, the rest of a body the route would take)
POST_BODY = {"type": "status", "feature": DEMO, "text": "t"}
NAMES_AN_ID = [
    ("/comms/acknowledge", "message_id", {"agent": "chief"}),
    ("/comms/supersede", "old_id", {"new_id": "n"}),
    ("/comms/supersede", "new_id", {"old_id": "o"}),
    ("/comms/answer", "question_id", {"cite": 1}),
    ("/comms/goals/run", "goal_id", {}),
    ("/comms/goals/stop", "goal_id", {}),
    ("/comms/goals/decompose", "goal_id", {}),
    ("/runs", "goal_id", {"kind": "goal"}),
    ("/comms/tasks/run", "message_id", {}),
    ("/comms/tasks/stop", "message_id", {}),
    ("/comms/post", "goal_id", POST_BODY),
    ("/comms/post", "run_id", POST_BODY),
]


@pytest.mark.parametrize(
    "rule,key,rest", NAMES_AN_ID, ids=[f"{r} {k}" for r, k, _ in NAMES_AN_ID]
)
@pytest.mark.parametrize("label,value", WEIRD, ids=[w[0] for w in WEIRD])
def test_a_malformed_id_is_a_4xx_and_never_a_500(
    client, project, stubs, started, rule, key, rest, label, value
):
    chief = _chief("operator", project)
    body = {"project_root": str(project), "from": "chief", **rest, key: value}

    resp = client.post(rule, json=body, headers=chief.headers)

    assert resp.status_code in (400, 403), (rule, key, label, shown(resp))


@pytest.mark.parametrize("action", ["pause", "stop", "retry"])
@pytest.mark.parametrize(
    "run_id",
    ["x" * 5000, "a\x00b", "a\nb", "a\x7fb", "a\tb", "café", " run-ours", "run-ours "],
    ids=["long", "nul", "newline", "delete", "tab", "unicode", "pad-left", "pad-right"],
)
def test_a_run_id_the_gate_cannot_place_is_a_403_and_never_a_500(
    client, project, action, run_id
):
    chief = _chief("operator", project)
    record_run(project, "run-ours")

    body = {"project_root": str(project)}
    resp = client.post(
        f"/runs/{quote(run_id, safe='')}/{action}", json=body, headers=chief.headers
    )

    assert is_refused(resp), (action, run_id, shown(resp))


@pytest.mark.parametrize("value", ["", "   ", None])
def test_a_blank_id_names_nothing_and_the_route_answers_400(client, project, value):
    chief = _chief("operator", project)
    body = {"project_root": str(project), "message_id": value, "agent": "chief"}

    resp = client.post("/comms/acknowledge", json=body, headers=chief.headers)

    assert _passed(resp) and resp.status_code == 400, shown(resp)


def test_a_topic_the_gate_cannot_look_up_spends_no_citation(client, project):
    """The ``topic`` of ``/runner/agent-answer`` is held by the cite rule (ticket 10); a lone
    surrogate in it used to reach SQLite when the citation was recorded, and a 500 came back.
    """
    chief = Session("operator", project)
    later()
    typed = chief.type("CSV, please")

    for topic in ("\ud800", "a\x00b", "x" * 10_000):
        body = {"topic": topic, "cite": typed}
        resp = client.post("/runner/agent-answer", json=body, headers=chief.headers)

        assert resp.status_code in (400, 404, 409), (topic[:5], shown(resp))
    assert citations() == []
