"""Read-policy core: row_allowed, policy_predicate and their agreement."""

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
OTHER = "run-other"


def _row(type_="discovery", role="builder", source="token", run=OTHER, **extra):
    row = {
        "type": type_,
        "author_role": role,
        "author_source": source,
        "author_run_id": run,
    }
    row.update(extra)
    return row


def test_type_only_withholds_any_author():
    pol = {"exclude_types": ["status"]}
    assert not row_allowed(_row("status", "architect"), pol, ME)
    assert row_allowed(_row("discovery", "architect"), pol, ME)


def test_author_only_withholds_nothing():
    assert row_allowed(
        _row("discovery", "builder"), {"exclude_authors": ["builder"]}, ME
    )


def test_type_and_author():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    assert not row_allowed(_row("discovery", "builder"), pol, ME)
    assert row_allowed(_row("discovery", "explorer"), pol, ME)
    assert row_allowed(_row("note", "builder"), pol, ME)


def test_empty_lists_withhold_nothing():
    for pol in ({}, {"exclude_types": [], "exclude_authors": []}, {"feature": True}):
        assert row_allowed(_row("discovery", "builder"), pol, ME)
    assert policy_predicate({}, ME) == ("1=1", [])
    assert policy_predicate(
        {"exclude_types": [], "exclude_authors": ["builder"]}, ME
    ) == ("1=1", [])


@pytest.mark.parametrize("type_", sorted(NEVER_WITHHELD_TYPES))
def test_never_withheld_types_kept(type_):
    pol = {"exclude_types": [type_, "discovery"], "exclude_authors": ["builder"]}
    assert row_allowed(_row(type_, "builder", "none", None), pol, ME)


def test_own_run_rows_kept():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    assert row_allowed(_row(run=ME), pol, ME)
    assert not row_allowed(_row(run=OTHER), pol, ME)
    assert not row_allowed(_row(run=ME), pol, None)


def test_unverified_row_of_excluded_type_withheld():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    assert not row_allowed(_row("discovery", None, "none", None), pol, ME)
    assert row_allowed(_row("discovery", None, "legacy", None), pol, ME)


def test_body_run_id_does_not_exempt():
    pol = {"exclude_types": ["discovery"], "exclude_authors": ["builder"]}
    row = _row(run=OTHER, run_id=ME, from_agent="explorer")
    assert not row_allowed(row, pol, ME)


def test_builtin_defaults_shape():
    assert set(BUILTIN_DEFAULTS) == {"reviewer", "tester", "chief", "anonymous"}
    assert BUILTIN_DEFAULTS["reviewer"]["exclude_types"] == [
        "discovery",
        "status",
        "nudge",
        "warning",
    ]
    assert BUILTIN_DEFAULTS["tester"]["exclude_authors"] == ["builder"]
    assert not BUILTIN_DEFAULTS["chief"].get("exclude_authors")
    anon = BUILTIN_DEFAULTS["anonymous"]
    assert set(anon["exclude_types"]) == {"discovery", "status", "nudge", "warning"}
    assert anon["exclude_authors"] == ["builder"]


TYPES = sorted(NEVER_WITHHELD_TYPES) + [
    "discovery",
    "status",
    "nudge",
    "warning",
    "note",
]
ROLES = ["builder", "reviewer", "explorer", "system", None]
SOURCES = ["token", "system", "legacy", "none"]


@pytest.mark.parametrize("name", sorted(BUILTIN_DEFAULTS))
@pytest.mark.parametrize("caller", [ME, None])
def test_predicate_matches_row_allowed(name, caller):
    policy = BUILTIN_DEFAULTS[name]
    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE comms_messages (id INTEGER PRIMARY KEY, type TEXT, "
        "author_role TEXT, author_source TEXT, author_run_id TEXT)"
    )
    rows = []
    for i, (t, r, s, run) in enumerate(
        itertools.product(TYPES, ROLES, SOURCES, [ME, OTHER, None]), 1
    ):
        rows.append(
            {
                "id": i,
                "type": t,
                "author_role": r,
                "author_source": s,
                "author_run_id": run,
            }
        )
    con.executemany(
        "INSERT INTO comms_messages VALUES (:id,:type,:author_role,:author_source,:author_run_id)",
        rows,
    )
    where, params = policy_predicate(policy, caller)
    got = {
        r[0]
        for r in con.execute(f"SELECT id FROM comms_messages WHERE {where}", params)
    }
    want = {r["id"] for r in rows if row_allowed(r, policy, caller)}
    assert got == want
    if policy.get("exclude_types"):
        assert len(got) < len(rows)
