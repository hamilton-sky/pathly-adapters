"""resolve_read_policy: per-role row -> per-feature row -> built-in default -> allow-all."""

from __future__ import annotations

import json
import sqlite3

import pytest

from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.runner.read_policy import BUILTIN_DEFAULTS, resolve_read_policy

ROOT = "C:/proj"
FEAT = "demo"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
    )
    return c


def _store(conn, role, value):
    key = f"board_scope:{ROOT}:{FEAT}" + (f":{role}" if role else "")
    set_setting(conn, key, json.dumps(value))


def _resolve(conn, role):
    return resolve_read_policy(conn, role, FEAT, project_root=ROOT)


def test_per_role_row_beats_builtin_default(conn):
    _store(conn, "reviewer", {"exclude_types": ["nudge"], "exclude_authors": []})
    p = _resolve(conn, "reviewer")
    assert p["exclude_types"] == ["nudge"]
    assert p["exclude_authors"] == []


def test_per_role_row_without_exclude_keys_is_allow_all_for_content(conn):
    _store(conn, "reviewer", {"feature": True, "project": False})
    p = _resolve(conn, "reviewer")
    assert p["exclude_types"] == []
    assert p["exclude_authors"] == []
    assert p["project"] is False


def test_per_feature_row_used_when_no_per_role_row(conn):
    _store(conn, None, {"exclude_types": ["status"], "exclude_authors": ["builder"]})
    p = _resolve(conn, "reviewer")
    assert p["exclude_types"] == ["status"]
    assert p["exclude_authors"] == ["builder"]


def test_builtin_default_for_reviewer_when_nothing_stored(conn):
    p = _resolve(conn, "reviewer")
    assert p["exclude_types"] == BUILTIN_DEFAULTS["reviewer"]["exclude_types"]
    assert p["exclude_authors"] == ["builder"]
    assert p["feature"] and p["project"] and p["global"]


def test_unknown_role_is_allow_all(conn):
    p = _resolve(conn, "wizard")
    assert p["exclude_types"] == []
    assert p["exclude_authors"] == []


def test_none_role_is_anonymous(conn):
    p = _resolve(conn, None)
    assert p["exclude_types"] == BUILTIN_DEFAULTS["anonymous"]["exclude_types"]
    assert p["exclude_authors"] == ["builder"]


def test_malformed_row_falls_through_to_builtin(conn):
    set_setting(conn, f"board_scope:{ROOT}:{FEAT}:reviewer", "not json")
    p = _resolve(conn, "reviewer")
    assert p["exclude_authors"] == ["builder"]
