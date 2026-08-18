"""Run-identity bookkeeping for a spawn.

One identity row per spawn (FSM stages, loop tasks and board runs all pass through the same
path with their own run_id), opened before the PTY starts and settled in the spawn's ``finally``.
Kept separate from the spawn itself so a change to how a run is IDENTIFIED cannot disturb how it
is EXECUTED.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .state import RunnerState, logger


def _record_spawn_identity(
    state: RunnerState, run_id: str, adapter: str
) -> Optional[tuple]:
    """run-identity: issue this spawn's identity row up front — run_id → (project_root,
    feature SLUG, board_scope) — at the ONE chokepoint every runner/board/goal spawn
    flows through, so telemetry consumers join by run_id instead of re-deriving identity
    from storage location. Returns (slug, board_scope) for _settle_spawn_identity, or
    None when the write was skipped. Best-effort; never blocks a spawn.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.run_history import upsert_run
        from pathly_orchestrator.fsm_ops import _resolve_storage_path

        storage = (
            Path(state.storage_path)
            if state.storage_path
            else _resolve_storage_path(None, state.project_root, state.topic)
        )
        slug = storage.name
        scope = _run_board_scope(state, storage)
        upsert_run(
            get_db(),
            state.project_root,
            slug,
            run_id,
            "running",
            adapter=adapter or None,
            board_scope=scope or None,
        )
        return (slug, scope)
    except Exception:
        logger.debug("_record_spawn_identity skipped", exc_info=True)
        return None


def _settle_spawn_identity(
    state: RunnerState, run_id: str, identity: Optional[tuple]
) -> None:
    """Settle the spawn's identity row when the spawn ends: done, or error when the
    stage is unwinding an exception (read via sys.exc_info() — this runs inside the
    caller's finally). Identity fields COALESCE in upsert_run, so this never
    overwrites the issued board_scope. Best-effort.
    """
    if not identity:
        return
    try:
        import sys as _sys
        import time as _time

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.run_history import upsert_run

        slug, scope = identity
        status = "error" if _sys.exc_info()[0] else "done"
        upsert_run(
            get_db(),
            state.project_root,
            slug,
            run_id,
            status,
            finished_at=_time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            board_scope=scope or None,
        )
    except Exception:
        logger.debug("_settle_spawn_identity skipped", exc_info=True)


def _run_board_scope(state: RunnerState, storage: Optional[Path]) -> str:
    """The board scope for THIS run's telemetry stamps (run-identity).

    Prefer the identity ISSUED at spawn (state.board_scope — the board/loop executors
    set it); fall back to deriving it exactly as build_prompt does (plain feature →
    the storage-dir basename; 'project' → normalized project_root; goal runs → the
    goal's parent board scope). Best-effort: '' when nothing resolves (stored as NULL).
    """
    if getattr(state, "board_scope", ""):
        return state.board_scope
    try:
        from pathly_orchestrator.fsm_compose import resolve_board_scope

        feature = storage.name if storage is not None else (state.topic or "")
        return resolve_board_scope(feature, state.project_root, state.goal_id or "")
    except Exception:
        return ""


def _record_spawn_prompt(state: RunnerState, run_id: str, instructions: str) -> None:
    """Persist this spawn's prompt for the Complete Run Record (unified-control-plane P0).

    Best-effort — MUST NOT raise into the spawn path (this is what keeps the P0
    "pure-additive, zero-behavior-change" claim true; mirrors the _record_spawn_identity
    guard). The injected board context is embedded in ``instructions`` in P0
    (board_context_injected becomes discrete in P1 — see ARCHITECTURE §2.3).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _rl_db
        from pathly_orchestrator.db.queries.run_log import write_run_log_spawn

        write_run_log_spawn(
            _rl_db(),
            run_id,
            stage=state.current_state or state.status or "stage",
            prompt_sent=instructions,
            board_context_injected=None,
            stdin=None,
        )
    except Exception:
        logger.debug("run_log spawn write skipped", exc_info=True)
