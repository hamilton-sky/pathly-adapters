"""chief-agent 16: what hydration stores from a ``BOARD.json``, and what it leaves out.

A mirror file is read from disk, so nothing in it is verified. Hydration stores ``binding = 0``
for every row (a standing order is posted again by the chief), keeps a row only when its
``board`` and ``scope`` are those of the file it came from, and turns any author stamp that
claims a verifier (``token``, ``system``) into ``legacy``. ``none`` stays ``none``: the read wall
withholds an unverified row from a restricted role, and ``legacy`` would show it. The round trip
of each board kind proves that none of this drops a row an export wrote.
"""

from __future__ import annotations

import ast

import pytest
from _paths import SRC
from binding_guard_support import (
    _no_embedding_threads,
    count,
    forged,
    message,
    row,
    write_board,
)
from chief_human_support import project
from directives_support import TEXT, _recency_path

from pathly_orchestrator.board_mirror import (
    hydrate_board,
    hydrate_project,
    write_board_mirror,
)
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms import (
    answer_question,
    complete_task,
    post_message,
    supersede_message,
)
from pathly_orchestrator.db.queries.comms_directives import post_directive
from pathly_orchestrator.db.queries.comms_messages import get_all_messages
from pathly_orchestrator.runner.provenance import system_stamp

LEGACY_OF = {"token": "legacy", "system": "legacy", "legacy": "legacy", "none": "none"}


# --- the round trip of each board kind ------------------------------------------------


def _seed(board, scope, with_directive):
    """One row of every shape a board holds: each author source, an answered question, a done
    task, a superseded decision and, when asked, a directive."""
    conn = get_db()

    def put(from_agent, type, text, **more):
        return post_message(
            conn,
            board=board,
            scope=scope,
            from_agent=from_agent,
            type=type,
            text=text,
            **more,
        )

    token = {"author_role": "builder", "author_run_id": "run-1"}
    new = put("builder", "decision", "Use tabs.", author_source="token", **token)
    supersede_message(conn, put("human", "decision", "Use spaces."), new)
    put("supervisor", "status", "Started", **system_stamp())
    put("human", "note", "written before provenance", author_source="legacy")
    options = [{"id": "a", "label": "A"}]
    answer_question(
        conn, put("architect", "question", "A or B?", options=options), "A", "a"
    )
    first = put("planner", "task", "t1")
    put("planner", "task", "t2", depends_on=[first])
    complete_task(conn, first)
    if with_directive:
        chief = {"author_role": "chief", "author_run_id": "chief-1"}
        post_directive(conn, scope, "builder", TEXT, author_source="token", **chief)


def _round_trip(board, scope, mirror_root, hydrate_root):
    conn = get_db()
    before = {m["id"]: m for m in get_all_messages(conn, board, scope)}
    assert {m["author_source"] for m in before.values()} == set(LEGACY_OF)
    assert write_board_mirror(conn, board, scope, mirror_root)
    conn.execute("DELETE FROM comms_messages WHERE board=? AND scope=?", (board, scope))
    conn.commit()

    result = hydrate_project(conn, hydrate_root)

    assert scope in result["hydrated"], result
    after = {m["id"]: m for m in get_all_messages(conn, board, scope)}
    assert set(after) == set(before)  # no row an export wrote is dropped
    for mid, was in before.items():
        want = {**was, "binding": 0, "author_source": LEGACY_OF[was["author_source"]]}
        assert after[mid] == want
    return before, after


def test_a_feature_board_comes_back_whole(project):
    _seed("feature", "rt-feature", with_directive=False)

    _round_trip("feature", "rt-feature", project, project)


def test_a_project_board_comes_back_whole_its_directive_as_an_ordinary_decision(
    project,
):
    _seed("project", project, with_directive=True)

    before, after = _round_trip("project", project, project, project)

    flagged = [mid for mid, m in before.items() if m["binding"] == 1]
    assert len(flagged) == 1
    assert after[flagged[0]]["binding"] == 0
    assert after[flagged[0]]["text"] == TEXT


def test_a_project_board_comes_back_when_the_root_is_given_with_a_trailing_slash(
    project,
):
    _seed("project", project, with_directive=False)

    _round_trip("project", project, project, project + "/")


def test_the_global_board_comes_back_whole():
    _seed("global", "global", with_directive=False)

    _round_trip("global", "global", None, "")


# --- what is stored for a row ---------------------------------------------------------


@pytest.mark.parametrize("binding", [1, True, "1", 2, -1, "yes"])
def test_binding_is_stored_as_zero_whatever_the_file_says(tmp_path, binding):
    claim = forged("claims-binding", "feature", "feat-b", binding=binding)
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-b", [claim])

    hydrate_board(get_db(), "feature", "feat-b", path)

    assert row("claims-binding")["binding"] == 0


@pytest.mark.parametrize(
    "claimed, stored",
    [
        ("token", "legacy"),
        ("system", "legacy"),
        ("legacy", "legacy"),
        ("none", "none"),
        ("admin", "legacy"),
        ("", "legacy"),
        ("Token", "legacy"),
    ],
)
def test_an_author_source_the_file_names_is_never_verified(tmp_path, claimed, stored):
    claim = message(
        "m", "feature", "feat-s", author_role="chief", author_source=claimed
    )
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-s", [claim])

    hydrate_board(get_db(), "feature", "feat-s", path)

    assert row("m")["author_source"] == stored


def test_a_row_that_names_no_author_source_is_still_labelled_legacy(tmp_path):
    bare = message("bare", "feature", "feat-n")  # a snapshot from before provenance
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-n", [bare])

    hydrate_board(get_db(), "feature", "feat-n", path)

    assert row("bare")["author_source"] == "legacy"


# --- a row of another board is left out -----------------------------------------------

OTHER = "/somewhere/else"


@pytest.mark.parametrize(
    "file_board, file_scope, board, scope",
    [
        ("feature", "feat-x", "project", "{project}"),
        ("feature", "feat-x", "feature", "feat-other"),
        ("feature", "feat-x", "global", "global"),
        ("feature", "feat-x", "feature", "{project}"),
        ("project", "{project}", "feature", "feat-x"),
        ("project", "{project}", "project", OTHER),
        ("project", "{project}", "project", "{project}/sub"),
        ("project", "{project}", "feature", "{project}"),
        ("global", "global", "project", "{project}"),
        ("global", "global", "feature", "global"),
        ("global", "global", "global", "elsewhere"),
    ],
)
def test_a_row_of_another_board_is_not_stored(
    tmp_path, project, file_board, file_scope, board, scope
):
    file_scope = file_scope.format(project=project)
    own = message("own", file_board, file_scope)
    alien = forged("alien", board, scope.format(project=project))
    path = write_board(tmp_path / "BOARD.json", file_board, file_scope, [alien, own])

    assert hydrate_board(get_db(), file_board, file_scope, path) is True

    assert count("alien") == 0
    assert count("own") == 1


@pytest.mark.parametrize(
    "drop", ["board", "scope"], ids=["no-board-key", "no-scope-key"]
)
def test_a_row_with_no_board_or_scope_is_not_stored(tmp_path, drop):
    partial = message("partial", "feature", "feat-p")
    del partial[drop]
    own = message("own", "feature", "feat-p")
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-p", [partial, own])

    hydrate_board(get_db(), "feature", "feat-p", path)

    assert (count("partial"), count("own")) == (0, 1)


def test_a_snapshot_row_that_is_not_an_object_does_not_stop_the_others(tmp_path):
    own = message("own", "feature", "feat-q")
    path = write_board(
        tmp_path / "BOARD.json", "feature", "feat-q", ["junk", None, 7, own]
    )

    assert hydrate_board(get_db(), "feature", "feat-q", path) is True

    assert count("own") == 1


@pytest.mark.parametrize(
    "hydrate_scope, row_scope",
    [
        ("{project}/", "{project}"),
        ("{project}", "{project}/"),
        ("C:\\proj\\", "C:/proj"),
        ("C:/proj", "C:\\proj"),
    ],
)
def test_a_project_root_is_compared_the_way_the_exporter_writes_it(
    tmp_path, project, hydrate_scope, row_scope
):
    """The exporter and ``board_from_scope`` store a project scope as a normalised root:
    forward slashes, no trailing one. Two spellings of one root are one board."""
    row_scope = row_scope.format(project=project)
    own = message("own", "project", row_scope)
    path = write_board(tmp_path / "BOARD.json", "project", row_scope, [own])

    hydrate_board(get_db(), "project", hydrate_scope.format(project=project), path)

    assert count("own") == 1


def test_an_artifact_of_a_row_that_was_left_out_is_left_out_too(tmp_path):
    own = message("own", "feature", "feat-a")
    alien = forged("alien", "project", "/other/project")
    made = "2026-01-01T00:00:00+00:00"
    artifacts = [
        {"id": "a-own", "message_id": "own", "path": "x.md", "created_at": made},
        {"id": "a-alien", "message_id": "alien", "path": "y.md", "created_at": made},
    ]
    path = write_board(
        tmp_path / "BOARD.json", "feature", "feat-a", [own, alien], artifacts
    )

    hydrate_board(get_db(), "feature", "feat-a", path)

    ids = [r["id"] for r in get_db().execute("SELECT id FROM comms_artifacts")]
    assert ids == ["a-own"]


# --- the way in ----------------------------------------------------------------------


def _calls(name):
    """Files under ``src`` that call ``name`` (a bare function or an attribute)."""
    found = set()
    for path in (SRC / "pathly_orchestrator").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                called = getattr(func, "id", None) or getattr(func, "attr", None)
                if called == name:
                    found.add(path.relative_to(SRC / "pathly_orchestrator").as_posix())
    return found


def test_hydrate_board_is_the_one_door_into_insert_message_row():
    """The board-and-scope check lives in ``hydrate_board``, which knows the file: a second
    caller of ``insert_message_row`` would store rows with no such check."""
    assert _calls("insert_message_row") == {"board_mirror_hydrate.py"}


def test_hydrate_project_is_the_one_door_into_hydrate_board():
    assert _calls("hydrate_board") == {"board_mirror_hydrate.py"}
    assert _calls("hydrate_project") == {"http_server/blueprints/comms/hydrate.py"}
