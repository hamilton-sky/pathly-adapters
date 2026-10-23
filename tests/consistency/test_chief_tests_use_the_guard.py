"""Every test module that opens a chief imports the guard against a watcher that outlives its test.

``tests/chief_session_guard.py`` holds the one autouse fixture ``_no_watcher_outlives_its_test``.
An autouse fixture does something only in a module that imports it BY NAME, so a new test file
that opens a chief and forgets the import leaves its watcher thread waiting; the watcher then wakes
in a later test, after that test's patched home is gone, and opens the developer's real
``~/.pathly``. Nothing else notices, so this file does.

The scan reads the text of every ``tests/**/test_*.py``. A module that opens a chief (it calls
``open_chief(``, ``open_with(`` or ``open_session(``, or posts to ``"/chief/open"``) must import the
guard under its own name, either from ``chief_session_guard`` or from a support module that itself
imports it from there. Dropping the import from any one module, or from a support module its tests
rely on, is caught below.
"""

from __future__ import annotations

import ast
import functools
import re
from pathlib import Path

import pytest

from tests._paths import REPO_ROOT

TESTS = REPO_ROOT / "tests"
GUARD = "_no_watcher_outlives_its_test"
GUARD_MODULE = "chief_session_guard"
SELF = "consistency/test_chief_tests_use_the_guard.py"
OPENS = re.compile(
    r"""(?<![\w.])(?:open_chief|open_with|open_session)\(|["']/chief/open["']"""
)
CALLS = re.compile(r"(?<![\w.])(?:open_chief|open_with|open_session)\(")
# A module the scan would flag that opens no chief, with the reason. Each entry is checked below.
EXEMPT = {
    "http_api/test_chief_gate.py": (
        "names /chief/open as a route a non-chief caller is refused; it never opens a chief"
    ),
}


@functools.cache
def _read_all() -> tuple[tuple[str, str], ...]:
    return tuple(
        (path.relative_to(TESTS).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(TESTS.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def _modules() -> dict[str, str]:
    """The text of every module under ``tests/``; a fresh dict, so a test may change its copy."""
    return dict(_read_all())


def _is_test(rel: str) -> bool:
    return Path(rel).name.startswith("test_")


def _guard_imports(text: str) -> list[ast.ImportFrom]:
    """Every ``from X import ... GUARD ...`` of the module (an alias counts, as a mistake)."""
    return [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and any(alias.name == GUARD for alias in node.names)
    ]


def _imports_guard_from(text: str, sources: set[str]) -> bool:
    """True when the module imports the guard, under its own name, from one of ``sources``."""
    return any(
        node.module in sources and all(a.asname is None for a in node.names)
        for node in _guard_imports(text)
    )


def _reexporters(modules: dict[str, str]) -> set[str]:
    """The support modules (not test files) that import the guard from its home."""
    return {
        Path(rel).stem
        for rel, text in modules.items()
        if not _is_test(rel) and _imports_guard_from(text, {GUARD_MODULE})
    }


def _opening(modules: dict[str, str]) -> list[str]:
    return [
        rel
        for rel, text in modules.items()
        if _is_test(rel) and rel != SELF and rel not in EXEMPT and OPENS.search(text)
    ]


def unguarded(modules: dict[str, str]) -> list[str]:
    """The test modules that open a chief and do not import the guard."""
    sources = {GUARD_MODULE} | _reexporters(modules)
    return [
        rel
        for rel in _opening(modules)
        if not _imports_guard_from(modules[rel], sources)
    ]


def _without_the_name(text: str) -> str:
    """The text with the guard's name replaced by another one: every import of it is gone."""
    return re.sub(rf"\b{GUARD}\b", "_something_else", text)


def _source(text: str) -> str | None:
    """The module the text imports the guard from (None when it does not)."""
    return next((node.module for node in _guard_imports(text)), None)


# --- the real tests ------------------------------------------------------------------------


def test_the_scan_finds_the_modules_that_open_a_chief():
    """A pattern that matched nothing would pass the check below for the wrong reason."""
    found = {Path(rel).name for rel in _opening(_modules())}

    assert len(found) >= 10, sorted(found)
    assert {
        "test_chief_acceptance.py",
        "test_chief_cli.py",
        "test_chief_routes.py",
        "test_chief_session.py",
        "test_chief_open_close_races.py",
        "test_comms_directives_route.py",
    } <= found


def test_every_module_that_opens_a_chief_imports_the_guard():
    assert unguarded(_modules()) == []


def test_the_guard_is_defined_once_in_the_session_guard_module():
    homes = [
        rel
        for rel, text in _modules().items()
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef) and node.name == GUARD
    ]

    assert homes == [f"{GUARD_MODULE}.py"]


def test_the_guard_is_an_autouse_fixture():
    tree = ast.parse((TESTS / f"{GUARD_MODULE}.py").read_text(encoding="utf-8"))
    (guard,) = [
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == GUARD
    ]

    decorators = [ast.unparse(d) for d in guard.decorator_list]

    assert decorators == ["pytest.fixture(autouse=True)"]


def test_the_guard_is_imported_under_its_own_name_everywhere():
    """An alias would hide it from this scan; a fixture defined again would shadow it."""
    aliased = [
        rel
        for rel, text in _modules().items()
        for node in _guard_imports(text)
        if any(a.name == GUARD and a.asname is not None for a in node.names)
    ]

    assert aliased == []


def test_only_support_modules_and_the_guard_module_are_import_sources():
    """A test module imports the guard from its home or from a support module that re-exports
    it, never from another test file."""
    sources = {GUARD_MODULE} | _reexporters(_modules())
    wrong = [
        (rel, node.module)
        for rel, text in _modules().items()
        for node in _guard_imports(text)
        if node.module not in sources
    ]

    assert wrong == []


# --- the scan catches what it is for -------------------------------------------------------


@pytest.mark.parametrize("rel", _opening(_modules()))
def test_dropping_the_import_from_one_module_is_caught(rel):
    modules = _modules()
    modules[rel] = _without_the_name(modules[rel])

    assert unguarded(modules) == [rel]


def test_dropping_the_import_from_test_chief_cli_is_caught():
    modules = _modules()
    rel = "http_api/test_chief_cli.py"
    assert rel in _opening(modules)
    modules[rel] = _without_the_name(modules[rel])

    assert unguarded(modules) == [rel]


@pytest.mark.parametrize(
    "rel",
    [rel for rel in _opening(_modules()) if _source(_modules()[rel]) != GUARD_MODULE],
)
def test_a_support_module_that_stops_importing_the_guard_is_caught(rel):
    """A test module that takes the guard from a support module is guarded only while that module
    imports it from ``chief_session_guard``."""
    modules = _modules()
    support = f"{_source(modules[rel])}.py"
    (support_rel,) = [r for r in modules if Path(r).name == support]
    modules[support_rel] = _without_the_name(modules[support_rel])

    assert rel in unguarded(modules)


def test_a_new_module_that_opens_a_chief_without_the_import_is_caught():
    modules = _modules()
    modules["http_api/test_chief_brand_new.py"] = (
        "def test_x(client):\n    client.post('/chief/open', json={})\n"
    )

    assert unguarded(modules) == ["http_api/test_chief_brand_new.py"]


def test_a_module_that_aliases_the_guard_is_caught():
    modules = _modules()
    modules["http_api/test_chief_brand_new.py"] = (
        "from chief_session_guard import _no_watcher_outlives_its_test as g\n"
        "def test_x():\n    open_chief()\n"
    )

    assert unguarded(modules) == ["http_api/test_chief_brand_new.py"]


# --- the exemptions ------------------------------------------------------------------------


@pytest.mark.parametrize("rel", sorted(EXEMPT))
def test_an_exemption_is_still_needed_and_still_true(rel):
    text = _modules()[rel]

    assert OPENS.search(text), f"{rel} no longer matches the scan: drop it from EXEMPT"
    assert not CALLS.search(text), f"{rel} now calls a function that opens a chief"
    assert not _guard_imports(text), f"{rel} imports the guard: drop it from EXEMPT"
