"""``scope_names.normalise_root``: the one way to write a project root as a key.

Four modules used to spell ``root.replace("\\", "/").rstrip("/")`` themselves, and the chief's copy
turned a bare drive root ``C:\\`` into ``C:``, which names the current folder of drive C and not its
root. The function drops the backslashes and the trailing slashes, keeps one ``/`` for a root that
is only a separator or a drive, and leaves the empty string empty. The callers use it, so they
cannot disagree.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.scope_names import normalise_root

SPELLINGS = [
    ("/p/", "/p"),
    ("/p", "/p"),
    ("/p//", "/p"),
    ("C:\\Users\\Yafit\\proj\\", "C:/Users/Yafit/proj"),
    ("C:\\Users\\Yafit\\proj", "C:/Users/Yafit/proj"),
    ("C:/Users/Yafit/proj/", "C:/Users/Yafit/proj"),
    ("C:\\", "C:/"),
    ("C:/", "C:/"),
    ("c:\\\\", "c:/"),
    ("/", "/"),
    ("//", "/"),
    ("\\", "/"),
    ("", ""),
]


@pytest.mark.parametrize("value,key", SPELLINGS)
def test_a_root_is_written_one_way(value, key):
    assert normalise_root(value) == key


@pytest.mark.parametrize("value,key", SPELLINGS)
def test_a_key_is_its_own_key(value, key):
    assert normalise_root(key) == key


@pytest.mark.parametrize("value", ["C:\\", "C:/", "/", "//", "\\"])
def test_a_bare_root_is_never_the_current_folder_of_a_drive(value):
    key = normalise_root(value)
    assert key.endswith("/")
    assert key not in ("C:", "")


def test_nothing_else_is_changed():
    """No trimming, no case change, no ``.`` or ``..`` collapse, no host switch."""
    assert normalise_root(" /p ") == " /p "
    assert normalise_root("/P/./q/../r/") == "/P/./q/../r"
    assert normalise_root("C:") == "C:"
    assert normalise_root("/p\\q") == "/p/q"


def test_the_chief_keys_a_project_with_it():
    from pathly_orchestrator.supervisor.chief_session import normalise_project_root

    for value, key in SPELLINGS:
        assert normalise_project_root(value) == key


def test_the_comms_routes_key_a_project_with_it():
    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        norm_project_root,
    )

    for value, key in SPELLINGS:
        assert norm_project_root(value) == key


def test_the_search_tiers_address_the_project_board_with_it():
    from pathly_orchestrator.runner.board_scope import search_tiers_value

    tiers = {"feature": False, "project": True, "global": False}
    assert search_tiers_value(tiers, "demo", "C:\\") == 'board "project" + scope "C:/"'
    assert (
        search_tiers_value(tiers, "demo", "C:\\Users\\Yafit\\proj\\")
        == 'board "project" + scope "C:/Users/Yafit/proj"'
    )
    assert search_tiers_value(tiers, "demo", "") == (
        "(none — board reads are disabled for this run; do not search)"
    )


@pytest.mark.parametrize("value,key", SPELLINGS)
def test_the_board_context_reads_the_project_board_with_it(monkeypatch, value, key):
    from pathly_orchestrator.runner import comms_context

    seen: list[str] = []
    monkeypatch.setattr(
        comms_context,
        "standing_orders_only",
        lambda root, role, stats: seen.append(root) or "",
    )
    off = {"feature": False, "project": False, "global": False}
    comms_context.retrieve_board_context("demo", value, "task", board_scope=off)
    assert seen == [key]
