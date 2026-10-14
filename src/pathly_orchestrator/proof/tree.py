"""Git working-tree snapshots and the diffs between them. Stdlib only, no Pathly imports.

:func:`snapshot` writes a tree object for the working tree as it is right now (tracked and
untracked files, never ignored ones) without touching the repo's index or ``HEAD``: it stages
into a private copy of the index (``GIT_INDEX_FILE``) and runs ``git write-tree``. Two such
tree ids diff like two commits.

Every function fails open: it returns ``None`` (or an empty result) when ``root`` is not the top
folder of a git work tree, when a tree id is missing, or when git fails, times out or is not
installed. A project inside a larger repo counts as "not a repo", because git would name paths
from the outer folder and every ``pathly/...`` prefix a caller uses would miss.

Snapshot objects are unreachable, so ``git gc`` prunes them after its grace period.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 60

# Variables that point git at another repo or index, or change how it reads a pathspec. One
# inherited from the caller (a git hook, say) must not override the repo that ``cwd=root``
# names, or turn ``:(exclude)pathly/`` into a literal file name.
_REPO_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_LITERAL_PATHSPECS",
    "GIT_GLOB_PATHSPECS",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
)

# Explicit diff settings, so a user's git config (external diff tools, textconv filters,
# no-prefix) cannot change the text callers parse.
_DIFF_FLAGS = ("--no-color", "--no-ext-diff", "--no-textconv", "--no-renames")
_PREFIXES = ("--src-prefix=a/", "--dst-prefix=b/")

# One escape in a name git C-quotes: an octal byte or a single character.
_ESCAPE = re.compile(rb"\\([0-3][0-7]{2}|.)", re.DOTALL)
_C_ESCAPES = {b"a": 7, b"b": 8, b"t": 9, b"n": 10, b"v": 11, b"f": 12, b"r": 13}


def _git(root: str | Path, *args: str, index: str | None = None) -> str | None:
    """stdout of ``git <args>`` run in ``root``, or None when git fails or cannot run."""
    env = {key: value for key, value in os.environ.items() if key not in _REPO_ENV}
    if index is not None:
        env["GIT_INDEX_FILE"] = index
    try:
        done = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=str(root),
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", "surrogateescape")


def _is_top(root: str | Path | None) -> bool:
    """True when ``git rev-parse --show-toplevel`` names ``root`` itself."""
    if root is None:
        return False
    top = _git(root, "rev-parse", "--show-toplevel")
    return top is not None and _same_folder(top.rstrip("\r\n"), str(root))


def _same_folder(a: str, b: str) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(
        os.path.realpath(b)
    )


def _trimmed(out: str | None) -> str | None:
    """git's one-line answer without its newline, or None when there is none."""
    if out is None:
        return None
    return out.strip() or None


def snapshot(root: str | Path) -> str | None:
    """A tree id for the working tree (tracked + untracked, not ignored), or None."""
    if not _is_top(root):
        return None
    index_path = _git(root, "rev-parse", "--git-path", "index")
    if index_path is None:
        return None
    real_index = os.path.join(str(root), index_path.rstrip("\r\n"))
    with tempfile.TemporaryDirectory(
        prefix="pathly-snapshot-", ignore_cleanup_errors=True
    ) as scratch:
        # git refuses an empty index file, so with no index the copy is simply absent.
        # copy2 keeps the index's mtime: git re-reads an entry as new as the index file and
        # trusts the stat data of an older one, so a fresh mtime on the copy would hide a
        # same-size edit made in the second the index was last written.
        private = os.path.join(scratch, "index")
        if os.path.isfile(real_index):
            try:
                shutil.copy2(real_index, private)
            except OSError:
                return None
        if _git(root, "add", "-A", index=private) is None:
            return None
        tree = _git(root, "write-tree", index=private)
    return _trimmed(tree)


def head(root: str | Path) -> str | None:
    """The commit id ``HEAD`` points at, or None (no commits yet, or not a repo top)."""
    if not _is_top(root):
        return None
    return _trimmed(_git(root, "rev-parse", "--verify", "--quiet", "HEAD"))


def changes(
    root: str | Path, a: str, b: str, paths: list[str] | None = None
) -> list[tuple[str, str]]:
    """``(status, path)`` for each path that differs between trees a and b (no renames)."""
    return changes_or_none(root, a, b, paths) or []


def changes_or_none(
    root: str | Path, a: str, b: str, paths: list[str] | None = None
) -> list[tuple[str, str]] | None:
    """As :func:`changes`, but None when git cannot diff, so a caller can tell that apart."""
    if not (a and b) or not _is_top(root):
        return None
    out = _git(
        root, "diff", "--name-status", "--no-renames", "-z", a, b, "--", *(paths or [])
    )
    if out is None:
        return None
    fields = out.split("\0")
    return [
        (fields[i], fields[i + 1])
        for i in range(0, len(fields) - 1, 2)
        if fields[i] and fields[i + 1]
    ]


def diff_text(
    root: str | Path,
    a: str,
    b: str,
    paths: list[str] | None = None,
    exclude: list[str] | None = None,
    unified: int = 0,
) -> str:
    """The patch from tree a to tree b, limited to ``paths`` and without ``exclude``.

    Each ``exclude`` entry becomes a ``:(exclude)<path>`` pathspec; with exclusions only, git
    diffs every other path.
    """
    return diff_text_or_none(root, a, b, paths, exclude, unified) or ""


def diff_text_or_none(
    root: str | Path,
    a: str,
    b: str,
    paths: list[str] | None = None,
    exclude: list[str] | None = None,
    unified: int = 0,
) -> str | None:
    """As :func:`diff_text`, but None when git cannot diff, so a caller can tell that apart."""
    if not (a and b) or not _is_top(root):
        return None
    pathspecs = [*(paths or []), *(":(exclude)" + path for path in exclude or [])]
    return _git(
        root,
        "diff",
        *_DIFF_FLAGS,
        *_PREFIXES,
        "--unified=%d" % unified,
        a,
        b,
        "--",
        *pathspecs,
    )


def blob(root: str | Path, tree: str, path: str) -> str | None:
    """The blob id of ``path`` in ``tree``, or None when the path is absent."""
    if not tree or not _is_top(root):
        return None
    return _trimmed(
        _git(root, "rev-parse", "--verify", "--quiet", "%s:%s" % (tree, path))
    )


def read(root: str | Path, tree: str, path: str) -> str | None:
    """The text of ``path`` in ``tree``, or None when the path is absent."""
    if not tree or not _is_top(root):
        return None
    return _git(root, "cat-file", "blob", "%s:%s" % (tree, path))


def unquote_path(name: str) -> str:
    """A path as git prints it in a patch header, without git's C-style quotes.

    git quotes a name that holds ``"``, ``\\`` or a control character even with
    ``core.quotepath=off`` (``"a/we\\"ird.py"``, octal for a byte). Other names come back as
    they are.
    """
    if len(name) < 2 or name[0] != '"' or name[-1] != '"':
        return name

    def one(match: re.Match[bytes]) -> bytes:
        code = match.group(1)
        if len(code) == 3:
            return bytes([int(code, 8)])
        return bytes([_C_ESCAPES.get(code, code[0])])

    raw = name[1:-1].encode("utf-8", "surrogateescape")
    return _ESCAPE.sub(one, raw).decode("utf-8", "surrogateescape")
