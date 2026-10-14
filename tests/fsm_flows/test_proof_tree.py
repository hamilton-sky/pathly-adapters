"""Git working-tree snapshots and the diffs between them (``proof/tree.py``).

Real ``git init`` repos under ``tmp_path``: the whole value of a snapshot is "git built this
tree without touching the repo's index or HEAD", which a mock cannot show.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from pathly_orchestrator.proof import tree

pytestmark = pytest.mark.no_pathly_autouse


def _git(repo: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )
    return done.stdout.strip()


def _init(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    return repo


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = _init(tmp_path / "repo")
    _write(root, ".gitignore", "ignored.txt\n")
    _write(root, "src/app.py", "def add(a, b):\n    return a + b\n")
    _write(root, "tests/test_app.py", "def test_add():\n    assert 1 + 1 == 2\n")
    _write(root, "pathly/features/demo/PLAN.md", "# Plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _index_bytes(repo: Path) -> bytes:
    return (repo / ".git" / "index").read_bytes()


# ── snapshot ──────────────────────────────────────────────────────────────────


def test_snapshot_sees_modified_new_and_deleted_files_and_skips_ignored(repo):
    base = tree.snapshot(repo)
    _write(repo, "src/app.py", "def add(a, b):\n    return b + a\n")
    _write(repo, "new.py", "x = 1\n")
    (repo / "tests" / "test_app.py").unlink()
    _write(repo, "ignored.txt", "secret\n")
    after = tree.snapshot(repo)

    assert base and after and base != after
    assert sorted(tree.changes(repo, base, after)) == [
        ("A", "new.py"),
        ("D", "tests/test_app.py"),
        ("M", "src/app.py"),
    ]
    assert tree.blob(repo, after, "ignored.txt") is None
    assert tree.blob(repo, after, "tests/test_app.py") is None
    assert tree.blob(repo, after, "new.py") is not None


def test_snapshot_leaves_the_index_bytes_and_head_unchanged(repo):
    """A half-staged repo: the index differs from both HEAD and the working tree."""
    _write(repo, "src/app.py", "def add(a, b):\n    return a + b + 0\n")
    _git(repo, "add", "src/app.py")
    _write(repo, "src/app.py", "def add(a, b):\n    return 0 + a + b\n")
    _write(repo, "untracked.py", "y = 2\n")
    head_before = tree.head(repo)
    index_before = _index_bytes(repo)

    snap = tree.snapshot(repo)

    index_after = _index_bytes(repo)
    assert snap is not None
    assert index_after == index_before
    assert tree.head(repo) == head_before == _git(repo, "rev-parse", "HEAD")
    assert tree.blob(repo, snap, "untracked.py") is not None


def test_snapshot_removes_its_temp_index(repo, tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    _write(repo, "new.py", "x = 1\n")

    assert tree.snapshot(repo) is not None
    assert list(scratch.iterdir()) == []


def test_snapshot_works_in_a_repo_with_no_index_yet(tmp_path):
    root = _init(tmp_path / "fresh")
    _write(root, "a.py", "a = 1\n")
    assert not (root / ".git" / "index").exists()

    snap = tree.snapshot(root)

    assert snap is not None
    assert tree.blob(root, snap, "a.py") == _git(root, "hash-object", "a.py")
    assert not (root / ".git" / "index").exists()
    assert tree.head(root) is None


def test_snapshot_works_over_an_index_with_unmerged_entries(repo):
    _git(repo, "checkout", "-q", "-b", "side")
    _write(repo, "src/app.py", "def add(a, b):\n    return 'side'\n")
    _git(repo, "commit", "-q", "-am", "side")
    _git(repo, "checkout", "-q", "-")
    _write(repo, "src/app.py", "def add(a, b):\n    return 'main'\n")
    _git(repo, "commit", "-q", "-am", "main")
    _git(repo, "merge", "side", check=False)
    assert "UU src/app.py" in _git(repo, "status", "--porcelain")
    index_before = _index_bytes(repo)

    snap = tree.snapshot(repo)

    assert snap is not None
    assert _index_bytes(repo) == index_before


# ── head, blob, changes, diff_text ────────────────────────────────────────────


def test_blob_finds_a_paths_blob(repo):
    snap = tree.snapshot(repo)
    assert tree.blob(repo, snap, "src/app.py") == _git(
        repo, "hash-object", "src/app.py"
    )
    assert tree.blob(repo, snap, "src/missing.py") is None


def test_changes_can_be_limited_to_paths(repo):
    base = tree.snapshot(repo)
    _write(repo, "src/app.py", "changed = True\n")
    _write(repo, "pathly/features/demo/PLAN.md", "# Plan, edited\n")
    after = tree.snapshot(repo)

    assert tree.changes(repo, base, after, paths=["pathly/"]) == [
        ("M", "pathly/features/demo/PLAN.md")
    ]


def test_diff_text_with_an_exclusion_shows_src_and_nothing_under_pathly(repo):
    base = tree.snapshot(repo)
    _write(repo, "src/app.py", "def add(a, b):\n    return b + a\n")
    _write(repo, "pathly/features/demo/PLAN.md", "# Plan, edited\n")
    after = tree.snapshot(repo)

    outside = tree.diff_text(repo, base, after, exclude=["pathly/"])
    inside = tree.diff_text(repo, base, after, paths=["pathly/"])

    assert "+++ b/src/app.py" in outside
    assert "+    return b + a" in outside
    assert "pathly/" not in outside
    assert "+++ b/pathly/features/demo/PLAN.md" in inside
    assert "src/app.py" not in inside


def test_diff_text_has_no_context_lines_by_default(repo):
    base = tree.snapshot(repo)
    _write(repo, "src/app.py", "def add(a, b):\n    return b + a\n")
    after = tree.snapshot(repo)

    lines = tree.diff_text(repo, base, after).splitlines()
    assert "-    return a + b" in lines
    assert "+    return b + a" in lines
    assert not [line for line in lines if line.startswith(" ")]


# ── fail open ─────────────────────────────────────────────────────────────────


def _assert_all_fail_open(root: Path, a: str | None, b: str | None) -> None:
    assert tree.snapshot(root) is None
    assert tree.head(root) is None
    assert tree.changes(root, a, b) == []
    assert tree.diff_text(root, a, b) == ""
    assert tree.blob(root, a, "src/app.py") is None


def test_every_function_fails_open_outside_a_git_repo(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    _assert_all_fail_open(plain, "HEAD", "HEAD")


def test_every_function_fails_open_in_a_subfolder_of_a_repo(repo):
    """git works there, but would name paths from the repo top, not from the folder."""
    base = tree.snapshot(repo)
    _write(repo, "src/app.py", "changed = True\n")
    after = tree.snapshot(repo)
    assert tree.changes(repo, base, after)

    _assert_all_fail_open(repo / "src", base, after)


def test_every_function_fails_open_when_git_is_missing(repo, tmp_path, monkeypatch):
    base = tree.snapshot(repo)
    empty_bin = tmp_path / "no-git-here"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    _assert_all_fail_open(repo, base, base)


def test_a_missing_tree_id_gives_an_empty_result(repo):
    snap = tree.snapshot(repo)
    assert tree.changes(repo, None, snap) == []
    assert tree.diff_text(repo, snap, None) == ""
    assert tree.blob(repo, None, "src/app.py") is None
