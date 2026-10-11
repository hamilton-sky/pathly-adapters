"""A spawn mints a run token, sends it in TERMINAL_SPAWN, and revokes it when the spawn ends."""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.supervisor.registry import get_run
from pathly_orchestrator.supervisor.state import RunnerState
from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal


def _state(tmp_path: Path, **overrides) -> RunnerState:
    storage = tmp_path / "pathly" / "features" / "feat-tok"
    storage.mkdir(parents=True, exist_ok=True)
    kwargs: dict = dict(
        topic="feat-tok",
        flow="team",
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=60,
        run_id="parent-1",
        current_state="BUILDING",
    )
    kwargs.update(overrides)
    state = RunnerState(**kwargs)
    state.storage_path = str(storage)
    return state


def _spawn(state: RunnerState, run_id: str) -> tuple[dict, dict | None]:
    """Run one spawn to completion. Returns (TERMINAL_SPAWN payload, token row seen mid-spawn)."""
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    seen: dict = {}

    def broadcast(_topic, payload):
        if payload.get("type") != "TERMINAL_SPAWN":
            return
        seen["payload"] = payload
        seen["row"] = resolve_run_token(get_db(), payload.get("run_token"))
        run = get_run(run_id)
        assert run is not None
        run.mark_started()
        run.mark_pty_result({"result": {}, "exit_code": 0})

    _run_stage_via_terminal(state, "do the work", "claude", "m", run_id, broadcast)
    return seen["payload"], seen["row"]


def test_fsm_stage_token_resolves_to_run_and_stage_role(tmp_path: Path) -> None:
    from pathly_orchestrator.db import get_db
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    payload, row = _spawn(_state(tmp_path), "feat-tok-1-100")
    assert row is not None
    assert row["run_id"] == "feat-tok-1-100"
    assert row["role"] == "builder"
    # settled: the token no longer resolves
    assert resolve_run_token(get_db(), payload["run_token"]) is None


def test_board_run_token_resolves_to_board_role_and_scope(tmp_path: Path) -> None:
    state = _state(
        tmp_path,
        flow="board-run",
        current_state="planner",
        board_scope="scope-x",
    )
    state.scope_tier = "project"
    payload, row = _spawn(state, "board-run-1")
    assert row is not None
    assert row["run_id"] == "board-run-1"
    assert row["role"] == "planner"
    assert (row["board"], row["scope"]) == ("project", "scope-x")


def test_loop_task_token_role_is_builder(tmp_path: Path) -> None:
    state = _state(tmp_path, flow="goal-loop", current_state="DRAINING")
    _, row = _spawn(state, "sched-task1#1")
    assert row is not None
    assert row["role"] == "builder"


def test_token_revoked_when_spawn_setup_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathly_orchestrator.db import get_db

    minted: list[str] = []
    from pathly_orchestrator.db.queries import run_tokens

    real_mint = run_tokens.mint_run_token

    def spy(*args, **kwargs):
        token = real_mint(*args, **kwargs)
        minted.append(token)
        return token

    monkeypatch.setattr(run_tokens, "mint_run_token", spy)

    def broadcast(_topic, payload):
        raise RuntimeError("broadcast exploded")

    with pytest.raises(RuntimeError):
        _run_stage_via_terminal(
            _state(tmp_path), "x", "claude", "m", "feat-tok-2-200", broadcast
        )
    assert len(minted) == 1
    assert run_tokens.resolve_run_token(get_db(), minted[0]) is None


def test_mint_error_leaves_token_none_and_spawn_still_goes_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathly_orchestrator.db.queries import run_tokens

    def boom(*_a, **_k):
        raise RuntimeError("db is down")

    monkeypatch.setattr(run_tokens, "mint_run_token", boom)
    payload, row = _spawn(_state(tmp_path), "feat-tok-3-300")
    assert payload["run_token"] is None
    assert row is None
