"""Tests for T6: goal-slug routing at goal call sites."""

from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

import pytest


def _make_test_db(tmp_path: Path) -> sqlite3.Connection:
    """Seed a temp SQLite DB with migrations and return a connection."""
    conn = sqlite3.connect(str(tmp_path / "pathly.db"))
    conn.row_factory = sqlite3.Row
    from pathly_orchestrator.db.migrations import _run_migrations

    _run_migrations(conn)
    return conn


def _insert_goal(
    conn: sqlite3.Connection, goal_id: str, scope: str, board: str = "project"
) -> None:
    now = "2026-06-30T00:00:00Z"
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (goal_id, board, scope, "human", "goal", "Implement the feature", now),
    )
    conn.commit()


def test_ensure_goal_slug_formats_correctly(tmp_path):
    """ensure_goal_slug produces <slugified-text>-<id[:8]> from a plain goal row."""
    conn = _make_test_db(tmp_path)
    goal_id = str(uuid.uuid4())
    _insert_goal(conn, goal_id, "my-project", board="project")

    from pathly_orchestrator.supervisor.slug import ensure_goal_slug

    slug = ensure_goal_slug(conn, goal_id)

    # Slug should contain the goal_id prefix and be filesystem-safe
    assert goal_id[:8] in slug
    assert " " not in slug
    assert "/" not in slug
    assert "\\" not in slug


def test_ensure_goal_slug_is_idempotent(tmp_path):
    """Calling ensure_goal_slug twice returns the same slug with no extra writes."""
    conn = _make_test_db(tmp_path)
    goal_id = str(uuid.uuid4())
    _insert_goal(conn, goal_id, str(tmp_path), board="project")

    from pathly_orchestrator.supervisor.slug import ensure_goal_slug

    slug1 = ensure_goal_slug(conn, goal_id)
    slug2 = ensure_goal_slug(conn, goal_id)

    assert slug1 == slug2


def test_project_goal_nests_under_project(tmp_path):
    """A project-tier goal's storage nests under pathly/project/goals/<slug> (no flat pathly/goals)."""
    conn = _make_test_db(tmp_path)
    goal_id = str(uuid.uuid4())
    _insert_goal(conn, goal_id, str(tmp_path), board="project")

    from pathly_orchestrator.supervisor.slug import ensure_goal_slug
    from pathly_orchestrator.supervisor.goal_decomposer import _goal_storage_dir

    slug = ensure_goal_slug(conn, goal_id)
    goal_dir = _goal_storage_dir(str(tmp_path), "project", str(tmp_path), slug).replace(
        "\\", "/"
    )

    expected = str(tmp_path / "pathly" / "project" / "goals" / slug).replace("\\", "/")
    assert goal_dir == expected
    assert "pathly/goals/" not in goal_dir  # the flat pathly/goals home is gone


def test_resolve_nested_project_goal_topic(tmp_path):
    """A project-tier goal's scope-nested topic (project/goals/<slug>) resolves under pathly/project/."""
    nested = tmp_path / "pathly" / "project" / "goals" / "g-slug"
    nested.mkdir(parents=True)

    from pathly_orchestrator.fsm_ops import _resolve_storage_path

    flow = {"storage_path": "pathly/{topic}/"}
    result = _resolve_storage_path(flow, str(tmp_path), "project/goals/g-slug")
    assert result == nested


def test_feature_slug_still_resolves_plans(tmp_path):
    """Feature slugs (not under goals/) still resolve to pathly/plans/<slug>."""
    slug = "my-feature"
    plans_dir = tmp_path / "pathly" / "plans" / slug
    plans_dir.mkdir(parents=True)

    from pathly_orchestrator.fsm_ops import _resolve_storage_path

    flow = {"storage_path": "pathly/plans/{topic}/"}
    result = _resolve_storage_path(flow, str(tmp_path), slug)
    assert result == plans_dir


def test_absolute_scope_never_reaches_fsm_ops(tmp_path):
    """_safe_topic raises on absolute scope so project-path scopes are caught early."""
    from pathly_orchestrator.storage_paths import _safe_topic

    absolute = str(tmp_path / "some" / "absolute")
    with pytest.raises(ValueError, match="unsafe topic"):
        _safe_topic(absolute)
