"""chief-agent 20, B10 to B12: three holes of board hydration (``BOARD.json`` into an empty board).

* B10: a message row needs an ``id`` that is a string with something in it after stripping; ``""``
  and ``" "`` landed in the table with a blank primary key.
* B11: an artifact is inserted only when its message exists in the database under this file's own
  board and scope after the message rows went in. A file row that reuses the id of a message of
  another board (the insert is a no-op) plus an artifact for that id used to put the artifact, with
  a path of the file's choosing, on the other board's message.
* B12: a file that adds nothing is not "hydrated": ``hydrate_board`` returns True only when at least
  one message row of the file is in the database under that board and scope afterwards, so
  ``hydrate_project`` lists such a scope under ``skipped`` (a clone at a different path, whose
  project-board rows all name the exporter's root, is the usual case).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from binding_guard_support import _no_embedding_threads, message, write_board
from chief_human_support import project
from mirror_drain_support import _mirrors_are_drained

from pathly_orchestrator.board_mirror import hydrate_board, hydrate_project
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import (
    get_all_messages,
    insert_message_row,
)

MADE = "2026-01-01T00:00:00+00:00"
BLANKS = ["", " ", "   ", "\t", "\n", " \t\n "]


def artifact(aid: str, message_id: str, path: str = "x.md") -> dict:
    return {"id": aid, "message_id": message_id, "path": path, "created_at": MADE}


def message_ids(board: str, scope: str) -> list[str]:
    return [m["id"] for m in get_all_messages(get_db(), board, scope)]


def artifacts() -> list[tuple[str, str, str]]:
    rows = get_db().execute(
        "SELECT id, message_id, path FROM comms_artifacts ORDER BY id"
    )
    return [tuple(r) for r in rows.fetchall()]


def total_rows() -> int:
    return get_db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]


# --- B10: a blank id -----------------------------------------------------------------------------


@pytest.mark.parametrize("blank", BLANKS, ids=repr)
def test_a_row_with_a_blank_id_is_left_out_and_the_rows_around_it_are_kept(
    tmp_path, blank
):
    rows = [
        message("first", "feature", "feat-b"),
        message(blank, "feature", "feat-b"),
        message("second", "feature", "feat-b"),
    ]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-b", rows)

    assert hydrate_board(get_db(), "feature", "feat-b", path) is True

    assert message_ids("feature", "feat-b") == ["first", "second"]
    assert total_rows() == 2


@pytest.mark.parametrize("blank", BLANKS, ids=repr)
def test_a_blank_id_never_reaches_the_table(tmp_path, blank):
    path = write_board(
        tmp_path / "BOARD.json",
        "feature",
        "feat-b",
        [message(blank, "feature", "feat-b")],
    )

    hydrate_board(get_db(), "feature", "feat-b", path)

    ids = [r[0] for r in get_db().execute("SELECT id FROM comms_messages")]
    assert [i for i in ids if not i.strip()] == []


def test_an_id_with_something_in_it_after_stripping_is_kept(tmp_path):
    rows = [message("a", "feature", "feat-b"), message("a b", "feature", "feat-b")]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-b", rows)

    assert hydrate_board(get_db(), "feature", "feat-b", path) is True

    assert sorted(message_ids("feature", "feat-b")) == ["a", "a b"]


# --- B11: an artifact on a row the file did not insert ---------------------------------------------


def _decoy(tmp_path: Path, *, with_own_row: bool) -> Path:
    """A message on (feature, other); a file for (feature, demo) that reuses its id and holds an
    artifact for it (and, optionally, a row of its own with an artifact too)."""
    insert_message_row(get_db(), message("m1", "feature", "other", text="theirs"))
    rows = [message("m1", "feature", "demo", text="a file's claim")]
    claims = [artifact("a-decoy", "m1", path="../../etc/passwd")]
    if with_own_row:
        rows.append(message("own", "feature", "demo"))
        claims.append(artifact("a-own", "own"))
    return write_board(tmp_path / "BOARD.json", "feature", "demo", rows, claims)


def test_an_artifact_is_not_attached_to_a_message_of_another_board(tmp_path):
    path = _decoy(tmp_path, with_own_row=False)

    hydrate_board(get_db(), "feature", "demo", path)

    assert artifacts() == []
    assert message_ids("feature", "other") == ["m1"]
    assert get_all_messages(get_db(), "feature", "other")[0]["text"] == "theirs"
    assert message_ids("feature", "demo") == []


def test_the_decoy_artifact_is_left_out_while_the_files_own_rows_and_artifacts_land(
    tmp_path,
):
    path = _decoy(tmp_path, with_own_row=True)

    assert hydrate_board(get_db(), "feature", "demo", path) is True

    assert artifacts() == [("a-own", "own", "x.md")]
    assert message_ids("feature", "demo") == ["own"]
    assert message_ids("feature", "other") == ["m1"]


def test_the_normal_case_still_imports_its_artifacts(tmp_path):
    rows = [message("one", "feature", "feat-n"), message("two", "feature", "feat-n")]
    claims = [artifact("a-1", "one"), artifact("a-2", "one"), artifact("a-3", "two")]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-n", rows, claims)

    assert hydrate_board(get_db(), "feature", "feat-n", path) is True

    assert [a[:2] for a in artifacts()] == [
        ("a-1", "one"),
        ("a-2", "one"),
        ("a-3", "two"),
    ]


# --- B12: a file that adds nothing ---------------------------------------------------------------


@pytest.mark.parametrize(
    "board, scope",
    [("project", "/elsewhere"), ("feature", "feat-other"), ("global", "global")],
)
def test_a_file_whose_rows_all_name_another_scope_is_not_hydrated(
    tmp_path, board, scope
):
    rows = [message("x", board, scope), message("y", board, scope)]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-e", rows)

    assert hydrate_board(get_db(), "feature", "feat-e", path) is False

    assert message_ids("feature", "feat-e") == []
    assert total_rows() == 0


def test_a_file_with_no_message_rows_at_all_is_not_hydrated(tmp_path):
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-e", [], [])

    assert hydrate_board(get_db(), "feature", "feat-e", path) is False


def test_a_file_with_one_row_of_its_own_among_alien_ones_is_hydrated(tmp_path):
    rows = [message("x", "feature", "feat-other"), message("own", "feature", "feat-e")]
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-e", rows)

    assert hydrate_board(get_db(), "feature", "feat-e", path) is True


def test_a_file_whose_every_row_is_already_in_another_board_is_not_hydrated(tmp_path):
    insert_message_row(get_db(), message("m1", "feature", "other"))
    path = write_board(
        tmp_path / "BOARD.json",
        "feature",
        "demo",
        [message("m1", "feature", "demo")],
        [artifact("a-1", "m1")],
    )

    assert hydrate_board(get_db(), "feature", "demo", path) is False


def test_hydrate_project_lists_a_board_that_stayed_empty_under_skipped(project):
    root = Path(project)
    conn = (
        get_db()
    )  # first: opening the DB rewrites the global BOARD.json (an empty one)
    alien = [message("a", "feature", "somewhere-else")]
    write_board(
        root / "pathly" / "features" / "demo" / "BOARD.json", "feature", "demo", alien
    )
    own = [message("own", "feature", "feat-ok")]
    write_board(
        root / "pathly" / "features" / "feat-ok" / "BOARD.json",
        "feature",
        "feat-ok",
        own,
    )

    result = hydrate_project(conn, project)

    assert result["hydrated"] == ["feat-ok"]
    assert result["skipped"] == ["demo", "global"]
    assert message_ids("feature", "demo") == []


def test_a_clone_at_another_path_has_its_project_scope_skipped(project):
    """Every row of the project board names the exporter's root, so none belongs here."""
    conn = get_db()
    exporter = "/home/someone-else/proj"
    rows = [message("p1", "project", exporter), message("p2", "project", exporter)]
    write_board(
        Path(project) / "pathly" / "project" / "BOARD.json", "project", exporter, rows
    )

    result = hydrate_project(conn, project)

    assert project not in result["hydrated"]
    assert project in result["skipped"]
    assert message_ids("project", project) == []
    assert message_ids("project", exporter) == []
