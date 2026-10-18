"""A goal's FSM run (`executor: team` / `loop`) takes its cost cap from `goal.max_cost_usd`.

`goal_executor._run_team` called `start_run` without `max_cost_usd`, so every goal run got
`start_run`'s default of $1 and parked as `cap_exceeded` after its first dollar, while the
drain inside the same run read `goal.max_cost_usd`. The run now passes the same setting: one
number caps a goal at both levels, and an unset setting means no cap at either (the setting's
documented fail-open contract), not a hidden $1.
"""

from __future__ import annotations

import time
import types
from unittest.mock import patch

import pytest


def _set_cap(value) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "goal.max_cost_usd", "" if value is None else str(value))


def _goal(scope: str, executor: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    goal_id = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text="Ship it",
    )
    conn.execute("UPDATE comms_messages SET executor=? WHERE id=?", (executor, goal_id))
    conn.commit()
    return goal_id


def _start_kwargs(tmp_path, executor: str) -> dict:
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    captured: dict = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="r1")

    result = start_goal_run(
        _goal(f"cap-{executor}", executor),
        project_root=str(tmp_path),
        start_fn=fake_start,
        block=True,
    )
    assert result["ok"], result
    return captured


@pytest.mark.parametrize("executor", ["team", "loop"])
def test_a_goal_run_takes_its_cap_from_the_goal_setting(tmp_path, executor):
    _set_cap(2.5)
    assert _start_kwargs(tmp_path, executor)["max_cost_usd"] == 2.5


@pytest.mark.parametrize("executor", ["team", "loop"])
def test_an_unconfigured_goal_run_has_no_cap_rather_than_one_dollar(tmp_path, executor):
    kwargs = _start_kwargs(tmp_path, executor)
    assert "max_cost_usd" in kwargs, "without it start_run's $1 default applies"
    assert kwargs["max_cost_usd"] is None


def test_an_uncapped_run_is_not_stopped_by_its_cost(tmp_path):
    """`max_cost_usd=None` reaches the loop as "no cap": two $50 stages run to done."""
    from pathly_orchestrator.supervisor import _lock, _registry, start_run

    topic = "uncapped-goal-run"
    with _lock:
        _registry.pop(topic, None)
    stages: list = []

    def fake_stage(*args, **kwargs):
        stages.append(1)
        return {"cost_usd": 50.0, "session_id": None}

    with (
        patch(
            "pathly_orchestrator.fsm_http_client.next_action",
            side_effect=[
                {"current_state": s, "agent": "builder", "instructions": "x"}
                for s in ("BUILDING", "REVIEWING")
            ],
        ),
        patch(
            "pathly_orchestrator.fsm_http_client.complete_stage",
            side_effect=[{"next_state": "REVIEWING"}, {"done": True}],
        ),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            side_effect=fake_stage,
        ),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_cost_usd=None,
            interactive=False,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted", "parked"}:
            assert time.monotonic() < deadline, state.status
            time.sleep(0.05)

    assert (state.status, state.error_kind) == ("done", None)
    assert len(stages) == 2 and state.cost_usd_so_far == 100.0
    with _lock:
        _registry.pop(topic, None)
