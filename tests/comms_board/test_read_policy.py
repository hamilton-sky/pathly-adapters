"""Read policy core: row_allowed rules and the SQL predicate agreeing with it."""

import itertools
import sqlite3

import pytest

from pathly_orchestrator.runner.read_policy import (
    BUILTIN_DEFAULTS,
    NEVER_WITHHELD_TYPES,
    policy_predicate,
    row_allowed,
)

ME = "run-me"


def _row(type_="discovery", role="builder", source="token", run=None, **extra):
    return {
        "type": type_,
        "author_role": role,
        "author_source": source,
        "author_run_id": run,
        **extra,
    }


def test_type_only_withholds_any_author():
    pol = {"exclude_types": ["status"]}
    assert not row_allowed(_row("status", "architect"), pol, ME)
    assert row_allowed(_row("discovery", "architect"), pol, ME)


def test_author_only_withholds_nothing():
    pol = {"exclude_authors": ["builder"]}
    assert row_allowed(_row("discovery", "builder"), pol, ME)


def test_type_and_author():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    assert not row_allowed(_row("discovery", "builder"), pol, ME)
    assert row_allowed(_row("discovery", "explorer"), pol, ME)
    assert row_allowed(_row("status", "builder"), pol, ME)


def test_empty_lists_withhold_nothing():
    for pol in ({}, {"exclude_types": [], "exclude_authors": []}, {"feature": True}):
        assert row_allowed(_row("discovery"), pol, ME)
        assert policy_predicate(pol, ME) == ("1=1", [])


@pytest.mark.parametrize("t", sorted(NEVER_WITHHELD_TYPES))
def test_never_withheld_types_kept(t):
    pol = {"exclude_types": [t, "discovery"], "exclude_authors": ["builder"]}
    assert row_allowed(_row(t, "builder"), pol, ME)


def test_own_run_rows_kept():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    assert row_allowed(_row(run=ME), pol, ME)
    assert not row_allowed(_row(run="other"), pol, ME)


def test_unverified_row_of_excluded_type_withheld():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    assert not row_allowed(_row(role=None, source="none"), pol, ME)
    assert row_allowed(_row(role=None, source="none", type_="decision"), pol, ME)


def test_body_run_id_does_not_exempt():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    row = _row(run="other", run_id=ME, from_agent="reviewer")
    assert not row_allowed(row, pol, ME)


def test_builtin_defaults_shape():
    assert BUILTIN_DEFAULTS["reviewer"]["exclude_types"] == [
        "discovery",
        "status",
        "nudge",
        "warning",
    ]
    assert BUILTIN_DEFAULTS["tester"]["exclude_types"] == [
        "discovery",
        "status",
        "nudge",
    ]
    assert "exclude_authors" not in BUILTIN_DEFAULTS["chief"]
    anon = BUILTIN_DEFAULTS["anonymous"]
    assert set(anon["exclude_types"]) == {"discovery", "status", "nudge", "warning"}
    assert anon["exclude_authors"] == ["builder"]


TYPES = sorted(
    NEVER_WITHHELD_TYPES | {"discovery", "status", "nudge", "warning", "note"}
) + [None]
ROLES = ["builder", "explorer", "reviewer", "system", None]
SOURCES = ["token", "system", "legacy", "none"]


@pytest.mark.parametrize("name", sorted(BUILTIN_DEFAULTS))
@pytest.mark.parametrize("caller", [ME, None])
def test_predicate_agrees_with_row_allowed(name, caller):
    pol = BUILTIN_DEFAULTS[name]
    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE comms_messages (id INTEGER PRIMARY KEY, type TEXT, author_role TEXT,"
        " author_source TEXT, author_run_id TEXT)"
    )
    rows = []
    for i, (t, r, s, run) in enumerate(
        itertools.product(TYPES, ROLES, SOURCES, [ME, "other", None]), start=1
    ):
        rows.append({"id": i, **_row(t, r, s, run)})
        con.execute("INSERT INTO comms_messages VALUES (?,?,?,?,?)", (i, t, r, s, run))
    sql, params = policy_predicate(pol, caller)
    got = {
        r[0] for r in con.execute(f"SELECT id FROM comms_messages WHERE {sql}", params)
    }
    want = {r["id"] for r in rows if row_allowed(r, pol, caller)}
    assert got == want
    assert want and len(want) < len(rows)
