"""The floor guard: scan the diff between two working-tree snapshots for a weakened bar.

Ported from feature-flow's ``feature_flow/floorguard.py`` (MIT): the regexes and the content
rules for config files are copied; its CLI and its ticket rules are not. A finding reads
``"<category>: <path>: <line>"``:

- ``skip``, ``suppress``, ``empty-catch``, ``threshold``, ``trivial-assert``: an added line
  outside ``pathly/`` matches a pattern (focused tests count as ``skip``, and
  ``trivial-assert`` counts, only in test files). Plan docs under ``pathly/`` may mention
  ``@pytest.mark.skip`` in prose; they are judged by ``plan-edit`` instead.
- ``test-delete``: a test file outside ``pathly/`` was deleted.
- ``config``: lint, test or CI config outside ``pathly/`` changed, by file name, or by content
  for ``pyproject.toml``, ``setup.cfg``, ``package.json``, ``conftest.py`` and a ``Makefile``
  that a verify command runs.
- ``plan-edit``: a path under a ``protected`` prefix changed and ``may_change`` did not excuse it.
- ``task-edit``: listed so an allow list can name it; its callers check it (they hold the rows).

Fewer assertion lines added than removed in test files is a warning, not a finding.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from . import tree

CATEGORIES = (
    "skip",
    "suppress",
    "empty-catch",
    "test-delete",
    "threshold",
    "trivial-assert",
    "config",
    "plan-edit",
    "task-edit",
)

# Pattern categories, test-delete and config apply only outside this folder.
PLAN_ROOT = "pathly/"

# ── Copied from feature-flow floorguard.py ────────────────────────────────────
SKIP = re.compile(
    r"@pytest\.mark\.(skip|xfail)|pytest\.skip\(|(^|[^A-Za-z_])(it|test|describe)\.(skip|todo)\("
    r"|(^|[^A-Za-z_])(xit|xdescribe|xtest)\(|@Disabled|t\.Skip\(|#\[ignore\]|unittest\.skip"
    r"|self\.skipTest\(|pytest\.importorskip|@unittest\.expectedFailure|t\.Skipf\(|t\.SkipNow\(|#\[ignore = "
)
FOCUSED = re.compile(r"\.only\(|(?<!def )(?<![A-Za-z0-9_.])(fit|fdescribe)\(")
SUPPRESS = re.compile(
    r"# noqa|# type: ignore|# pylint: disable|# pragma: no cover|# fmt: off|# ruff: noqa"
    r"|eslint-disable|@ts-ignore|@ts-expect-error|// nolint|#\[allow\(|--no-verify"
)
EMPTY_CATCH = re.compile(
    r"except[^:]*:[ \t]*pass[ \t]*$|catch[ \t]*(\([^)]*\))?[ \t]*\{[ \t]*\}"
)
# An assertion that cannot fail, added to a test file: assert True, assertEqual(x, x),
# expect(true), expect(x).toBe(x).
TRIVIAL = (
    re.compile(r"(^|[^A-Za-z_.])assert\s+(True|1\s*==\s*1|not\s+False)\s*(#.*)?$"),
    re.compile(r"assertTrue\(\s*True\s*[,)]"),
    re.compile(r"assertEqual\(\s*([A-Za-z_][\w.]*|\d+)\s*,\s*\1\s*[,)]"),
    re.compile(r"(^|[^A-Za-z_.])assert\s+([A-Za-z_][\w.]*)\s*==\s*\2\s*(#.*)?$"),
    re.compile(r"expect\(\s*true\s*\)\.(toBe\(\s*true\s*\)|toBeTruthy\(\))"),
    re.compile(r"expect\(\s*([A-Za-z_][\w.]*)\s*\)\.toBe\(\s*\1\s*\)"),
)
THRESHOLD = re.compile(r"fail_under|fail-under|coverageThreshold|cov-fail-under")
DELETED_TEST = re.compile(
    r"(^|/)(test_[^/]*\.py|[^/]*_test\.[a-z]+|[^/]*\.(test|spec)\.[a-z]+|tests?/|__tests__/)"
)
CONFIG = re.compile(
    r"(^|/)(\.eslintrc[^/]*|eslint\.config\.[a-z]+|ruff\.toml|\.ruff\.toml|mypy\.ini|pytest\.ini"
    r"|tox\.ini|tsconfig[^/]*\.json|jest\.config\.[a-z]+|vitest\.config\.[a-z]+"
    r"|\.pre-commit-config\.yaml|\.github/workflows/[^/]*|\.azure/.*"
    r"|\.coveragerc|\.flake8|\.pylintrc|\.golangci\.ya?ml|karma\.conf\.[^/]*"
    r"|playwright\.config\.[^/]*|cypress\.config\.[^/]*|codecov\.yml|\.nycrc[^/]*)$"
)
PYPROJECT_SECTIONS = re.compile(
    r"tool\.(pytest|coverage|ruff|pylint)(\..*)?$|tool\.(mypy|pyright|black|isort)(\..*)?$"
)
SETUP_SECTIONS = re.compile(r"tool:pytest|flake8|mypy|coverage:")
SECTION_HEADER = re.compile(r"^\s*\[\[?\s*([A-Za-z0-9_.:\-\"' ]+?)\s*\]\]?\s*(#.*)?$")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
PACKAGE_KEYS = ("jest", "scripts", "eslintConfig", "nyc", "c8", "mocha", "ava")
CONFTEST_WORDS = ("collect_ignore", "pytest_collection_modifyitems", "deselect", "skip")
ASSERT_LINE = re.compile(r"assert|expect\(")
# ──────────────────────────────────────────────────────────────────────────────

# A verify command that runs make: a plain string or a JSON argv array.
MAKE_COMMAND = re.compile(r"""^[\s\["']*make\b""")

_CHANGED = {"A": "added", "D": "deleted"}


@dataclass(frozen=True)
class FloorReport:
    """``findings`` block the work; ``warnings`` are worth a look but block nothing."""

    findings: list[str]
    warnings: list[str]


@dataclass
class _FileDiff:
    """One file's part of a zero-context diff. A path is "" on the side where it is absent."""

    old: str = ""
    new: str = ""
    hunks: list[tuple[int, int, int, int]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)


def parse_allow(value: str | Iterable[str] | None) -> frozenset[str]:
    """The categories in a list, or in a string of names split by commas or spaces."""
    if value is None:
        return frozenset()
    names = value.replace(",", " ").split() if isinstance(value, str) else value
    allowed: set[str] = set()
    for name in names:
        category = name.strip().lower() if isinstance(name, str) else name
        if category == "":
            continue
        if category not in CATEGORIES:
            raise ValueError(
                "unknown floor category %r; valid categories: %s"
                % (name, ", ".join(CATEGORIES))
            )
        allowed.add(category)
    return frozenset(allowed)


def scan(
    root: str | Path,
    base: str,
    after: str,
    *,
    allow: Iterable[str] = frozenset(),
    protected: Iterable[str] = (),
    may_change: Callable[[str], bool] | None = None,
    config_commands: Iterable[str] = (),
) -> FloorReport:
    """Diff snapshot ``base`` to ``after`` and report each way it weakens the bar.

    Fails open: when git cannot diff the two trees, the report is empty.
    """
    allowed = frozenset(allow)
    findings: list[str] = []

    def add(category: str, path: str, text: str) -> None:
        if category not in allowed:
            findings.append("%s: %s: %s" % (category, path, text))

    diff = tree.diff_text(root, base, after, exclude=[PLAN_ROOT])
    files = _file_diffs(diff)
    for part in files:
        for line in part.added:
            for category in _line_categories(part.new, line):
                add(category, part.new, line.lstrip(" \t")[:100])

    rows = tree.changes(root, base, after)
    outside = [
        (status, path) for status, path in rows if not path.startswith(PLAN_ROOT)
    ]
    for status, path in outside:
        if status == "D" and DELETED_TEST.search(path):
            add("test-delete", path, "a test file was deleted")
    makes = any(MAKE_COMMAND.match(str(command)) for command in config_commands)
    for path in _config_paths(root, base, after, outside, files, makes):
        add("config", path, "lint, test or CI config was changed")

    prefixes = [p.rstrip("/") for p in protected if p.rstrip("/")]
    for status, path in rows:
        if not any(path == p or path.startswith(p + "/") for p in prefixes):
            continue
        if may_change is None or not may_change(path):
            word = _CHANGED.get(status, "changed")
            add("plan-edit", path, "a protected plan file was %s" % word)

    warnings: list[str] = []
    removed, added = count_assertions(diff)
    if removed > added:
        warnings.append(
            "%d assertion line(s) removed, %d added. check that no test got weaker."
            % (removed, added)
        )
    return FloorReport(findings=findings, warnings=warnings)


def count_assertions(diff: str) -> tuple[int, int]:
    """(removed, added) assertion lines, counting only files whose path looks like a test."""
    removed = added = 0
    for part in _file_diffs(diff):
        if DELETED_TEST.search(part.old):
            removed += sum(1 for line in part.removed if ASSERT_LINE.search(line))
        if DELETED_TEST.search(part.new):
            added += sum(1 for line in part.added if ASSERT_LINE.search(line))
    return removed, added


def _line_categories(path: str, line: str) -> list[str]:
    """The pattern categories one added line falls in, in feature-flow's order."""
    is_test = bool(DELETED_TEST.search(path))
    found: list[str] = []
    if SKIP.search(line) or (is_test and FOCUSED.search(line)):
        found.append("skip")
    if SUPPRESS.search(line):
        found.append("suppress")
    if EMPTY_CATCH.search(line):
        found.append("empty-catch")
    if THRESHOLD.search(line):
        found.append("threshold")
    if is_test and any(pattern.search(line) for pattern in TRIVIAL):
        found.append("trivial-assert")
    return found


def _config_paths(
    root: str | Path,
    base: str,
    after: str,
    outside: list[tuple[str, str]],
    files: list[_FileDiff],
    makes: bool,
) -> list[str]:
    """Changed paths that are lint, test or CI config: by name, else by what changed in them."""
    by_path = {part.new or part.old: part for part in files}
    found: list[str] = []
    for _status, path in outside:
        name = path.rsplit("/", 1)[-1]
        part = by_path.get(path, _FileDiff())
        if CONFIG.search(path):
            found.append(path)
        elif name in ("pyproject.toml", "setup.cfg"):
            sections = (
                PYPROJECT_SECTIONS if name == "pyproject.toml" else SETUP_SECTIONS
            )
            old = tree.read(root, base, path) or ""
            new = tree.read(root, after, path) or ""
            if _guarded_toml(old, new, part.hunks, sections):
                found.append(path)
        elif name == "package.json":
            old = tree.read(root, base, path) or ""
            new = tree.read(root, after, path) or ""
            if _package_json_changed(old, new):
                found.append(path)
        elif name == "conftest.py":
            if any(word in line for line in part.added for word in CONFTEST_WORDS):
                found.append(path)
        elif name == "Makefile" and makes:
            found.append(path)
    return found


def _section_of(lines: list[str], number: int, name_pattern: re.Pattern[str]) -> bool:
    """Whether the last [section] header at or above 1-based line ``number`` is guarded."""
    for line in reversed(lines[:number]):
        match = SECTION_HEADER.match(line)
        if match:
            return bool(name_pattern.match(match.group(1)))
    return False


def _guarded_toml(
    old_text: str,
    new_text: str,
    hunks: list[tuple[int, int, int, int]],
    pattern: re.Pattern[str],
) -> bool:
    """Does any changed line of a pyproject.toml or setup.cfg sit in a guarded section?"""
    old, new = old_text.split("\n"), new_text.split("\n")
    for old_start, old_len, new_start, new_len in hunks:
        for n in range(old_start, old_start + old_len):
            if _section_of(old, n, pattern):
                return True
        for n in range(new_start, new_start + new_len):
            if _section_of(new, n, pattern):
                return True
    return False


def _package_json_changed(old: str, new: str) -> bool:
    old_json, new_json = _json_or_none(old), _json_or_none(new)
    if old_json is None or new_json is None:
        return old != new
    if not isinstance(old_json, dict) or not isinstance(new_json, dict):
        return old_json != new_json
    return any(old_json.get(key) != new_json.get(key) for key in PACKAGE_KEYS)


def _json_or_none(text: str) -> object:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _records(text: str) -> list[str]:
    """Lines split on newline only; a last line without one still counts."""
    if not text:
        return []
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def _diff_path(text: str, prefix: str) -> str:
    """The path on a ``---``/``+++`` header line, or "" for /dev/null.

    git ends a name that holds a space with a tab, so the tab goes.
    """
    text = text.rstrip("\t")
    if text == "/dev/null":
        return ""
    return text[len(prefix) :] if text.startswith(prefix) else text


def _file_diffs(diff: str) -> list[_FileDiff]:
    """Split a ``git diff --unified=0`` patch into files.

    ``---``/``+++`` lines are read as names only in a file's header (before its first hunk),
    so an added line whose text starts with ``++ `` is still an added line.
    """
    files: list[_FileDiff] = []
    current: _FileDiff | None = None
    in_header = False
    for record in _records(diff):
        hunk = HUNK.match(record)
        if record.startswith("diff --git "):
            current = _FileDiff()
            files.append(current)
            in_header = True
        elif current is None:
            continue
        elif hunk:
            in_header = False
            old_start, old_len, new_start, new_len = hunk.groups()
            current.hunks.append(
                (int(old_start), int(old_len or 1), int(new_start), int(new_len or 1))
            )
        elif in_header:
            if record.startswith("--- "):
                current.old = _diff_path(record[4:], "a/")
            elif record.startswith("+++ "):
                current.new = _diff_path(record[4:], "b/")
        elif record.startswith("+"):
            current.added.append(record[1:])
        elif record.startswith("-"):
            current.removed.append(record[1:])
    return files
