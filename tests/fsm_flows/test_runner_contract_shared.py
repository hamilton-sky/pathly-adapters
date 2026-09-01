"""One runner contract, two prompt paths — fsm-fan-out Phase A.

``build_prompt`` has always appended a "### Runner contract — the supervisor owns the FSM"
block; the DAG-task path in ``supervisor/scheduler.py`` appended nothing, so a loop-executor
task agent was the one headless agent never told the supervisor drives the flow. Under FSM
fan-out those agents run INSIDE an FSM stage, where a self-driven transition is a
double-advance or a 404 respawn loop — the exact failure ``test_runner_contract.py`` pins for
the FSM path.

Both paths now share ``fsm_compose.RUNNER_CONTRACT_BLOCK``. These tests assert the block is
present in each, and present EXACTLY ONCE (a second copy would be the obvious way this
regresses — appending it in the scheduler *and* in ``compose_skill``'s fragment layer).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.fsm_compose import RUNNER_CONTRACT_BLOCK

_HEADING = "### Runner contract — the supervisor owns the FSM"


class _FakeState:
    """Minimal stand-in for RunnerState (mirrors tests/dag_goals/test_dag_scheduler.py)."""

    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "claude-sonnet-4-6"


def _make_task(conn, scope: str, text: str) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn, board="feature", scope=scope, from_agent="builder", type="task", text=text
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', lane=? WHERE id=?",
        ("main", mid),
    )
    conn.commit()
    return mid


def _scheduler_task_prompt(scope: str) -> str:
    """Drain a one-task DAG through the REAL scheduler_loop, returning the composed prompt."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    _make_task(get_db(), scope, "implement the widget")
    captured: dict[str, str] = {}

    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        captured["instructions"] = instructions
        return {"ok": True}

    scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=_spawn,
    )
    assert "instructions" in captured, "scheduler never spawned the task"
    return captured["instructions"]


def test_constant_is_a_plain_constant():
    """It interpolates nothing — that is what makes sharing it a constant, not a builder."""
    assert _HEADING in RUNNER_CONTRACT_BLOCK
    assert "{" not in RUNNER_CONTRACT_BLOCK and "}" not in RUNNER_CONTRACT_BLOCK


def test_fsm_stage_prompt_carries_the_contract_exactly_once(tmp_path):
    """The FSM path's behaviour is unchanged — same block, still exactly one copy."""
    from pathly_orchestrator.fsm_compose import build_prompt
    from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path

    flow_cfg = _load_flow("team", str(tmp_path))
    storage = Path(str(_resolve_storage_path(flow_cfg, str(tmp_path), "feat")))
    storage.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(flow_cfg, "BUILDING", storage)

    assert RUNNER_CONTRACT_BLOCK in prompt
    assert prompt.count(_HEADING) == 1


def test_dag_task_prompt_carries_the_contract_exactly_once():
    """The gap Phase A closes: a scheduler task prompt now carries the identical block."""
    prompt = _scheduler_task_prompt("contract-dag")

    assert RUNNER_CONTRACT_BLOCK in prompt
    assert prompt.count(_HEADING) == 1


def test_dag_task_prompt_keeps_the_contract_when_composition_fails(monkeypatch):
    """The contract survives the raw-task-text fallback.

    ``_worker`` falls back to the bare task text when ``compose_skill`` raises. The contract
    is appended AFTER that try/except precisely so the fallback — the path where the agent
    has the least guidance — is not the one path that loses it.
    """
    import pathly_orchestrator.skills.compose as _compose

    def _boom(*a, **k):
        raise RuntimeError("composition unavailable")

    monkeypatch.setattr(_compose, "compose_skill", _boom)
    prompt = _scheduler_task_prompt("contract-dag-fallback")

    assert RUNNER_CONTRACT_BLOCK in prompt
    assert prompt.count(_HEADING) == 1


@pytest.mark.parametrize(
    "forbidden",
    ["pathly-fsm-call", "complete-stage", "/complete_stage", "/next_action"],
)
def test_both_paths_name_the_same_forbidden_moves(tmp_path, forbidden):
    """The contract is shared TEXT, not two paraphrases that can drift apart."""
    assert forbidden in RUNNER_CONTRACT_BLOCK
    assert forbidden in _scheduler_task_prompt(
        f"contract-shared-{forbidden.strip('/-')}"
    )
