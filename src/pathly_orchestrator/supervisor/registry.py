"""Registry: shared in-memory state, signal dicts, and registry helpers."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable, Optional

from .state import RunnerState, logger

_registry: dict[str, RunnerState] = {}
_lock = threading.Lock()
_terminal_started_events: dict[str, threading.Event] = {}
_terminal_result_events: dict[str, threading.Event] = {}
_terminal_result_data: dict[str, dict] = {}

# Early-advance signal channels — independent of _terminal_result_events/_terminal_result_data.
# The watcher sets _agent_done_events[run_id] when AGENT_DONE is detected in SQLite.
# _agent_done_stop_events[run_id] is set to stop the watcher thread.
# These dicts MUST NEVER be read from or written to by the /runner/terminal/result handler.
_agent_done_events: dict[str, threading.Event] = {}
_agent_done_stop_events: dict[str, threading.Event] = {}

_TERMINAL_RESULT_TIMEOUT = 1800


def get_state(topic: str) -> Optional[RunnerState]:
    with _lock:
        return _registry.get(topic)


def recover_stale_mirrors(project_root: str) -> None:
    """On server startup, mark any runner_state rows left as 'running' → 'error'.

    Uses the central ~/.pathly/pathly.db to call mark_stale_runners().
    Falls back to rewriting RUNNER_STATE.json for feature dirs that have no SQLite entry.
    """
    from pathly_orchestrator import db as _db

    plans_dir = Path(project_root) / "pathly" / "plans"
    if not plans_dir.is_dir():
        return

    handled: set = set()
    try:
        conn = _db.get_db()
        count = _db.mark_stale_runners(conn)
        if count:
            logger.info("Marked %d stale runner(s) in central DB → error", count)
    except Exception as exc:
        logger.warning("recover_stale_mirrors: SQLite mark failed: %s", exc)

    for mirror in plans_dir.glob("*/RUNNER_STATE.json"):
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
            logger.info("Rewrote stale mirror for topic %s → error", data.get("topic"))


def _write_mirror(state: RunnerState) -> None:
    try:
        from pathly_orchestrator import db as _db
        feature_dir = Path(state.project_root) / "pathly" / "plans" / state.topic
        feature_dir.mkdir(parents=True, exist_ok=True)
        conn = _db.get_db()
        _db.write_runner_state(conn, state.project_root, state.topic, state.public_dict())
    except Exception as exc:
        logger.warning("Failed to write runner_state SQLite for %s: %s", state.topic, exc)


def _set_status(state: RunnerState, status: str, broadcast_fn: Optional[Callable]) -> None:
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


def _cleanup_run_id(run_id: str) -> None:
    """Pop all four signal dicts for run_id — used by interactive mode (no reconciliation window)."""
    with _lock:
        _terminal_result_events.pop(run_id, None)
        _terminal_result_data.pop(run_id, None)
        _agent_done_events.pop(run_id, None)
        _agent_done_stop_events.pop(run_id, None)
    _terminal_started_events.pop(run_id, None)
