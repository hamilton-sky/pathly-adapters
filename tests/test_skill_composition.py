"""Tests for DB-backed composition overrides (skill_composition + load_effective_manifest)."""

from __future__ import annotations

import sqlite3

from pathly_orchestrator.db.migrations import _run_migrations
from pathly_orchestrator.db.queries.skill_composition import (
    delete_composition_override,
    get_composition_overrides,
    set_composition_override,
)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    _run_migrations(c)
    return c


# ── query round-trip ──────────────────────────────────────────────────────────


def test_override_roundtrip():
    c = _conn()
    assert get_composition_overrides(c) == {}
    set_composition_override(c, None, "team/build", ["a", "b"])
    assert get_composition_overrides(c)["team/build"] == ["a", "b"]
    # upsert replaces, does not duplicate
    set_composition_override(c, None, "team/build", ["c"])
    assert get_composition_overrides(c)["team/build"] == ["c"]
    # delete reverts to absent
    delete_composition_override(c, None, "team/build")
    assert "team/build" not in get_composition_overrides(c)


def test_project_override_wins_over_global():
    c = _conn()
    set_composition_override(c, None, "team/build", ["global"])
    set_composition_override(c, "/proj", "team/build", ["proj"])
    assert get_composition_overrides(c, "/proj")["team/build"] == ["proj"]
    assert get_composition_overrides(c, None)["team/build"] == ["global"]
    # a different project sees only the global one
    assert get_composition_overrides(c, "/other")["team/build"] == ["global"]


def test_override_path_normalization_matches():
    # The editor writes with forward slashes; the runner reads with OS-native
    # backslashes. Both must resolve to the same per-project override.
    c = _conn()
    set_composition_override(c, "C:/Users/x/repo", "team/build", ["a"])
    assert get_composition_overrides(c, "C:\\Users\\x\\repo")["team/build"] == ["a"]
    # trailing slash is irrelevant too
    set_composition_override(c, "C:/Users/x/repo/", "team/build", ["b"])
    assert get_composition_overrides(c, "C:\\Users\\x\\repo")["team/build"] == ["b"]


# ── load_effective_manifest merge ───────────────────────────────────────────────


def test_effective_manifest_empty_is_identical_to_base(monkeypatch):
    from pathly_orchestrator import compose
    import pathly_orchestrator.db.connection as dbconn
    import pathly_orchestrator.db.queries.skill_composition as sc

    monkeypatch.setattr(dbconn, "get_db", lambda *a, **k: None)
    monkeypatch.setattr(sc, "get_composition_overrides", lambda conn, pr=None: {})
    assert compose.load_effective_manifest("/proj") == compose.load_manifest()


def test_effective_manifest_applies_override(monkeypatch):
    from pathly_orchestrator import compose
    import pathly_orchestrator.db.connection as dbconn
    import pathly_orchestrator.db.queries.skill_composition as sc

    monkeypatch.setattr(dbconn, "get_db", lambda *a, **k: None)
    monkeypatch.setattr(
        sc,
        "get_composition_overrides",
        lambda conn, pr=None: {"team/build": ["scout-choreography"]},
    )
    eff = compose.load_effective_manifest("/proj")
    assert eff["skills"]["team/build"]["fragments"] == ["scout-choreography"]
    # base manifest is untouched
    assert compose.load_manifest()["skills"]["team/build"]["fragments"] != [
        "scout-choreography"
    ]


def test_effective_manifest_failsafe_on_db_error(monkeypatch):
    from pathly_orchestrator import compose
    import pathly_orchestrator.db.connection as dbconn

    def _boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(dbconn, "get_db", _boom)
    # Any DB error must degrade to the pure YAML manifest, never raise.
    assert compose.load_effective_manifest("/proj") == compose.load_manifest()
