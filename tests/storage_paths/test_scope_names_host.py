"""chief-agent 08 (round 7): ``scope_names`` says what "the same directory" means on this host.

The chief gate compares a request's ``project_root`` and file paths with the chief's own project
by one spelling (``root_spelling``) and one containment test (``lies_under``). Both take the host
from ``host_is_windows``, the one switch a test patches. Where two strings get the same spelling,
the routes must open the same directory with either, so the tests that matter most create the
folders and ask the file system.
"""

from __future__ import annotations

import os

import pytest


def _host(monkeypatch, windows: bool) -> None:
    monkeypatch.setattr(
        "pathly_orchestrator.scope_names.host_is_windows",
        lambda: windows,
        raising=False,
    )


def test_the_host_switch_follows_the_platform():
    from pathly_orchestrator import scope_names

    assert scope_names.host_is_windows() is (os.name == "nt")


@pytest.mark.parametrize(
    "value,spelling",
    [
        ("/p", "/p"),
        ("/p/", "/p"),
        ("/p//", "/p"),
        ("/", "/"),
        ("//", "/"),
        ("/a b/c", "/a b/c"),
        (
            "/p/./q",
            "/p/./q",
        ),  # not collapsed: a different spelling is not the same folder
        ("/p//q", "/p//q"),
        (" /p", " /p"),
        ("proj/x", "proj/x"),
        ("/p\\", None),
        ("\\p", None),
        ("/p/sub\\..\\..\\q", None),
        ("C:\\p", None),
        ("", None),
        ("/p\0", None),
        (7, None),
        (None, None),
        (["/p"], None),
    ],
)
def test_a_root_is_spelled_by_what_a_posix_host_opens(monkeypatch, value, spelling):
    from pathly_orchestrator.scope_names import root_spelling

    _host(monkeypatch, False)

    assert root_spelling(value) == spelling


@pytest.mark.parametrize(
    "value,spelling",
    [
        ("C:\\p", "C:/p"),
        ("C:/p/", "C:/p"),
        ("C:\\p\\", "C:/p"),
        ("C:\\p\\q", "C:/p/q"),
        (
            "c:\\p",
            "c:/p",
        ),  # a drive letter's case is kept: a different spelling is refused
        ("\\\\host\\share\\p\\", "//host/share/p"),
        ("/p\\", "/p"),
        ("\\", "/"),
        ("/p\0", None),
        ("", None),
        (7, None),
    ],
)
def test_a_root_is_spelled_by_what_a_windows_host_opens(monkeypatch, value, spelling):
    from pathly_orchestrator.scope_names import root_spelling

    _host(monkeypatch, True)

    assert root_spelling(value) == spelling


def test_two_spellings_with_one_key_name_one_folder(tmp_path, monkeypatch):
    """The property the gate relies on: if the gate calls two strings the same root, the file
    system opens the same folder with either."""
    from pathly_orchestrator.scope_names import root_spelling

    _host(monkeypatch, False)
    folder = tmp_path / "a b" / "proj"
    folder.mkdir(parents=True)
    own = str(folder)
    spelled = [
        own,
        own + "/",
        own + "//",
        own + "///",
        own + "/.",
        own.replace("/proj", "/./proj"),
        own.replace("a b", "a b/../a b"),
        own + "\\",
        own.replace("/", "\\"),
        f"{folder.parent}\\proj",
    ]

    named = [s for s in spelled if root_spelling(s) == root_spelling(own)]

    assert own in named and own + "/" in named and own + "//" in named
    assert not any("\\" in s for s in named)
    for s in named:
        assert os.path.samefile(s, folder), s
    for s in spelled:
        if s not in named:
            assert not os.path.isdir(s) or os.path.samefile(s, folder) or "\\" in s


@pytest.mark.parametrize(
    "path,anchored,inside",
    [
        ("/p/src/x.py", False, True),
        ("/p", False, True),
        ("/p/", False, True),
        ("/p/../p/x.py", False, True),
        ("/p/../q/x.py", False, False),
        ("/pp/x.py", False, False),
        ("/p/src/../../q", False, False),
        ("src/x.py", False, False),
        ("src/x.py", True, True),
        ("../q/x.py", True, False),
        ("a/../../q/x.py", True, False),
        ("/p/src\\x.py", False, False),
        ("src\\x.py", True, False),
        ("\\p\\x.py", False, False),
        (" /p/x.py", False, False),
        (
            " /p/x.py",
            True,
            True,
        ),  # relative to the root, whitespace and all: the route joins it
        ("C:/p/x.py", False, False),
        ("/p/x\0y", False, False),
        ("", False, False),
        (7, False, False),
    ],
)
def test_a_path_lies_under_a_root_on_a_posix_host(monkeypatch, path, anchored, inside):
    from pathly_orchestrator.scope_names import lies_under

    _host(monkeypatch, False)

    assert lies_under(path, "/p", anchored) is inside


@pytest.mark.parametrize(
    "path,anchored,inside",
    [
        ("C:\\p\\src\\x.py", False, True),
        ("C:/p/src\\x.py", False, True),
        ("C:\\p", False, True),
        ("C:\\p\\..\\q\\x.py", False, False),
        ("C:\\pp\\x.py", False, False),
        ("c:\\p\\x.py", False, False),
        ("src\\x.py", True, True),
        ("..\\q\\x.py", True, False),
        ("D:\\p\\x.py", False, False),
    ],
)
def test_a_path_lies_under_a_root_on_a_windows_host(
    monkeypatch, path, anchored, inside
):
    from pathly_orchestrator.scope_names import lies_under

    _host(monkeypatch, True)

    assert lies_under(path, "C:/p", anchored) is inside


def test_no_root_means_no_path_is_inside(monkeypatch):
    from pathly_orchestrator.scope_names import lies_under

    _host(monkeypatch, False)

    assert lies_under("/p/x", None, False) is False
    assert lies_under("x", None, True) is False
    assert lies_under("/p/x", "", False) is False
