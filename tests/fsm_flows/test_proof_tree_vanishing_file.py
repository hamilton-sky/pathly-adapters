"""``proof/tree.snapshot`` survives a file that vanishes while ``git add -A`` runs.

The DB->disk mirrors write ``<name>.tmp`` and ``os.replace`` it; when git lists the temp file and
it is renamed away before git stats it, ``git add -A`` exits 128 with ``unable to stat ...: No
such file or directory``. The snapshot retries the add then (3 attempts in all) and fails at once
on any other error. The race is replayed deterministically by patching ``subprocess.run`` for the
``add -A`` call only; every other git call is real.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pathly_orchestrator.proof import tree

pytestmark = pytest.mark.no_pathly_autouse

_REAL_RUN = subprocess.run

_VANISHED = (
    b'error: open("pathly/features/demo/EVENTS.tmp"): No such file or directory\n'
    b"fatal: unable to stat 'pathly/features/demo/EVENTS.tmp': No such file or directory\n"
)
_OTHER = b"fatal: Unable to create '.git/index.lock': File exists.\n"


def _git(repo: Path, *args: str) -> str:
    done = _REAL_RUN(["git", *args], cwd=repo, check=True, capture_output=True)
    return done.stdout.decode("utf-8").strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    (root / "src" / "new.py").write_text("y = 2\n", encoding="utf-8")
    return root


def _is_add(argv: list[str]) -> bool:
    return "add" in argv and "-A" in argv


def _patch_add(monkeypatch, failures: list[bytes]) -> list[list[str]]:
    """Each ``git add -A`` takes the next stderr in ``failures`` (exit 128); then runs for real."""
    adds: list[list[str]] = []
    pending = list(failures)

    def fake_run(argv, *args, **kwargs):
        if not _is_add(argv):
            return _REAL_RUN(argv, *args, **kwargs)
        adds.append(list(argv))
        if pending:
            return subprocess.CompletedProcess(argv, 128, b"", pending.pop(0))
        return _REAL_RUN(argv, *args, **kwargs)

    monkeypatch.setattr(tree.subprocess, "run", fake_run)
    return adds


def _expected_tree(repo: Path) -> str:
    """``git write-tree`` of the same files, staged into the repo's own index."""
    _git(repo, "add", "-A")
    return _git(repo, "write-tree")


def test_a_vanished_path_then_a_clean_add_gives_the_tree(repo, monkeypatch):
    adds = _patch_add(monkeypatch, [_VANISHED])

    snap = tree.snapshot(repo)

    monkeypatch.undo()
    assert len(adds) == 2
    assert snap is not None
    assert snap == _expected_tree(repo)


def test_three_vanished_path_failures_give_none_and_no_fourth_add(repo, monkeypatch):
    adds = _patch_add(monkeypatch, [_VANISHED, _VANISHED, _VANISHED, _VANISHED])

    assert tree.snapshot(repo) is None
    assert len(adds) == 3


def test_any_other_add_failure_gives_none_after_one_attempt(repo, monkeypatch):
    adds = _patch_add(monkeypatch, [_OTHER, _OTHER, _OTHER])

    assert tree.snapshot(repo) is None
    assert len(adds) == 1


def test_a_missing_file_without_unable_to_stat_is_not_retried(repo, monkeypatch):
    adds = _patch_add(
        monkeypatch, [b"fatal: pathspec 'x' did not match: No such file or directory\n"]
    )

    assert tree.snapshot(repo) is None
    assert len(adds) == 1


def test_a_real_repo_snapshot_equals_git_write_tree(repo):
    snap = tree.snapshot(repo)

    assert snap is not None
    assert snap == _expected_tree(repo)
