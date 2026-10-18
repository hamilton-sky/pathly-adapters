"""A feedback spawn's cost counts toward the run, as a stage spawn's does.

`orchestrator_stage._resolve_stage_supervised` threw away the result of the feedback spawn,
so a builder fix round (BUILD_FAILURES, TEST_FAILURES, ...) cost money the run never saw:
`state.cost_usd_so_far` held only the stage spawns, and the cost cap could not stop a run
whose spend was in its fix rounds.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from pathly_orchestrator.supervisor import _lock, _registry, start_run

_NEXT_ACTION = "pathly_orchestrator.fsm_http_client.next_action"
_COMPLETE_STAGE = "pathly_orchestrator.fsm_http_client.complete_stage"
_RUN_STAGE = "pathly_orchestrator.supervisor._run_stage_via_terminal"


def _na(state: str) -> dict:
    return {"current_state": state, "agent": "builder", "instructions": "do it"}


def _blocked(file_: str = "BUILD_FAILURES.md") -> dict:
    return {
        "blocked": True,
        "target_agent": "builder",
        "file": file_,
        "instructions": "fix the build",
    }


def _run(tmp_path, topic, next_actions, completes, costs, max_cost_usd=100.0):
    with _lock:
        _registry.pop(topic, None)
    spawned: list = []

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        spawned.append(run_id)
        return {"cost_usd": costs[len(spawned) - 1], "session_id": None}

    with (
        patch(_NEXT_ACTION, side_effect=next_actions),
        patch(_COMPLETE_STAGE, side_effect=completes),
        patch(_RUN_STAGE, side_effect=fake_spawn),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_cost_usd=max_cost_usd,
            interactive=False,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted", "parked"}:
            assert time.monotonic() < deadline, state.status
            time.sleep(0.05)
    with _lock:
        _registry.pop(topic, None)
    return state, spawned


def test_feedback_rounds_add_their_cost_to_the_run(tmp_path):
    state, spawned = _run(
        tmp_path,
        "fb-cost-counted",
        [_na("BUILDING")],
        [_blocked(), _blocked(), {"done": True}],
        costs=[1.0, 0.25, 0.5],
    )

    assert state.status == "done"
    assert len(spawned) == 3 and sum("-fb" in r for r in spawned) == 2
    assert state.cost_usd_so_far == 1.75


def test_the_cost_cap_sees_a_fix_round_and_stops_the_next_stage(tmp_path):
    """The stage costs $1 and its fix round $3: with a $2 cap the next stage never spawns."""
    state, spawned = _run(
        tmp_path,
        "fb-cost-capped",
        [_na("BUILDING"), _na("REVIEWING")],
        [_blocked(), {"next_state": "REVIEWING"}, {"done": True}],
        costs=[1.0, 3.0, 1.0],
        max_cost_usd=2.0,
    )

    assert (state.status, state.error_kind) == ("error", "cap_exceeded")
    assert len(spawned) == 2
    assert state.cost_usd_so_far == 4.0
