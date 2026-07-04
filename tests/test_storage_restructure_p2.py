"""storage-restructure Phase 2 — feature-nested goal storage + robust project-root derivation.

Covers the two safe, self-contained changes:
  1. goal_decomposer._goal_storage_dir — planner/plan decompose nests feature-tier goals under
     pathly/features/<feature>/goals/<slug>; project/global stay legacy.
  2. fsm_compose._project_root_from_storage — derive the project root from the `pathly/` anchor
     instead of a fixed parent.parent.parent (which broke for any nested storage path).
"""

from pathlib import Path

from pathly_orchestrator.supervisor.goal_decomposer import (
    _goal_storage_dir,
    _goal_topic,
    board_run_storage_dir,
    board_run_topic,
)
from pathly_orchestrator.fsm_compose import _project_root_from_storage

ROOT = str(Path("/proj").resolve())


def _n(p: str) -> str:
    return p.replace("\\", "/")


# ── _goal_topic + _goal_storage_dir (board-scoped; no flat pathly/goals) ──────

def test_goal_topic_feature_tier():
    assert _goal_topic("feature", "my-feature", "goal-slug") == "features/my-feature/goals/goal-slug"


def test_goal_topic_project_tier():
    # Project-tier scope is the project root path; the topic uses the singular 'project' home.
    assert _goal_topic("project", "/some/root", "goal-slug") == "project/goals/goal-slug"


def test_goal_topic_global_tier():
    assert _goal_topic("global", "global", "goal-slug") == "project/goals/goal-slug"


def test_goal_topic_feature_empty_scope_falls_back():
    # Defensive: a feature board with an empty scope must not build features//goals/…
    assert _goal_topic("feature", "", "goal-slug") == "project/goals/goal-slug"


def test_feature_tier_nests_under_feature():
    d = _goal_storage_dir(ROOT, "feature", "my-feature", "goal-slug")
    assert _n(d).endswith("pathly/features/my-feature/goals/goal-slug")


def test_project_tier_nests_under_project():
    d = _goal_storage_dir(ROOT, "project", "/some/root", "goal-slug")
    assert _n(d).endswith("pathly/project/goals/goal-slug")
    assert "pathly/goals/" not in _n(d)  # the flat pathly/goals home is gone


# ── board_run_topic — generalize goal nesting to every run kind (board-scoped-storage) ──


def test_board_run_topic_nests_every_kind_under_the_board():
    for kind in ("goals", "explorations", "debugs", "fixes"):
        assert board_run_topic("feature", "my-feature", kind, "slug") == f"features/my-feature/{kind}/slug"
        # project + global + empty-scope all collapse to the project home
        assert board_run_topic("project", "/some/root", kind, "slug") == f"project/{kind}/slug"
        assert board_run_topic("global", "global", kind, "slug") == f"project/{kind}/slug"
        assert board_run_topic("feature", "", kind, "slug") == f"project/{kind}/slug"


def test_goal_helpers_are_board_run_goals_wrappers():
    # _goal_topic / _goal_storage_dir must stay byte-identical to the 'goals' kind.
    assert _goal_topic("feature", "f", "s") == board_run_topic("feature", "f", "goals", "s")
    assert _goal_topic("project", "/r", "s") == "project/goals/s"
    assert _n(_goal_storage_dir(ROOT, "feature", "f", "s")) == _n(
        board_run_storage_dir(ROOT, "feature", "f", "goals", "s")
    )


def test_board_run_storage_dir_absolute_nested():
    d = board_run_storage_dir(ROOT, "feature", "my-feature", "explorations", "slug")
    assert _n(d).endswith("pathly/features/my-feature/explorations/slug")


# ── _project_root_from_storage ───────────────────────────────────────

def test_legacy_plans_identical_to_old_behavior():
    # The dominant production layout: <root>/pathly/plans/<topic> (3 levels). Here the new
    # anchor-based derivation MUST equal the old parent.parent.parent it replaced.
    sp = Path(ROOT) / "pathly" / "plans" / "my-feature"
    assert _n(_project_root_from_storage(sp)) == _n(ROOT)
    assert _project_root_from_storage(sp) == str(sp.parent.parent.parent)


def test_new_style_flat_resolves_root():
    # <root>/pathly/<topic> (2 levels) — old parent.parent.parent overshot to <root>'s parent.
    sp = Path(ROOT) / "pathly" / "my-feature"
    assert _n(_project_root_from_storage(sp)) == _n(ROOT)


def test_phase1_feature_plans_resolves_root():
    # <root>/pathly/features/<f>/plans — the latent Phase-1 bug: old gave <root>/pathly/features.
    sp = Path(ROOT) / "pathly" / "features" / "my-feature" / "plans"
    assert _n(_project_root_from_storage(sp)) == _n(ROOT)


def test_phase2_nested_goal_resolves_root():
    sp = Path(ROOT) / "pathly" / "features" / "my-feature" / "goals" / "slug"
    assert _n(_project_root_from_storage(sp)) == _n(ROOT)


def test_project_dir_named_like_pathly_not_confused():
    # A project dir whose name merely contains 'pathly' (e.g. …/pathly-adapters) is not the
    # anchor — only an exact 'pathly' path segment is. Uses the LAST such segment.
    base = Path(ROOT) / "pathly-adapters"
    sp = base / "pathly" / "plans" / "my-feature"
    assert _n(_project_root_from_storage(sp)) == _n(str(base))
