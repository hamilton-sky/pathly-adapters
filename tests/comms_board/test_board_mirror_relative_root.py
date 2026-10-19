"""A project board whose scope is a RELATIVE root is no longer mirrored (chief-agent 08, round 6).

Before the fix a board scope was any string with a ``/`` and the mirror wrote
``<scope>/pathly/project/BOARD.json``, so a project board posted with a relative root such as
``proj/x`` had its ``BOARD.json`` written under the server's working directory. The scope is
request-derived, so the mirror now answers only a normalised absolute root. That is a change for a
caller that kept a relative root: its board is stored and served as before, but no longer exported
to disk (the startup backfill, ``export_project_boards``, goes through the same
``write_board_mirror``). A caller that wants the export names the absolute root. The "Chief gate"
section of ``src/pathly_orchestrator/CLAUDE.md`` says so; this test pins what it says.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator import board_mirror
from pathly_orchestrator.board_mirror import (
    board_from_scope,
    board_mirror_path,
    flush_dirty,
    mark_board_dirty_by_scope,
    write_board_mirror,
)
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import get_all_messages, post_message

RELATIVE = ["proj/x", "./proj/x", "proj/x/", "../proj-b", "a/b"]


@pytest.fixture(autouse=True)
def _quiet_flusher(monkeypatch):
    """No flusher thread: the test drains the dirty set itself."""
    monkeypatch.setattr(board_mirror, "_flusher_started", True)
    board_mirror._dirty.clear()


@pytest.mark.parametrize("scope", RELATIVE)
def test_a_relative_root_is_no_project_board_to_the_mirror(scope):
    assert board_from_scope(scope) is None


@pytest.mark.parametrize("scope", RELATIVE)
def test_a_project_board_with_a_relative_root_writes_no_mirror(
    tmp_path, monkeypatch, scope
):
    work = tmp_path / "server"
    work.mkdir()
    monkeypatch.chdir(work)
    post_message(
        get_db(),
        board="project",
        scope=scope,
        from_agent="human",
        type="note",
        text="kept in the database",
    )

    mark_board_dirty_by_scope(scope)
    flush_dirty(get_db())
    written = write_board_mirror(get_db(), "project", scope, scope)

    assert written is False
    assert list(work.rglob("*")) == []
    assert [p for p in tmp_path.rglob("BOARD.json") if ".pathly" not in p.parts] == []
    # The board itself is untouched: the row is stored and served, only the export is gone.
    rows = get_all_messages(get_db(), "project", scope)
    assert [r["text"] for r in rows] == ["kept in the database"]


def test_the_startup_backfill_exports_no_relative_root_either(tmp_path, monkeypatch):
    work = tmp_path / "server"
    work.mkdir()
    monkeypatch.chdir(work)
    post_message(
        get_db(),
        board="project",
        scope="proj/x",
        from_agent="human",
        type="note",
        text="kept in the database",
    )

    assert (
        board_mirror.export_project_boards(get_db(), "proj/x") == 1
    )  # the global board
    assert list(work.rglob("*")) == []


def test_the_same_root_named_absolutely_is_mirrored(tmp_path):
    root = tmp_path / "proj" / "x"
    root.mkdir(parents=True)
    scope = str(root).replace("\\", "/")
    post_message(
        get_db(),
        board="project",
        scope=scope,
        from_agent="human",
        type="note",
        text="exported",
    )

    assert board_from_scope(scope) == "project"
    assert write_board_mirror(get_db(), "project", scope, scope) is True
    assert board_mirror_path("project", scope, scope) == (
        root / "pathly" / "project" / "BOARD.json"
    )
    assert (root / "pathly" / "project" / "BOARD.json").is_file()
