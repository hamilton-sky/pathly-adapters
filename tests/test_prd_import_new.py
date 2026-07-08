"""Board-native PRD import contract (planner-hierarchy G3).

The import skill is prompt-driven, so these tests lock the deterministic surface:
composition, emitted board-card contracts, dependency semantics, and removal of
the legacy conversation-file workflow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import pathly_data
from pathly_orchestrator import compose
from pathly_orchestrator.skills.compose import compose_skill

pytestmark = pytest.mark.no_pathly_autouse


def _skill_text() -> str:
    p = Path(pathly_data.__file__).parent / "core" / "skills" / "planning" / "prd-import.md"
    return p.read_text(encoding="utf-8")


def _composed() -> str:
    return compose_skill("planning/prd-import", "claude")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def test_prd_import_composition_matches_terminal_emitters():
    manifest = compose.load_manifest()
    cfg = manifest["skills"]["planning/prd-import"]
    assert cfg["no_defaults"] is True
    assert cfg["fragments"] == ["code-query", "comms-post", "completion-report"]


def test_composed_prompt_posts_features_and_goals_not_tasks():
    body = _composed()
    assert '"type": "feature"' in body
    assert '"board": "project"' in body
    assert '"type": "goal"' in body
    assert '"board": "feature"' in body
    assert "feature-board `type=goal` cards" in body
    assert "type=task" not in _skill_text()
    assert "goal_id" not in _skill_text()


def test_prd_import_removes_legacy_conversation_output():
    body = _skill_text()
    assert "CONVERSATION_PROMPTS.md" not in body
    assert "PROGRESS.md phases" not in body
    assert "4/8-file PRD plan output" not in body
    assert "USER_STORIES.md" not in body
    assert "IMPLEMENTATION_PLAN.md" not in body


def test_prd_import_argument_contract_is_project_scoped():
    body = _skill_text()
    assert "<path/to/PRD.md> [project_scope_or_root]" in body
    assert "<feature-name> <path/to/PRD.md>" in body
    assert "Do not use the old" in body
    assert "derive a readable project key from the PRD title" in body


def test_prd_import_requires_idempotency_before_feature_and_goal_posts():
    body = _skill_text()
    assert "board=project&scope=$PROJECT&type=feature" in body
    assert "feature=$FEATURE&scope=$FEATURE&type=goal" in body
    flat = _one_line(body)
    assert "do not duplicate the feature set" in flat
    assert "do not duplicate that goal set" in flat


def test_prd_import_dependency_contract_is_message_id_based_at_all_levels():
    body = _skill_text()
    assert "Epic dependencies -> feature-card `depends_on`" in body
    assert "Story dependencies -> goal-card `depends_on`" in body
    assert "`depends_on` must always store returned board `message_id` values" in body
    assert "never slugs" in body
    assert '"depends_on": ["<message_id_of_feature_dependency>"]' in body
    assert '"depends_on": ["<message_id_of_goal_dependency>"]' in body
    assert "Task dependencies remain the executable DAG under one goal" in body


def test_prd_import_scaffolds_feature_specs_and_materializes_feature_boards():
    body = _skill_text()
    assert "pathly/features/<feature-slug>/SPEC.md" in body
    assert "Materialize each feature board/root goal" in body
    assert "matching `planning/project-decompose` behavior" in _one_line(body)
    assert '"executor": "single"' in body


def test_prd_import_bmad_and_generic_mapping_contracts():
    body = _skill_text()
    assert "Epics -> project-board `type=feature` cards" in body
    assert "Stories -> feature-board `type=goal` cards" in body
    assert "Propose 2-5 project-board features" in body
    assert "Generic PRD" in body
