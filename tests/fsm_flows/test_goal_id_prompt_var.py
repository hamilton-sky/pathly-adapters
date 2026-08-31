"""Phase 0 hygiene fix — team/build's board query was unscoped by goal_id.

The FSM gates that surround team/build's own board poll (on_board_count,
require_tasks_done) are already goal-scoped via RunnerState.goal_id — but the skill's
own `GET /comms/tasks?ready=true` call had no goal_id param, so a goal-executor run
could claim a ready task belonging to a DIFFERENT goal on the same feature board.
build_prompt now substitutes a real `<goal_id>` placeholder (mirroring <feature>,
<board>, ...) so the skill's own query stays in lockstep with the gates around it.
"""

from __future__ import annotations

from pathlib import Path

FLOW_CONFIG = {
    "agent_map": {"BUILDING": "quick"},
    "composition": {},
}


def _storage(tmp_path: Path, feature: str = "test-feature") -> Path:
    p = tmp_path / "pathly" / "features" / feature
    p.mkdir(parents=True, exist_ok=True)
    return p


def test_build_prompt_substitutes_goal_id(tmp_path, monkeypatch):
    import pathly_orchestrator.fsm_compose as fsm_compose

    monkeypatch.setattr(
        fsm_compose, "_load_agent_text", lambda *_: "query: goal_id=<goal_id>"
    )
    storage_path = _storage(tmp_path)

    prompt = fsm_compose.build_prompt(
        FLOW_CONFIG, "BUILDING", storage_path, goal_id="goal-123"
    )

    assert "goal_id=goal-123" in prompt
    assert "<goal_id>" not in prompt


def test_build_prompt_goal_id_empty_for_non_goal_run(tmp_path, monkeypatch):
    """A plain feature/project run (no goal_id) renders an empty value, not the
    literal placeholder — /comms/tasks treats `goal_id=` the same as omitted."""
    import pathly_orchestrator.fsm_compose as fsm_compose

    monkeypatch.setattr(
        fsm_compose, "_load_agent_text", lambda *_: "query: goal_id=<goal_id>"
    )
    storage_path = _storage(tmp_path)

    prompt = fsm_compose.build_prompt(FLOW_CONFIG, "BUILDING", storage_path)

    assert "goal_id=<goal_id>" not in prompt
    assert "query: goal_id=" in prompt


def test_team_build_skill_board_query_is_goal_scoped():
    """Regression guard on the actual skill file: the board-task poll must carry
    goal_id, matching the goal-scoped gates (on_board_count, require_tasks_done)
    that already surround BUILDING in team-build.flow.yaml."""
    import pathly_data

    skill_path = (
        Path(pathly_data.__file__).parent / "core" / "skills" / "team" / "build.md"
    )
    text = skill_path.read_text(encoding="utf-8")
    assert "ready=true" in text
    assert "goal_id=<goal_id>" in text
