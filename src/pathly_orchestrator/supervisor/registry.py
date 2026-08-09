"""Registry: shared in-memory state, signal dicts, and registry helpers."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .state import RunnerState, logger

_registry: dict[str, RunnerState] = {}
_lock = threading.Lock()
_TERMINAL_RESULT_TIMEOUT = 1800


@dataclass
class TerminalRun:
    """All lifecycle state for one PTY stage execution, guarded by one Condition.

    Replaces five separate signal dicts (_terminal_started_events,
    _terminal_result_events, _terminal_result_data, _agent_done_events,
    _agent_done_stop_events). One object, one lock, all transitions visible.
    """

    run_id: str
    started: bool = False
    pty_result: dict | None = None
    agent_done: bool = False
    stop_watcher: bool = False
    _cond: threading.Condition = field(default_factory=threading.Condition)

    def mark_started(self) -> None:
        with self._cond:
            self.started = True
            self._cond.notify_all()

    def mark_pty_result(self, data: dict) -> None:
        with self._cond:
            self.pty_result = data
            self._cond.notify_all()

    def mark_agent_done(self) -> None:
        with self._cond:
            self.agent_done = True
            self._cond.notify_all()

    def request_stop_watcher(self) -> None:
        with self._cond:
            self.stop_watcher = True
            self._cond.notify_all()

    def wait_started(self, timeout: float) -> bool:
        with self._cond:
            return self._cond.wait_for(lambda: self.started, timeout=timeout)

    def wait_pty_result(self, timeout: float) -> bool:
        with self._cond:
            return self._cond.wait_for(
                lambda: self.pty_result is not None, timeout=timeout
            )

    def wait_result_or_agent_done(self, timeout: float) -> str:
        """Returns 'agent_done', 'pty_result', or 'timeout'."""
        with self._cond:
            fired = self._cond.wait_for(
                lambda: self.pty_result is not None or self.agent_done,
                timeout=timeout,
            )
            if not fired:
                return "timeout"
            if self.agent_done and self.pty_result is None:
                return "agent_done"
            return "pty_result"

    def wait_watcher_stop_signal(self, timeout: float) -> bool:
        """Used by the watcher thread: sleep until stop is requested or timeout elapses."""
        with self._cond:
            return self._cond.wait_for(lambda: self.stop_watcher, timeout=timeout)


_runs: dict[str, TerminalRun] = {}
_runs_lock = threading.Lock()


def create_run(run_id: str) -> TerminalRun:
    run = TerminalRun(run_id=run_id)
    with _runs_lock:
        _runs[run_id] = run
    return run


def get_run(run_id: str) -> Optional[TerminalRun]:
    with _runs_lock:
        return _runs.get(run_id)


def drop_run(run_id: str) -> None:
    with _runs_lock:
        _runs.pop(run_id, None)


def get_state(topic: str) -> Optional[RunnerState]:
    with _lock:
        return _registry.get(topic)


def recover_stale_mirrors(project_root: str) -> None:
    """On server startup, mark any runner_state rows left as 'running' → 'error'.

    Uses the central ~/.pathly/pathly.db to call mark_stale_runners().
    Falls back to rewriting RUNNER_STATE.json for feature dirs that have no SQLite entry.
    """
    from pathly_orchestrator import db as _db

    pathly_root = Path(project_root) / "pathly"
    # Feature homes under the flat layout (pathly/features/) AND the legacy base (pathly/plans/).
    bases = [pathly_root / "features", pathly_root / "plans"]
    if not any(b.is_dir() for b in bases):
        return

    handled: set = set()
    try:
        conn = _db.get_db()
        count = _db.mark_stale_runners(conn)
        if count:
            logger.info("Marked %d stale runner(s) in central DB → error", count)
    except Exception as exc:
        logger.warning("recover_stale_mirrors: SQLite mark failed: %s", exc)

    for base in bases:
        if not base.is_dir():
            continue
        for mirror in base.glob("*/RUNNER_STATE.json"):
            if mirror.parent in handled:
                continue
            try:
                data = json.loads(mirror.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("status") == "running":
                data["status"] = "error"
                data["error_kind"] = "stale_restart"
                mirror.write_text(json.dumps(data, indent=2), encoding="utf-8")
                logger.info(
                    "Rewrote stale mirror for topic %s → error", data.get("topic")
                )


def _write_mirror(state: RunnerState) -> None:
    try:
        from pathly_orchestrator import db as _db

        # runner_state is DB-backed (write_runner_state → SQLite) — there is no on-disk
        # RUNNER_STATE.json to create, so no feature dir is materialized here. A prior mkdir
        # of the feature dir was vestigial; resolving it via the flow-less resolver would mkdir
        # a features/<topic> *decoy* that then wins _resolve_storage_path's existence probe and
        # hijacks storage resolution for debug/fix/goal runs whose home lives elsewhere.
        conn = _db.get_db()
        _db.write_runner_state(
            conn, state.project_root, state.topic, state.public_dict()
        )
    except Exception as exc:
        logger.warning(
            "Failed to write runner_state SQLite for %s: %s", state.topic, exc
        )


def _record_run_history(
    state: RunnerState, status: str, *, finished_at: Optional[str] = None
) -> None:
    """Write/refresh this supervised run's run_history PARENT row (the run-identity map).

    The parent row's ``adapter`` column carries the FLOW NAME (``state.flow``), NOT the last
    stage's CLI adapter: the read-model (``run_history_read._classify_kind``) keys a bare-uuid
    run's kind off this column, so a flow name in ``FLOW_NAMES`` ({team, team-build,
    consultation, …}) classifies as ``flow`` (cost summed over the stage time-window) — whereas a
    real adapter like "claude" mis-reads as ``single`` with $0 (no invocation carries the parent
    uuid). Writing ``state.current_adapter`` here was exactly that clobber.

    Shared by ``start_run`` (early ``running`` row → the run is visible in GET /runs while it
    runs) and ``_set_status`` (terminal row). Keyed by the run SLUG (storage-dir basename), not
    the topic (a goal run's topic is the nested features/<f>/goals/<slug> path). Best-effort:
    telemetry must never break a run.
    """
    try:
        from pathlib import Path as _Path

        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.run_history import (
            upsert_run as _upsert_run,
        )
        from pathly_orchestrator.fsm_compose import resolve_board_scope
        from pathly_orchestrator.fsm_ops import _resolve_storage_path

        _storage = (
            _Path(state.storage_path)
            if state.storage_path
            else _resolve_storage_path(None, state.project_root, state.topic)
        )
        _slug = _storage.name
        _scope = getattr(state, "board_scope", "") or resolve_board_scope(
            _slug, state.project_root, state.goal_id or ""
        )
        _upsert_run(
            _get_db(),
            project_root=state.project_root,
            feature=_slug,
            run_id=state.run_id,
            status=status,
            finished_at=finished_at,
            stage_count=state.iterations,
            total_tokens=0,
            cost_usd=state.cost_usd_so_far,
            adapter=state.flow or None,
            board_scope=_scope or None,
        )
    except Exception:
        logger.debug("run_history upsert (%s) error", status, exc_info=True)


def _set_status(
    state: RunnerState, status: str, broadcast_fn: Optional[Callable]
) -> None:
    state.status = status
    _write_mirror(state)
    if broadcast_fn:
        try:
            broadcast_fn(
                state.topic,
                {"type": "RUNNER_STATUS", "topic": state.topic, "status": status},
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)
    if status in {"done", "aborted", "error"}:
        import time as _time

        _record_run_history(
            state,
            status,
            finished_at=_time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        )


def _cleanup_run_id(run_id: str) -> None:
    """Remove all lifecycle state for run_id. Used by interactive mode (no reconciliation window)."""
    drop_run(run_id)
