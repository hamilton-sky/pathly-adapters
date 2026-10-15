"""supervisor/run_budget.py — a goal run's iteration cap follows its DAG (build-proof 12).

``refresh(state)`` raises ``state.max_iterations`` to
``tasks x goal.task_max_attempts x (MAX_FEEDBACK_ROUNDS + 1)`` when that is larger, never lowers
it, never raises, and leaves a run without a ``goal_id`` alone. The DAG is real rows in the
per-test DB; ``_resolve_stage_supervised`` is the wiring (it runs after every stage).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms_messages import (
    post_message,
    soft_delete_message,
)
from pathly_orchestrator.supervisor import run_budget
from pathly_orchestrator.supervisor.state import RunnerState


def _state(
    goal_id: str = "goal-1", max_iterations: int = 10, root: str = "/nonexistent"
) -> RunnerState:
    return RunnerState(
        topic="budget-demo",
        flow="team-build",
        project_root=root,
        model="claude-sonnet-4-6",
        timeout=600,
        goal_id=goal_id,
        max_iterations=max_iterations,
    )


def _add_tasks(count: int, goal_id: str = "goal-1") -> list[str]:
    conn = get_db()
    return [
        post_message(
            conn,
            board="feature",
            scope="budget-demo",
            from_agent="planner",
            type="task",
            text=f"task {i}",
            goal_id=goal_id,
        )
        for i in range(count)
    ]


def test_five_tasks_and_three_attempts_give_sixty():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(5)
    state = _state()

    run_budget.refresh(state)

    assert state.max_iterations == 5 * 3 * (3 + 1) == 60


def test_the_attempts_setting_is_read_each_time():
    set_setting(get_db(), "goal.task_max_attempts", "5")
    _add_tasks(2)
    state = _state()

    run_budget.refresh(state)

    assert state.max_iterations == 2 * 5 * 4 == 40


def test_an_unset_attempts_setting_uses_the_default_of_three():
    _add_tasks(1)
    state = _state()

    run_budget.refresh(state)

    assert state.max_iterations == 12


def test_a_goal_with_no_tasks_yet_keeps_ten():
    state = _state()

    run_budget.refresh(state)

    assert state.max_iterations == 10


def test_a_goal_with_one_task_gives_twelve():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(1)
    state = _state()

    run_budget.refresh(state)

    assert state.max_iterations == 12


def test_a_larger_caller_cap_is_kept():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(5)
    state = _state(max_iterations=100)

    run_budget.refresh(state)

    assert state.max_iterations == 100


def test_adding_tasks_between_calls_raises_the_cap():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    state = _state()
    _add_tasks(2)
    run_budget.refresh(state)
    assert state.max_iterations == 24

    _add_tasks(3)
    run_budget.refresh(state)

    assert state.max_iterations == 60


def test_deleting_tasks_never_lowers_the_cap():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    state = _state()
    ids = _add_tasks(5)
    run_budget.refresh(state)
    assert state.max_iterations == 60

    for message_id in ids[:3]:
        assert soft_delete_message(get_db(), message_id, force=True) == "deleted"
    run_budget.refresh(state)

    assert state.max_iterations == 60


def test_a_run_without_a_goal_is_untouched():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(5)
    state = _state(goal_id="")

    run_budget.refresh(state)

    assert state.max_iterations == 10


def test_another_goals_tasks_do_not_count():
    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(5, goal_id="goal-2")
    state = _state(goal_id="goal-1")

    run_budget.refresh(state)

    assert state.max_iterations == 10


def test_it_logs_when_it_raises_the_cap_and_is_quiet_otherwise(caplog):
    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(5)
    state = _state()

    with caplog.at_level(logging.INFO, logger="pathly.supervisor"):
        run_budget.refresh(state)
    assert "60" in caplog.text and "max_iterations" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="pathly.supervisor"):
        run_budget.refresh(state)
    assert "max_iterations" not in caplog.text


def test_it_never_raises_and_leaves_the_cap_when_the_db_fails():
    state = _state(max_iterations=10)

    with patch(
        "pathly_orchestrator.db.queries.comms_tasks.count_tasks_for_goal",
        side_effect=RuntimeError("db is gone"),
    ):
        run_budget.refresh(state)

    assert state.max_iterations == 10


def test_it_never_raises_when_the_attempts_setting_cannot_be_read():
    _add_tasks(5)
    state = _state()

    with patch(
        "pathly_orchestrator.supervisor.task_retry.resolve_max_attempts",
        side_effect=RuntimeError("settings are gone"),
    ):
        run_budget.refresh(state)

    assert state.max_iterations == 10


# ── Wiring: _resolve_stage_supervised runs after every stage ───────────────────────


def test_resolve_stage_supervised_refreshes_the_budget_first(tmp_path):
    from pathly_orchestrator.supervisor.orchestrator_stage import (
        _resolve_stage_supervised,
    )

    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(5)
    state = _state(root=str(tmp_path))
    fhc = SimpleNamespace(complete_stage=lambda payload: {"done": True})

    result = _resolve_stage_supervised(
        state, "team-build", "budget-demo", str(tmp_path), "m", None, fhc
    )

    assert result == {"done": True}
    assert state.max_iterations == 60


def test_the_budget_is_raised_even_when_the_stage_is_then_blocked_on_a_human(tmp_path):
    from pathly_orchestrator.supervisor.orchestrator_stage import (
        _resolve_stage_supervised,
    )

    set_setting(get_db(), "goal.task_max_attempts", "3")
    _add_tasks(2)
    state = _state(root=str(tmp_path))
    fhc = SimpleNamespace(
        complete_stage=lambda payload: {
            "blocked": True,
            "target_agent": "human",
            "file": "HUMAN_QUESTIONS.md",
        }
    )

    result = _resolve_stage_supervised(
        state, "team-build", "budget-demo", str(tmp_path), "m", None, fhc
    )

    assert result is None
    assert state.status == "parked"
    assert state.max_iterations == 24
