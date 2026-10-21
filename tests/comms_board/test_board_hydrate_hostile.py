"""chief-agent 16 (round 2): a hostile ``BOARD.json`` cannot stop hydration, or plant an artifact.

``hydrate_board`` reads a file nobody verified and is documented never to raise. The ids in it
are whatever the file says: a list or a dict is unhashable, so a set or a ``in`` test over the
ids raised ``TypeError`` out of the function, and ``hydrate_project`` (whose outer ``try``
swallows it) then skipped every board after the bad one. Here each such value sits on a kept
row, on a row that is left out and on an artifact, and the good rows around it must still
import. An artifact is stored only when the file also holds the message row it points at.
"""

from __future__ import annotations

import json
from pathlib import Path

import binding_support
import pytest
from binding_guard_support import _no_embedding_threads, message, write_board
from chief_human_support import project

from pathly_orchestrator.board_mirror import hydrate_board, hydrate_project
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import get_all_messages

MADE = "2026-01-01T00:00:00+00:00"
UNHASHABLE = [[], [1], {}, {"id": "x"}, [[]], [{}]]
NOT_STRINGS = [7, 1.5, True, None]


def artifact(aid, message_id) -> dict:
    return {"id": aid, "message_id": message_id, "path": "x.md", "created_at": MADE}


def message_ids(board, scope) -> list:
    return [m["id"] for m in get_all_messages(get_db(), board, scope)]


def artifact_ids() -> list:
    rows = get_db().execute("SELECT id FROM comms_artifacts ORDER BY id").fetchall()
    return [r["id"] for r in rows]


# --- a message row with an id that is not a string ---------------------------------------


@pytest.mark.parametrize("bad", UNHASHABLE + NOT_STRINGS, ids=repr)
def test_a_kept_row_whose_id_is_not_a_string_stops_nothing(tmp_path, bad):
    """Not stored (an export writes a string id), and the good row next to it is."""
    hostile = message("x", "feature", "feat-k", id=bad)
    own = message("own", "feature", "feat-k")
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-k", [hostile, own])

    assert hydrate_board(get_db(), "feature", "feat-k", path) is True

    assert message_ids("feature", "feat-k") == ["own"]


@pytest.mark.parametrize("bad", UNHASHABLE, ids=repr)
@pytest.mark.parametrize(
    "board, scope",
    [("project", "{project}"), ("feature", "feat-other"), ("global", "global")],
)
def test_a_left_out_row_whose_id_is_unhashable_stops_nothing(
    tmp_path, project, bad, board, scope
):
    alien = message("x", board, scope.format(project=project), id=bad)
    own = message("own", "feature", "feat-l")
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-l", [alien, own])

    assert hydrate_board(get_db(), "feature", "feat-l", path) is True

    assert message_ids("feature", "feat-l") == ["own"]


# --- an artifact with a message_id that is not a string ----------------------------------


@pytest.mark.parametrize("bad", UNHASHABLE + NOT_STRINGS, ids=repr)
def test_an_artifact_whose_message_id_is_not_a_string_is_left_out(tmp_path, bad):
    own = message("own", "feature", "feat-m")
    artifacts = [artifact("a-bad", bad), artifact("a-own", "own")]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-m", [own], artifacts)

    assert hydrate_board(get_db(), "feature", "feat-m", path) is True

    assert message_ids("feature", "feat-m") == ["own"]
    assert artifact_ids() == ["a-own"]


def test_an_artifact_entry_that_is_not_an_object_stops_nothing(tmp_path):
    own = message("own", "feature", "feat-j")
    junk = ["junk", None, 7, [1], artifact("a-own", "own")]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-j", [own], junk)

    assert hydrate_board(get_db(), "feature", "feat-j", path) is True

    assert artifact_ids() == ["a-own"]


# --- an artifact is kept only when its message row is in the file -------------------------


def test_an_artifact_on_an_id_the_file_does_not_hold_is_not_stored(tmp_path, project):
    """The planted artifact points at a row of another board that the DB already holds."""
    elsewhere = binding_support.directive("Never push.", scope=project)
    own = message("own", "feature", "feat-p")
    artifacts = [
        artifact("a-planted", elsewhere),
        artifact("a-nowhere", "no-such-message"),
        artifact("a-own", "own"),
    ]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-p", [own], artifacts)

    assert hydrate_board(get_db(), "feature", "feat-p", path) is True

    assert artifact_ids() == ["a-own"]


def test_every_artifact_of_a_kept_row_is_stored(tmp_path):
    rows = [message("one", "feature", "feat-n"), message("two", "feature", "feat-n")]
    artifacts = [artifact("a-1", "one"), artifact("a-2", "one"), artifact("a-3", "two")]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-n", rows, artifacts)

    hydrate_board(get_db(), "feature", "feat-n", path)

    assert artifact_ids() == ["a-1", "a-2", "a-3"]


# --- a file or a list of the wrong shape ------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["[]", "[1, 2]", '"text"', "5", "null", "true", "", "{not json"]
)
def test_a_file_that_is_not_a_json_object_imports_nothing(tmp_path, raw):
    path = tmp_path / "BOARD.json"
    path.write_text(raw, encoding="utf-8")

    assert hydrate_board(get_db(), "feature", "feat-o", path) is False

    assert message_ids("feature", "feat-o") == []


def _write_snapshot(path, scope, **keys):
    path.write_text(
        json.dumps({"board": "feature", "scope": scope, **keys}), encoding="utf-8"
    )
    return path


@pytest.mark.parametrize("bad", [5, "abc", {"id": "x"}, None, True], ids=repr)
def test_a_messages_value_that_is_not_a_list_imports_nothing(tmp_path, bad):
    path = _write_snapshot(
        tmp_path / "BOARD.json",
        "feat-w",
        messages=bad,
        artifacts=[artifact("a-1", "x")],
    )

    assert hydrate_board(get_db(), "feature", "feat-w", path) is True

    assert message_ids("feature", "feat-w") == []
    assert artifact_ids() == []


@pytest.mark.parametrize("bad", [7, "abc", {"id": "a"}, None, True], ids=repr)
def test_an_artifacts_value_that_is_not_a_list_still_imports_the_messages(
    tmp_path, bad
):
    own = message("own", "feature", "feat-v")
    path = _write_snapshot(
        tmp_path / "BOARD.json", "feat-v", messages=[own], artifacts=bad
    )

    assert hydrate_board(get_db(), "feature", "feat-v", path) is True

    assert message_ids("feature", "feat-v") == ["own"]
    assert artifact_ids() == []


# --- one hostile file does not stop the other boards -------------------------------------


def _poison(kind, project):
    """The content of the project board's file (the first candidate ``hydrate_project`` reads):
    the good row ``p-own`` next to one hostile entry, or a file that is no object at all.
    """
    own = message("p-own", "project", project)
    return {
        "id-list": ([message("x", "project", project, id=[1]), own], []),
        "id-dict": ([message("x", "project", project, id={}), own], []),
        "left-out-id": ([message("x", "feature", "feat-a", id=[1]), own], []),
        "artifact-id": ([own], [artifact("a-bad", [1]), artifact("a-p", "p-own")]),
        "no-object": None,
    }[kind]


@pytest.mark.parametrize(
    "kind", ["id-list", "id-dict", "left-out-id", "artifact-id", "no-object"]
)
def test_one_hostile_entry_in_the_project_file_does_not_stop_the_other_boards(
    project, kind
):
    conn = (
        get_db()
    )  # first: opening the DB rewrites the global BOARD.json (an empty one)
    root = Path(project)
    poison = _poison(kind, project)
    project_file = root / "pathly" / "project" / "BOARD.json"
    if poison is None:
        project_file.parent.mkdir(parents=True)
        project_file.write_text("[1, 2, 3]", encoding="utf-8")
    else:
        write_board(project_file, "project", project, *poison)
    for feat in ("feat-a", "feat-b"):
        rows = [message(f"{feat}-row", "feature", feat)]
        write_board(
            root / "pathly" / "features" / feat / "BOARD.json", "feature", feat, rows
        )
    global_file = Path.home() / ".pathly" / "global" / "BOARD.json"
    write_board(global_file, "global", "global", [message("g-row", "global", "global")])

    result = hydrate_project(conn, project)

    assert {"feat-a", "feat-b", "global"} <= set(result["hydrated"]), result
    assert message_ids("feature", "feat-a") == ["feat-a-row"]
    assert message_ids("feature", "feat-b") == ["feat-b-row"]
    assert message_ids("global", "global") == ["g-row"]
    if poison is None:
        assert project in result["skipped"]
        assert message_ids("project", project) == []
    else:
        assert project in result["hydrated"]
        assert message_ids("project", project) == ["p-own"]
