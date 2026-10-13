"""resolve_read_policy: per-role row -> per-feature row -> built-in default -> allow all."""

from __future__ import annotations

import json

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.runner.read_policy import BUILTIN_DEFAULTS, resolve_read_policy

ROOT = "C:/proj"
FEATURE = "demo"


def _put(role, value):
    key = f"board_scope:{ROOT}:{FEATURE}" + (f":{role}" if role else "")
    set_setting(get_db(), key, json.dumps(value))


def _resolve(role):
    return resolve_read_policy(get_db(), role, FEATURE, project_root=ROOT)


def test_per_role_row_beats_builtin_default():
    _put("reviewer", {"exclude_types": ["warning"], "exclude_authors": ["tester"]})
    p = _resolve("reviewer")
    assert p["exclude_types"] == ["warning"]
    assert p["exclude_authors"] == ["tester"]


def test_per_role_row_without_exclude_keys_is_allow_all_for_content():
    _put("reviewer", {"feature": True, "project": False, "global": True})
    p = _resolve("reviewer")
    assert not p.get("exclude_types")
    assert not p.get("exclude_authors")
    assert p["project"] is False


def test_per_feature_row_used_when_no_per_role_row():
    _put(None, {"exclude_types": ["nudge"]})
    assert _resolve("builder")["exclude_types"] == ["nudge"]
    # a feature row without exclude keys also stops the built-in wall
    _put(None, {"feature": True})
    assert not _resolve("reviewer").get("exclude_types")


def test_builtin_default_for_reviewer_when_nothing_stored():
    p = _resolve("reviewer")
    assert p["exclude_types"] == BUILTIN_DEFAULTS["reviewer"]["exclude_types"]
    assert p["exclude_authors"] == ["builder"]


def test_builtin_result_is_a_copy():
    p = _resolve("reviewer")
    p["exclude_types"].append("x")
    p["exclude_authors"].clear()
    assert "x" not in BUILTIN_DEFAULTS["reviewer"]["exclude_types"]
    assert BUILTIN_DEFAULTS["reviewer"]["exclude_authors"] == ["builder"]
    a = resolve_read_policy(get_db(), None, FEATURE)
    a["exclude_types"].clear()
    assert BUILTIN_DEFAULTS["anonymous"]["exclude_types"]


def test_unknown_role_is_allow_all():
    p = _resolve("wizard")
    assert not p.get("exclude_types")
    assert not p.get("exclude_authors")


def test_none_role_is_anonymous_builtin():
    assert resolve_read_policy(get_db(), None, FEATURE) == BUILTIN_DEFAULTS["anonymous"]


def test_anonymous_role_name_is_builtin_key():
    p = _resolve("anonymous")
    assert p["exclude_authors"] == BUILTIN_DEFAULTS["anonymous"]["exclude_authors"]


def test_malformed_role_row_falls_through():
    set_setting(get_db(), f"board_scope:{ROOT}:{FEATURE}:reviewer", "not json")
    _put(None, {"exclude_types": ["nudge"]})
    assert _resolve("reviewer")["exclude_types"] == ["nudge"]


@pytest.mark.parametrize("role", ["reviewer", "tester", "chief"])
def test_builtin_roles_resolve(role):
    assert _resolve(role)["exclude_types"] == BUILTIN_DEFAULTS[role]["exclude_types"]
