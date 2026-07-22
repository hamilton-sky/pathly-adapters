"""run-identity: server-side run_id + board_scope stamping (supervisor guarantee).

The spawner knows both identities at spawn, so the supervisor paths that synthesize
or patch events stamp them when the agent omitted them — COALESCE-style, never
overwriting an agent-provided value (SPEC Risks #4).
"""

from __future__ import annotations

from pathlib import Path

from pathly_orchestrator.supervisor.state import RunnerState
from pathly_orchestrator.supervisor.terminal import (
    _run_board_scope,
    _synthesize_agent_done_if_missing,
)


def _executor_state(tmp_path: Path, **overrides) -> RunnerState:
    """A minimal executor-owned RunnerState with a real storage dir under tmp_path."""
    storage = tmp_path / "pathly" / "features" / "feat-x"
    storage.mkdir(parents=True, exist_ok=True)
    kwargs: dict = dict(
        topic="feat-x",
        flow="board-run",
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=60,
        run_id="run-ident-1",
        current_state="planner",
    )
    kwargs.update(overrides)
    state = RunnerState(**kwargs)
    state.executor_owned_telemetry = True
    state.storage_path = str(storage)
    return state


def _last_event(storage: Path) -> dict | None:
    from pathly_orchestrator.runner import read_last_agent_done

    return read_last_agent_done(storage)


def test_synthesize_stamps_run_id_and_board_scope(tmp_path: Path) -> None:
    """A run whose agent self-reported NO AGENT_DONE yields a synthetic row carrying
    run_id AND board_scope (both issued at spawn)."""
    state = _executor_state(tmp_path, board_scope="parent-feat")
    _synthesize_agent_done_if_missing(
        state,
        "run-ident-1",
        "claude-sonnet-4-6",
        {"result": {"summary": "did work", "tokens_in": 5, "tokens_out": 7}},
    )
    last = _last_event(Path(state.storage_path))
    assert last is not None, "no synthetic AGENT_DONE was written"
    assert last.get("synthetic") is True
    assert last.get("run_id") == "run-ident-1"
    assert last.get("board_scope") == "parent-feat"
    # the fsm_events column is stamped too (board-scope-column extraction)
    from pathly_orchestrator.db import get_db

    row = (
        get_db()
        .execute(
            "SELECT board_scope FROM fsm_events WHERE feature='feat-x' "
            "AND event_type='AGENT_DONE' ORDER BY seq DESC LIMIT 1"
        )
        .fetchone()
    )
    assert row["board_scope"] == "parent-feat"


def test_synthesize_never_overwrites_agent_provided(tmp_path: Path) -> None:
    """When the agent self-reported (same run_id), the synthesis does nothing — an
    agent-provided board_scope survives untouched (never-overwrite direction)."""
    from pathly_orchestrator import eventlog

    state = _executor_state(tmp_path, board_scope="server-derived")
    eventlog.append_event(
        state.storage_path,
        {
            "type": "AGENT_DONE",
            "agent": "planner",
            "run_id": "run-ident-1",
            "board_scope": "agent-chose",
            "summary": "self-reported",
            "ts": "2026-07-22T00:00:00Z",
        },
    )
    _synthesize_agent_done_if_missing(
        state, "run-ident-1", "claude-sonnet-4-6", {"result": {"summary": "pty"}}
    )
    last = _last_event(Path(state.storage_path))
    assert last is not None
    assert last.get("board_scope") == "agent-chose"
    assert last.get("summary") == "self-reported"
    assert not last.get("synthetic")


def test_synthesize_fills_when_agent_omitted_board_scope(tmp_path: Path) -> None:
    """The other direction: agent wrote nothing → the server fills BOTH identities."""
    state = _executor_state(tmp_path, board_scope="")  # not issued → derived fallback
    _synthesize_agent_done_if_missing(state, "run-ident-1", "m", {"result": {}})
    last = _last_event(Path(state.storage_path))
    assert last is not None
    assert last.get("synthetic") is True
    # fallback derivation: plain feature run → the storage-dir basename
    assert last.get("board_scope") == "feat-x"


def test_patch_last_agent_done_billing_carries_board_scope(tmp_path: Path) -> None:
    """The BILLING_UPDATE carries board_scope so the projection can stamp it."""
    from pathly_orchestrator.db import get_db, read_events
    from pathly_orchestrator.runner import _patch_last_agent_done

    storage = tmp_path / "pathly" / "features" / "feat-bill"
    storage.mkdir(parents=True, exist_ok=True)
    _patch_last_agent_done(
        storage,
        1.25,
        100,
        50,
        9,
        3,
        model="claude-sonnet-4-6",
        run_id="run-bill-1",
        board_scope="parent-feat",
    )
    events = read_events(get_db(), str(tmp_path), "feat-bill")
    billing = [e for e in events if e.get("type") == "BILLING_UPDATE"]
    assert billing, "no BILLING_UPDATE written"
    assert billing[-1].get("board_scope") == "parent-feat"
    assert billing[-1].get("run_id") == "run-bill-1"


def test_run_board_scope_prefers_issued_over_derived(tmp_path: Path) -> None:
    """Spawn-issued identity wins; derivation is only the fallback."""
    storage = tmp_path / "pathly" / "features" / "feat-y"
    storage.mkdir(parents=True, exist_ok=True)

    issued = _executor_state(tmp_path, board_scope="issued-scope")
    assert _run_board_scope(issued, storage) == "issued-scope"

    derived = _executor_state(tmp_path, board_scope="")
    assert _run_board_scope(derived, storage) == "feat-y"


def test_run_board_scope_project_storage_normalizes_root(tmp_path: Path) -> None:
    """'project' storage basename derives the normalized project_root (build_prompt parity)."""
    storage = tmp_path / "pathly" / "project"
    storage.mkdir(parents=True, exist_ok=True)
    state = _executor_state(tmp_path, board_scope="")
    expected = str(tmp_path).replace("\\", "/").rstrip("/")
    assert _run_board_scope(state, storage) == expected
