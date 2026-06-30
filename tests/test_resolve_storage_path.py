"""Tests for _resolve_storage_path with the 3-tier probe order (P1)."""
from __future__ import annotations

from pathlib import Path

import pytest

import pathly_orchestrator.fsm_ops as fsm_ops


FLOW = {"storage_path": "pathly/plans/{topic}/"}


def test_prefers_goals_tier_when_dir_exists(tmp_path):
    """pathly/goals/<slug> is returned when that dir exists."""
    slug = "my-goal-slug"
    goal_dir = tmp_path / "pathly" / "goals" / slug
    goal_dir.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), slug)
    assert result == goal_dir


def test_goals_tier_has_exactly_two_components_under_pathly(tmp_path):
    """Storage path is pathly/goals/<slug> — exactly 2 components under pathly."""
    slug = "two-components"
    goal_dir = tmp_path / "pathly" / "goals" / slug
    goal_dir.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), slug)
    # parent.parent.parent must equal project_root (watcher invariant)
    assert result.parent.parent.parent == tmp_path


def test_absolute_topic_raises(tmp_path):
    """_safe_topic now raises on absolute paths (P1 flip)."""
    absolute = str(tmp_path / "some" / "absolute" / "path")
    with pytest.raises(ValueError, match="unsafe topic"):
        fsm_ops._resolve_storage_path(FLOW, str(tmp_path), absolute)


def test_feature_slug_resolves_plans_or_pathly(tmp_path):
    """Feature slugs still resolve to pathly/plans/<slug> when no goals/ dir exists."""
    slug = "feature-abc"
    plans_dir = tmp_path / "pathly" / "plans" / slug
    plans_dir.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), slug)
    assert result == plans_dir


def test_new_style_pathly_topic_still_wins(tmp_path):
    """pathly/<topic> (new-style) wins over goals/ when it exists."""
    slug = "direct-topic"
    new_style = tmp_path / "pathly" / slug
    new_style.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), slug)
    assert result == new_style
