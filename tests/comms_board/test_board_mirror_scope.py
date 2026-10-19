"""The board mirror writes only for a scope that is a project root or a plain name.

``board_from_scope`` used to call any scope with a ``/`` a project board, so a relative or
traversing scope (``../proj-b``, ``/a/../b``) made ``write_board_mirror`` create
``<scope>/pathly/project/BOARD.json`` wherever the path led, relative to the server's working
directory included. The scope is request-derived (it is the scope of a posted row), so the
mirror now answers only a normalised absolute root on the project board and one plain folder
name on a feature board, and ignores anything else. Every spelling a caller really sends keeps
working: roots with spaces, unicode and a Windows drive letter, feature names with dots, spaces
and unicode.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator import board_mirror
from pathly_orchestrator.board_mirror import (
    board_from_scope,
    board_mirror_path,
    flush_dirty,
    mark_board_dirty,
    mark_board_dirty_by_scope,
    write_board_mirror,
)
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import post_message

ROOTS = [
    "/home/me/proj",
    "/srv/p q/ünï/proj",
    "/tmp/x.y/z",
    "C:/Users/Yafit/proj",
    "d:/a b/c",
    "//server/share/proj",
]
NAMES = [
    "my-feature",
    "feat_1",
    "Q3 plan",
    "café-ü",
    "v1.2.3",
    ".hidden",
    "(interactive)",
    "hq",
]
# Neither a normalised absolute root nor one plain name.
REFUSED = [
    "../proj-b",
    "../../x",
    "rel/dir",
    "a/b",
    "./x",
    "/abs/../x",
    "/abs/./x",
    "/a/b/../../c",
    "C:/x/..",
    "/abs/dir/",
    "C:\\Users\\x",
    "a\\b",
    "C:x",
    "a:b",
    "..",
    ".",
    "...",
    "",
    "x\0y",
]


def _mirrors(root):
    """The board mirrors under ``root``, apart from the global one in the fake home."""
    return [p for p in root.rglob("BOARD.json") if ".pathly" not in p.parts]


@pytest.fixture(autouse=True)
def _quiet_flusher(monkeypatch):
    """No flusher thread: a test drains the dirty set itself, so a write is deterministic."""
    monkeypatch.setattr(board_mirror, "_flusher_started", True)
    board_mirror._dirty.clear()
    yield
    board_mirror._dirty.clear()


@pytest.mark.parametrize("root", ROOTS)
def test_a_normalised_absolute_root_is_a_project_board(root):
    assert board_from_scope(root) == "project"


@pytest.mark.parametrize("name", NAMES)
def test_a_plain_name_is_a_feature_board(name):
    assert board_from_scope(name) == "feature"


def test_global_is_the_global_board():
    assert board_from_scope("global") == "global"


@pytest.mark.parametrize("scope", REFUSED)
def test_any_other_scope_is_no_board(scope):
    assert board_from_scope(scope) is None


@pytest.mark.parametrize("scope", REFUSED)
def test_a_refused_scope_is_not_queued_for_a_rewrite(scope):
    mark_board_dirty_by_scope(scope)

    assert board_mirror._dirty == set()


@pytest.mark.parametrize(
    "scope,board", [("/home/me/proj", "project"), ("a b", "feature")]
)
def test_a_legitimate_scope_is_still_queued(scope, board):
    mark_board_dirty_by_scope(scope)

    assert board_mirror._dirty == {(board, scope)}


@pytest.mark.parametrize("scope", [s for s in REFUSED if s])
def test_a_refused_scope_writes_nothing_even_when_it_is_queued_directly(
    tmp_path, monkeypatch, scope
):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    for board in ("project", "feature"):
        mark_board_dirty(board, scope)

    flush_dirty(get_db())

    assert _mirrors(tmp_path) == []
    assert list(work.rglob("*")) == []


@pytest.mark.parametrize("board", ["project", "feature"])
@pytest.mark.parametrize("scope", [s for s in REFUSED if s])
def test_write_board_mirror_refuses_a_refused_scope(tmp_path, board, scope):
    root = tmp_path / "proj"
    root.mkdir()

    assert write_board_mirror(get_db(), board, scope, str(root)) is False
    assert _mirrors(tmp_path) == []


@pytest.mark.parametrize("scope", ["..", ".", "...", "a/b", "a\\b", "a:b", "x\0y"])
def test_a_feature_mirror_path_is_one_plain_folder_name(tmp_path, scope):
    assert board_mirror_path("feature", scope, str(tmp_path)) is None


@pytest.mark.parametrize("name", NAMES)
def test_a_plain_name_has_a_feature_mirror_path(tmp_path, name):
    path = board_mirror_path("feature", name, str(tmp_path))

    assert path == tmp_path / "pathly" / "features" / name / "BOARD.json"


def test_a_relative_traversing_scope_plants_nothing_through_the_hook(
    tmp_path, monkeypatch
):
    """The reported case, end to end: the hook, the flush and the write."""
    mine = tmp_path / "proj-a"
    other = tmp_path / "proj-b"
    mine.mkdir()
    other.mkdir()
    monkeypatch.chdir(mine)
    post_message(
        get_db(),
        board="feature",
        scope="../proj-b",
        from_agent="chief",
        type="note",
        text="planted",
    )

    mark_board_dirty_by_scope("../proj-b")
    mark_board_dirty_by_scope(f"{mine}/../proj-b")
    flush_dirty(get_db())

    assert list(other.rglob("*")) == []
    assert list(mine.rglob("*")) == []


@pytest.mark.parametrize("root", ["PLAIN", "SPACED", "UNICODE"])
def test_a_legitimate_project_root_still_gets_its_mirror(tmp_path, root):
    name = {"PLAIN": "proj", "SPACED": "my proj", "UNICODE": "prøj-ü"}[root]
    folder = tmp_path / name
    folder.mkdir()
    scope = str(folder).replace("\\", "/")
    post_message(
        get_db(),
        board="project",
        scope=scope,
        from_agent="human",
        type="note",
        text="kept",
    )

    mark_board_dirty_by_scope(scope)
    flush_dirty(get_db())

    assert (folder / "pathly" / "project" / "BOARD.json").is_file()
