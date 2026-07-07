"""Unit tests for the cross-feature file-claim overlap registry."""

from __future__ import annotations

import pytest

from pathly_orchestrator.supervisor import file_claims


@pytest.fixture(autouse=True)
def _reset():
    file_claims._claims.clear()
    yield
    file_claims._claims.clear()


def test_disjoint_claims_coexist():
    assert file_claims.try_claim("A", ["src/api/x.py"]) is None
    assert file_claims.try_claim("B", ["studio/src/y.tsx"]) is None  # disjoint -> ok


def test_same_file_conflicts():
    assert file_claims.try_claim("A", ["src/x.py"]) is None
    assert file_claims.try_claim("B", ["src/x.py"]) == "A"


def test_directory_containment_overlaps():
    assert file_claims.try_claim("A", ["src/api"]) is None
    assert (
        file_claims.try_claim("B", ["src/api/routes.py"]) == "A"
    )  # dir covers the file


def test_undeclared_is_wildcard():
    assert file_claims.try_claim("A", []) is None  # no files -> wildcard
    assert file_claims.try_claim("B", ["anything.py"]) == "A"  # wildcard overlaps all


def test_release_frees_the_claim():
    file_claims.try_claim("A", ["src/x.py"])
    file_claims.release("A")
    assert file_claims.try_claim("B", ["src/x.py"]) is None  # A gone -> B may claim


def test_reclaim_same_scope_refreshes():
    assert file_claims.try_claim("A", ["src/a.py"]) is None
    assert (
        file_claims.try_claim("A", ["src/b.py"]) is None
    )  # same scope -> refresh, no self-conflict
    assert file_claims.active()["A"] == ["src/b.py"]
