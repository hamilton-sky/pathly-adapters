"""CliProvider path resolution — relative targets anchor to project_root, not CWD.

Regression test for the silent /code/query failure: the cli backend resolved the
target file via os.path.abspath() (process-CWD-relative). The FSM server rarely runs
from the repo root, so every RELATIVE-path query (agents pass the git changed-set)
mislocated the file and returned an empty block. build_block now threads project_root
through to _project, which anchors relative paths to it.
"""

from __future__ import annotations

import json
import os

import pytest

# A platform-appropriate ABSOLUTE root: os.path.isabs() only treats a drive-letter
# path as absolute on Windows, and a leading-slash path as absolute on POSIX — so the
# "absolute path" assertions below must use the right shape for the host OS (CI is Linux).
_ABS = "D:/work/myrepo" if os.name == "nt" else "/work/myrepo"

_FAKE_PROJECTS = json.dumps({
    "projects": [
        {"name": "myrepo", "root_path": _ABS},
        {"name": "myrepo-src", "root_path": _ABS + "/src"},
    ]
})


@pytest.fixture()
def provider(monkeypatch):
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    p = CliProvider()
    # Mock the binary call so the test needs no installed codebase-memory-mcp / index.
    monkeypatch.setattr(p, "_run", lambda exe, args: _FAKE_PROJECTS)
    return p


def test_relative_path_anchors_to_project_root(provider):
    # Relative file + project_root → longest-prefix match picks the nested -src project.
    assert provider._project("exe", "src/pkg/mod.py", _ABS) == "myrepo-src"
    # A path outside the nested src still matches the repo-root project.
    assert provider._project("exe", "README.md", _ABS) == "myrepo"


def test_absolute_path_used_as_is(provider):
    assert provider._project("exe", _ABS + "/src/pkg/mod.py") == "myrepo-src"


@pytest.mark.skipif(os.name != "nt", reason="backslash paths are Windows-only")
def test_windows_backslash_path_normalized(provider):
    assert provider._project("exe", "D:\\work\\myrepo\\a.py") == "myrepo"


def test_relative_without_root_from_unrelated_cwd_misses(provider, tmp_path, monkeypatch):
    # The bug it fixes: a relative path with NO project_root resolves against the
    # process CWD; from an unrelated dir that matches no indexed project → "".
    monkeypatch.chdir(tmp_path)
    assert provider._project("exe", "src/pkg/mod.py") == ""


def test_build_block_passes_project_root(monkeypatch):
    """build_block forwards project_root to _project (the whole point of the fix)."""
    from pathly_orchestrator.runner.code_context_cli import CliProvider

    p = CliProvider()
    seen = {}

    monkeypatch.setattr("shutil.which", lambda _t: "exe")
    monkeypatch.setattr(p, "_project", lambda exe, f, pr="": seen.setdefault("project_root", pr) or "")
    p.build_block("scope", ["src/x.py"], "builder", 1500, project_root=_ABS)
    assert seen["project_root"] == _ABS
