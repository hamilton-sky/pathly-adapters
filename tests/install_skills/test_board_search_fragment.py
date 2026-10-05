"""The board-search fragment — an agent's own query back to the board.

Board context is pushed from ONE query the runner derives from the task
description. `board-search` gives the agent the second, self-authored query it
previously had no way to make: `/comms/search` existed but no fragment exposed
it, so an agent handed a weak semantic match had no recourse but to proceed.

Wired alongside `catalog-pull` — wherever an agent may already PULL from the
board by path, it may also SEARCH it by question.

The tiers it may search are the run's OWN board-scope setting, injected as
`<search_tiers>` — an extension inside that governance, never around it. Both
substitution sites (the flow path's `build_prompt` and the board-run mirror
`_inject_board_prompt_vars`) are pinned below, because an unsubstituted
placeholder would ship the literal string `<search_tiers>` to a CLI.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.skills.compose import compose_skill

_HEADING = "## Searching the board"

# Every skill that composes catalog-pull composes board-search too.
_SEARCH_SKILLS = [
    "team/build",
    "team/review",
    "development/build",
    "development/review",
    "debug/build",
]


@pytest.mark.parametrize("skill", _SEARCH_SKILLS)
def test_search_fragment_composes_exactly_once(skill):
    out = compose_skill(skill, "claude")
    assert out.count(_HEADING) == 1, f"{skill}: board-search not composed exactly once"


@pytest.mark.parametrize("skill", _SEARCH_SKILLS)
def test_search_pairs_with_catalog_pull(skill):
    """The two pull affordances travel together — search finds it, catalog reads it."""
    out = compose_skill(skill, "claude")
    assert "## Pulling context from the Board Catalog" in out
    assert _HEADING in out


def test_not_composed_into_unrelated_skills():
    """Scope stays where catalog-pull already reaches; design/retro are untouched."""
    for skill in ("team/design", "team/retro"):
        assert _HEADING not in compose_skill(skill, "claude")


def test_fragment_targets_the_real_search_endpoint():
    out = compose_skill("team/build", "claude")
    body = out[out.index(_HEADING) :]
    assert "/comms/search" in body
    # The hardened bounds the route enforces must not be misdescribed to the agent.
    assert "512" in body, "query length cap should be stated"
    assert "max 50" in body, "k cap should be stated"


def test_fragment_only_uses_substituted_placeholders():
    """`<feature>`/`<board>`/`<search_tiers>` are injected by the runner; the rest ships literally."""
    from tests._paths import SRC

    text = (SRC / "pathly_data/core/skills/fragments/board-search.md").read_text(
        encoding="utf-8"
    )
    import re

    used = set(re.findall(r"<([a-z_]+)>", text))
    substituted = {
        "feature",
        "board",
        "project_root",
        "agent",
        "run_id",
        "search_tiers",
    }
    assert used <= substituted, f"unsubstituted placeholder(s): {used - substituted}"


def test_search_tiers_substituted_on_the_flow_path(tmp_path):
    """build_prompt leaves no literal `<search_tiers>` and names each tier's own scope."""
    from pathly_orchestrator.fsm_compose import build_prompt

    storage = tmp_path / "pathly" / "features" / "demo-feature"
    storage.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(
        {"agent_map": {"BUILDING": "team/build"}, "composition": {}},
        "BUILDING",
        storage,
    )

    assert "<search_tiers>" not in prompt, "placeholder reached the CLI verbatim"
    # Default (nothing configured) = all three tiers, each with the scope that addresses it:
    # the feature slug, the normalized project root, and the literal "global".
    assert 'board "feature" + scope "demo-feature"' in prompt
    assert f'board "project" + scope "{tmp_path.as_posix()}"' in prompt
    assert 'board "global" + scope "global"' in prompt


def test_search_tiers_substituted_on_the_board_run_path(tmp_path):
    """The board-run mirror substitutes it too — board runs bypass build_prompt entirely."""
    from pathly_orchestrator.supervisor.board_run import _inject_board_prompt_vars

    out = _inject_board_prompt_vars(
        "search here: <search_tiers>",
        scope="demo-feature",
        board="feature",
        agent="builder",
        skill="development/build",
        project_root=str(tmp_path),
        storage_path=str(tmp_path / "pathly" / "features" / "demo-feature"),
    )

    assert "<search_tiers>" not in out
    assert 'board "feature" + scope "demo-feature"' in out


def test_search_tiers_follows_the_board_scope_setting(tmp_path):
    """A disabled tier is not offered for search — the fragment extends the governance,
    it does not route around it."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_board_scope
    from pathly_orchestrator.fsm_compose import build_prompt

    storage = tmp_path / "pathly" / "features" / "demo-feature"
    storage.mkdir(parents=True, exist_ok=True)
    set_board_scope(
        get_db(),
        tmp_path.as_posix(),
        "demo-feature",
        {"feature": True, "project": False, "global": False},
    )

    prompt = build_prompt(
        {"agent_map": {"BUILDING": "team/build"}, "composition": {}},
        "BUILDING",
        storage,
    )

    assert 'board "feature" + scope "demo-feature"' in prompt
    assert 'board "project"' not in prompt
    assert 'board "global"' not in prompt


def test_empty_result_is_documented_as_an_answer():
    """`[]` is a real 'nothing here', not a failure — the agent must not loop on it."""
    body = compose_skill("team/build", "claude")
    body = body[body.index(_HEADING) :]
    assert "never padded" in body
