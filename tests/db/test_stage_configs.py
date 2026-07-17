"""stage_configs query helpers — flow-phase-inspector (#5) per-stage selection persistence.

Covers the additive ability_ids + excluded_sections columns: they store the SELECTION
(JSON lists), read back as [] when absent (so callers never special-case NULL), and an
upsert replaces the whole selection.
"""

from __future__ import annotations

import sqlite3

from pathly_orchestrator.db.migrations import _run_migrations
from pathly_orchestrator.db.queries.stage_configs import (
    delete_stage_config,
    read_stage_config,
    upsert_stage_config,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _run_migrations(conn)
    return conn


def test_ability_ids_and_excluded_sections_roundtrip():
    conn = _conn()
    upsert_stage_config(
        conn,
        "/proj",
        "feat",
        "BUILDING",
        agent="builder",
        adapter="claude",
        ability_ids=["build/react-web", "build/tdd"],
        excluded_sections=["Extra notes", "Examples"],
    )
    cfg = read_stage_config(conn, "/proj", "feat", "BUILDING")
    assert cfg is not None
    assert cfg["agent"] == "builder"
    assert cfg["adapter"] == "claude"
    assert cfg["ability_ids"] == ["build/react-web", "build/tdd"]
    assert cfg["excluded_sections"] == ["Extra notes", "Examples"]


def test_absent_selection_reads_back_as_empty_lists():
    """A stage configured only with an agent (the pre-#5 shape) has no selection — the new
    columns must read back as [] so callers never special-case NULL."""
    conn = _conn()
    upsert_stage_config(conn, "/proj", "feat", "BUILDING", agent="builder")
    cfg = read_stage_config(conn, "/proj", "feat", "BUILDING")
    assert cfg is not None
    assert cfg["ability_ids"] == []
    assert cfg["excluded_sections"] == []


def test_upsert_replaces_the_selection():
    conn = _conn()
    upsert_stage_config(conn, "/proj", "feat", "S", ability_ids=["a/one"])
    upsert_stage_config(
        conn,
        "/proj",
        "feat",
        "S",
        ability_ids=["b/two"],
        excluded_sections=["Heading"],
    )
    cfg = read_stage_config(conn, "/proj", "feat", "S")
    assert cfg is not None
    assert cfg["ability_ids"] == ["b/two"]
    assert cfg["excluded_sections"] == ["Heading"]


def test_unknown_stage_is_none():
    conn = _conn()
    assert read_stage_config(conn, "/proj", "feat", "NOPE") is None


def test_delete_removes_the_config():
    conn = _conn()
    upsert_stage_config(conn, "/proj", "feat", "S", ability_ids=["a/one"])
    delete_stage_config(conn, "/proj", "feat", "S")
    assert read_stage_config(conn, "/proj", "feat", "S") is None
