"""flow-phase-inspector (#5) apply-at-spawn: build_prompt applies a stage's saved selection.

Covers the pure post-compose transform helpers _drop_sections + _apply_stage_selection: a
selection drops excluded ``##`` sections and appends the chosen layer-3 abilities, while an
empty selection is byte-identical (the guard that keeps every existing flow run unchanged).
"""

from __future__ import annotations

from pathly_orchestrator.fsm_compose import _apply_stage_selection, _drop_sections

SAMPLE = """# Build skill

Intro line.

## Approach

Do the thing.

## Extra notes

Trim me.

## Completion report

Locked platform section.
"""


def test_drop_sections_removes_named_h2_keeps_others():
    out = _drop_sections(SAMPLE, {"Extra notes"})
    assert "## Extra notes" not in out
    assert "Trim me." not in out
    # Sibling H2s, the H1 title, and the (locked) platform section all survive.
    assert "## Approach" in out
    assert "Do the thing." in out
    assert "# Build skill" in out
    assert "## Completion report" in out


def test_drop_sections_empty_is_noop():
    assert _drop_sections(SAMPLE, set()) == SAMPLE


def test_drop_sections_multiple_named():
    out = _drop_sections(SAMPLE, {"Approach", "Extra notes"})
    assert "## Approach" not in out
    assert "## Extra notes" not in out
    assert "## Completion report" in out


def test_apply_selection_noop_when_empty():
    assert _apply_stage_selection(SAMPLE, [], [], "/proj") == SAMPLE
    assert _apply_stage_selection(SAMPLE, None, None, "/proj") == SAMPLE


def test_apply_selection_drops_excluded_sections():
    out = _apply_stage_selection(SAMPLE, [], ["Extra notes"], "/proj")
    assert "Trim me." not in out
    assert "## Approach" in out


def test_apply_selection_appends_selected_ability(tmp_path):
    from pathly_orchestrator.skills.abilities import write_ability

    write_ability(
        "build",
        "react-web",
        "# React web\n\nPrefer function components.",
        project_root=str(tmp_path),
        scope="project",
    )
    out = _apply_stage_selection(
        "# Skill\n\nBody.", ["build/react-web"], [], str(tmp_path)
    )
    assert out.startswith("# Skill")
    assert "Prefer function components." in out


def test_apply_selection_unknown_ability_is_skipped(tmp_path):
    out = _apply_stage_selection("# Skill\n\nBody.", ["build/nope"], [], str(tmp_path))
    assert out == "# Skill\n\nBody."
