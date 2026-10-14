"""The floor scan over two working-tree snapshots (``proof/floor.py``).

Each test snapshots a real ``git init`` repo, makes one edit a builder might make to get green
without doing the work, snapshots again and scans the diff between the two trees.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import pytest

from pathly_orchestrator.proof import floor, tree

pytestmark = pytest.mark.no_pathly_autouse

PYPROJECT = """[project]
name = "demo"
version = "1.0"

[tool.pytest.ini_options]
addopts = "-q"

[tool.coverage.report]
fail_under = 80
"""

TEST_X = """import pytest


def test_one():
    assert 1 + 1 == 2


def test_two():
    assert "a".upper() == "A"
"""

FILES = {
    "src/app.py": "def add(a, b):\n    return a + b\n",
    "tests/test_x.py": TEST_X,
    "tests/conftest.py": "import pytest\n",
    "web/app.test.js": "it('adds', () => { expect(add(1, 2)).toBe(3) })\n",
    "pyproject.toml": PYPROJECT,
    "pytest.ini": "[pytest]\naddopts = -q\n",
    "Makefile": "test:\n\tpytest\n",
    "package.json": '{"name": "demo", "version": "1.0.0", "scripts": {"test": "jest"}}\n',
    "pathly/features/demo/USER_STORIES.md": "# Stories\n\n- [ ] it adds\n",
    "pathly/features/demo/notes.md": "# Notes\n",
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    for rel, text in FILES.items():
        _write(root, rel, text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _replace(rel: str, old: str, new: str) -> Callable[[Path], None]:
    def edit(repo: Path) -> None:
        text = (repo / rel).read_text(encoding="utf-8")
        assert old in text
        _write(repo, rel, text.replace(old, new))

    return edit


def _append(rel: str, extra: str) -> Callable[[Path], None]:
    def edit(repo: Path) -> None:
        _write(repo, rel, (repo / rel).read_text(encoding="utf-8") + extra)

    return edit


def _scan(repo: Path, edit: Callable[[Path], None], **kwargs) -> floor.FloorReport:
    base = tree.snapshot(repo)
    edit(repo)
    after = tree.snapshot(repo)
    assert base and after
    return floor.scan(repo, base, after, **kwargs)


def _categories(report: floor.FloorReport) -> list[str]:
    return sorted(finding.split(":", 1)[0] for finding in report.findings)


# ── One finding per category ──────────────────────────────────────────────────


def test_a_clean_change_gives_no_finding(repo):
    report = _scan(repo, _replace("src/app.py", "a + b", "b + a"))
    assert report.findings == []
    assert report.warnings == []


def test_skip_marker(repo):
    edit = _replace(
        "tests/test_x.py", "def test_one", "@pytest.mark.skip\ndef test_one"
    )
    report = _scan(repo, edit)
    assert report.findings == ["skip: tests/test_x.py: @pytest.mark.skip"]


def test_focused_test_counts_as_skip_only_in_a_test_file(repo):
    report = _scan(repo, _replace("web/app.test.js", "it(", "it.only("))
    assert _categories(report) == ["skip"]
    assert report.findings[0].startswith("skip: web/app.test.js: it.only(")

    assert _scan(repo, _append("src/app.py", "result = fit(data)\n")).findings == []


def test_suppress_comment(repo):
    report = _scan(repo, _replace("src/app.py", "a + b", "a + b  # noqa"))
    assert report.findings == ["suppress: src/app.py: return a + b  # noqa"]


def test_one_line_empty_except(repo):
    edit = _append("src/app.py", "try:\n    import json\nexcept ImportError: pass\n")
    report = _scan(repo, edit)
    assert report.findings == ["empty-catch: src/app.py: except ImportError: pass"]


def test_deleted_test_file(repo):
    report = _scan(repo, lambda r: (r / "tests" / "test_x.py").unlink())
    assert _categories(report) == ["test-delete"]
    assert report.findings[0].startswith("test-delete: tests/test_x.py: ")


def test_fail_under_change(repo):
    report = _scan(
        repo, _replace("pyproject.toml", "fail_under = 80", "fail_under = 60")
    )
    assert "threshold: pyproject.toml: fail_under = 60" in report.findings
    # [tool.coverage.report] is also a guarded pyproject section.
    assert _categories(report) == ["config", "threshold"]


def test_assert_true_in_a_test_file(repo):
    edit = _replace("tests/test_x.py", 'assert "a".upper() == "A"', "assert True")
    report = _scan(repo, edit)
    assert report.findings == ["trivial-assert: tests/test_x.py: assert True"]


def test_assert_true_outside_a_test_file_is_not_trivial_assert(repo):
    assert _scan(repo, _append("src/app.py", "assert True\n")).findings == []


def test_pytest_ini_edit(repo):
    report = _scan(repo, _replace("pytest.ini", "-q", "-q -p no:randomly"))
    assert _categories(report) == ["config"]
    assert report.findings[0].startswith("config: pytest.ini: ")


def test_pyproject_pytest_section_edit(repo):
    edit = _replace(
        "pyproject.toml", 'addopts = "-q"', "addopts = \"-q -k 'not slow'\""
    )
    report = _scan(repo, edit)
    assert _categories(report) == ["config"]
    assert report.findings[0].startswith("config: pyproject.toml: ")


def test_pyproject_edit_outside_a_guarded_section_is_not_config(repo):
    report = _scan(
        repo, _replace("pyproject.toml", 'version = "1.0"', 'version = "1.1"')
    )
    assert report.findings == []


def test_protected_plan_file_edit(repo):
    edit = _append("pathly/features/demo/USER_STORIES.md", "- [ ] it also subtracts\n")
    report = _scan(repo, edit, protected=["pathly/features/demo/"])
    assert _categories(report) == ["plan-edit"]
    assert report.findings[0].startswith(
        "plan-edit: pathly/features/demo/USER_STORIES.md: "
    )


# ── Content rules for config files ────────────────────────────────────────────


def test_makefile_counts_only_when_a_command_starts_with_make(repo):
    edit = _replace("Makefile", "\tpytest", "\tpytest -x")
    assert _scan(repo, edit, config_commands=["python -m pytest -q"]).findings == []

    edit = _replace("Makefile", "\tpytest -x", "\tpytest -q")
    report = _scan(repo, edit, config_commands=["python -m build", "make test"])
    assert _categories(report) == ["config"]

    edit = _replace("Makefile", "\tpytest -q", "\tpytest")
    report = _scan(repo, edit, config_commands=['["make", "test"]'])
    assert _categories(report) == ["config"]


def test_conftest_counts_when_it_adds_a_collection_word(repo):
    edit = _append("tests/conftest.py", 'collect_ignore = ["test_x.py"]\n')
    assert _categories(_scan(repo, edit)) == ["config"]

    edit = _append("tests/conftest.py", "VALUE = 3\n")
    assert _scan(repo, edit).findings == []


def test_package_json_counts_when_a_guarded_key_changes(repo):
    edit = _replace("package.json", '"jest"', '"jest --passWithNoTests"')
    assert _categories(_scan(repo, edit)) == ["config"]

    edit = _replace("package.json", '"1.0.0"', '"1.0.1"')
    assert _scan(repo, edit).findings == []


# ── Allow lists, pathly/ prose, may_change, warnings ──────────────────────────


def test_an_allowed_category_gives_no_finding(repo):
    edit = _replace(
        "tests/test_x.py", "def test_one", "@pytest.mark.skip\ndef test_one"
    )
    report = _scan(repo, edit, allow=floor.parse_allow(["skip"]))
    assert report.findings == []


def test_a_skip_written_under_pathly_is_not_a_skip(repo):
    edit = _append(
        "pathly/features/demo/notes.md", "Never add @pytest.mark.skip  # noqa\n"
    )
    assert _scan(repo, edit).findings == []


def test_may_change_clears_a_plan_edit(repo):
    edit = _append("pathly/features/demo/notes.md", "- the builder may keep notes\n")
    report = _scan(
        repo,
        edit,
        protected=["pathly/features/demo/"],
        may_change=lambda path: path == "pathly/features/demo/notes.md",
    )
    assert report.findings == []


def test_removed_assertions_give_a_warning_not_a_finding(repo):
    edit = _replace("tests/test_x.py", 'assert "a".upper() == "A"', '"a".upper()')
    report = _scan(repo, edit)
    assert report.findings == []
    assert len(report.warnings) == 1
    assert "1 assertion line(s) removed, 0 added" in report.warnings[0]


# ── parse_allow ───────────────────────────────────────────────────────────────


def test_parse_allow_rejects_an_unknown_category():
    with pytest.raises(ValueError) as caught:
        floor.parse_allow(["nope"])
    assert "nope" in str(caught.value)
    assert "trivial-assert" in str(caught.value)


def test_parse_allow_reads_lists_and_strings():
    assert floor.parse_allow(["skip", "Config"]) == frozenset({"skip", "config"})
    assert floor.parse_allow("skip, task-edit") == frozenset({"skip", "task-edit"})
    assert floor.parse_allow(None) == frozenset()
    assert set(floor.CATEGORIES) >= {"plan-edit", "task-edit", "test-delete"}


def test_scan_fails_open_outside_a_git_repo(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    report = floor.scan(plain, None, None, protected=["pathly/"])
    assert report.findings == []
    assert report.warnings == []
