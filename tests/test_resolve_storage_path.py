"""Tests for _resolve_storage_path with the 3-tier probe order (P1)."""
from __future__ import annotations

from pathlib import Path

import pytest

import pathly_orchestrator.fsm_ops as fsm_ops


FLOW = {"storage_path": "pathly/plans/{topic}/"}


def test_flat_pathly_goals_no_longer_resolves(tmp_path):
    """The flat pathly/goals/<slug> candidate is DROPPED — goals nest by board scope now. A bare
    slug with a stray pathly/goals/<slug> dir falls through to the flow template default."""
    slug = "my-goal-slug"
    goal_dir = tmp_path / "pathly" / "goals" / slug
    goal_dir.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), slug)
    assert result != goal_dir
    assert result == tmp_path / "pathly" / "plans" / slug  # FLOW template fallback


def test_scope_nested_feature_goal_topic_resolves(tmp_path):
    """A consultation's feature-tier topic (features/<f>/goals/<slug>) lands at the nested dir
    via the pathly/<topic> candidate."""
    nested = tmp_path / "pathly" / "features" / "my-feature" / "goals" / "g-slug"
    nested.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), "features/my-feature/goals/g-slug")
    assert result == nested


def test_scope_nested_project_goal_topic_resolves(tmp_path):
    """A project-tier goal topic (project/goals/<slug>) resolves under pathly/project/."""
    nested = tmp_path / "pathly" / "project" / "goals" / "g-slug"
    nested.mkdir(parents=True)
    result = fsm_ops._resolve_storage_path(FLOW, str(tmp_path), "project/goals/g-slug")
    assert result == nested


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
