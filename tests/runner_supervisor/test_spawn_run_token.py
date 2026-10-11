"""run-token: every spawn mints a token in the TERMINAL_SPAWN payload, revoked at settle."""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_tokens import resolve_run_token
from pathly_orchestrator.supervisor.state import RunnerState
from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal


def _state(tmp_path: Path, **kw) -> RunnerState:
    storage = tmp_path / "pathly" / "features" / "feat-x"
    storage.mkdir(parents=True, exist_ok=True)
    args: dict = dict(
        topic="feat-x",
        flow="team",
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=60,
    )
    args.update(kw)
    state = RunnerState(**args)
    state.storage_path = str(storage)
    return state


def _spawn(state: RunnerState, run_id: str) -> dict:
    """Run one spawn; capture the TERMINAL_SPAWN payload, then abort the spawn."""
    seen: list[dict] = []

    def _bc(topic, payload):
        if payload.get("type") == "TERMINAL_SPAWN":
            seen.append(payload)
            raise RuntimeError("stop after spawn")

    with pytest.raises(RuntimeError):
        _run_stage_via_terminal(state, "do it", "claude", "m", run_id, _bc)
    assert seen, "no TERMINAL_SPAWN was broadcast"
    return seen[0]


def test_fsm_stage_token_resolves_to_run_and_role(tmp_path: Path) -> None:
    state = _state(tmp_path, current_state="BUILDING", agent_role="builder")
    seen: list[dict] = []

    def _bc(topic, payload):
        if payload.get("type") == "TERMINAL_SPAWN":
            seen.append(payload)
            # token is live while the spawn is in flight
            row = resolve_run_token(get_db(), payload["run_token"])
            assert row["run_id"] == "run-tok-1"
            assert row["role"] == "builder"
            raise RuntimeError("stop")

    with pytest.raises(RuntimeError):
        _run_stage_via_terminal(state, "x", "claude", "m", "run-tok-1", _bc)
    assert seen[0]["run_token"]


def test_board_run_token_resolves_to_agent_and_scope(tmp_path: Path) -> None:
    state = _state(
        tmp_path,
        flow="board-run",
        current_state="planner",
        board_scope="feat-x",
    )
    seen: list[dict] = []

    def _bc(topic, payload):
        if payload.get("type") == "TERMINAL_SPAWN":
            seen.append(resolve_run_token(get_db(), payload["run_token"]))
            raise RuntimeError("stop")

    with pytest.raises(RuntimeError):
        _run_stage_via_terminal(state, "x", "claude", "m", "run-tok-2", _bc)
    row = seen[0]
    assert row["role"] == "planner"
    assert row["scope"] == "feat-x"
    assert row["run_id"] == "run-tok-2"


def test_token_is_revoked_after_settle(tmp_path: Path) -> None:
    state = _state(tmp_path, current_state="BUILDING", agent_role="builder")
    payload = _spawn(state, "run-tok-3")
    assert payload["run_token"]
    assert resolve_run_token(get_db(), payload["run_token"]) is None


def test_mint_error_leaves_none_and_spawn_goes_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "pathly_orchestrator.db.queries.run_tokens.mint_run_token", _boom
    )
    state = _state(tmp_path, current_state="BUILDING", agent_role="builder")
    payload = _spawn(state, "run-tok-4")
    assert payload["run_token"] is None
