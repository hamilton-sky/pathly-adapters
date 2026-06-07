"""Terminal stage execution: spawn, watcher, reconciliation."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from pathly_orchestrator import eventlog as _eventlog

from .state import RunnerState, logger
from .registry import (
    _lock,
    _terminal_started_events,
    _terminal_result_events,
    _terminal_result_data,
    _agent_done_events,
    _agent_done_stop_events,
    _TERMINAL_RESULT_TIMEOUT,
    _cleanup_run_id,
)


def _agent_done_watcher(
    run_id: str,
    feature_dir: Path,
    feature: str,
    last_seq: int,
) -> None:
    """Poll SQLite fsm_events for AGENT_DONE; set _agent_done_events[run_id] on first match.

    Runs as a daemon thread when feature_flags.early_advance is True.
    Stops when _agent_done_stop_events[run_id] is set or after _TERMINAL_RESULT_TIMEOUT seconds.
    """
    from pathly_orchestrator import db as _db

    with _lock:
        stop_evt = _agent_done_stop_events.setdefault(run_id, threading.Event())

    try:
        conn = _db.get_db()
    except Exception as exc:
        logger.warning("_agent_done_watcher: cannot open DB for %s: %s", feature, exc)
        return

    project_root = str(feature_dir.parent.parent.parent)
    _POLL = 0.15
    _TIMEOUT = _TERMINAL_RESULT_TIMEOUT
    elapsed = 0.0
    seq = last_seq

    while elapsed < _TIMEOUT:
        if stop_evt.is_set():
            return
        try:
            rows = _db.read_events(conn, project_root, feature, since_seq=seq)
        except Exception:
            rows = []
        for row in rows:
            if row.get("seq", 0) > seq:
                seq = row["seq"]
            if row.get("type") == "AGENT_DONE":
                with _lock:
                    done_evt = _agent_done_events.get(run_id)
                    if done_evt is not None:
                        done_evt.set()
                return
        stop_evt.wait(_POLL)
        elapsed += _POLL


def _reconciliation_window(
    run_id: str,
    stage: str,
    topic: str,
    events_path: str,
    timeout: float = 600,
) -> None:
    """Wait up to `timeout` seconds for PTY billing POST after early FSM advance.

    If billing data arrives: patch last AGENT_DONE and append BILLING_UPDATE via _patch_last_agent_done.
    If timeout: write TYPE_STAGE_RECONCILIATION_FAILURE to EVENTS.jsonl.
    Always cleans up all four dicts for run_id.
    """
    import datetime
    from pathlib import Path
    from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE
    from pathly_orchestrator.runner import _patch_last_agent_done

    with _lock:
        result_evt = _terminal_result_events.get(run_id)

    arrived = result_evt.wait(timeout=timeout) if result_evt is not None else False

    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if arrived:
            with _lock:
                data = _terminal_result_data.pop(run_id, {})
            billing_record = data.get("result") or {}
            cost_usd = float((billing_record.get("cost_usd") or 0.0) if isinstance(billing_record, dict) else 0.0)
            tokens_in = int((billing_record.get("tokens_in") or 0) if isinstance(billing_record, dict) else 0)
            tokens_out = int((billing_record.get("tokens_out") or 0) if isinstance(billing_record, dict) else 0)
            tool_uses = int((billing_record.get("tool_uses") or 0) if isinstance(billing_record, dict) else 0)
            wall_seconds = int(data.get("wall_seconds") or 0)
            try:
                _patch_last_agent_done(
                    Path(events_path).parent,
                    cost_usd, tokens_in, tokens_out, wall_seconds, tool_uses,
                )
            except Exception as exc:
                logger.warning("_reconciliation_window: _patch_last_agent_done failed: %s", exc)
        else:
            try:
                _eventlog.append_event(
                    str(Path(events_path).parent),
                    {
                        "type": TYPE_STAGE_RECONCILIATION_FAILURE,
                        "topic": topic,
                        "stage": stage,
                        "run_id": run_id,
                        "exit_code": -1,
                        "ts": now_ts,
                    },
                )
            except Exception as exc:
                logger.warning("_reconciliation_window: failed to write event: %s", exc)
    finally:
        with _lock:
            _terminal_result_events.pop(run_id, None)
            _terminal_result_data.pop(run_id, None)
            _agent_done_events.pop(run_id, None)
            _agent_done_stop_events.pop(run_id, None)
        _terminal_started_events.pop(run_id, None)


def _run_stage_via_terminal(
    state: RunnerState,
    instructions: str,
    adapter: str,
    model: str,
    run_id: str,
    broadcast_fn: Optional[Callable],
    session: Optional[str] = None,
    autonomy: bool = True,
) -> dict:
    import datetime
    import pathly_orchestrator.supervisor as _sup
    from pathly_orchestrator.events import TYPE_STAGE_INTERACTIVE_DONE
    from pathly_orchestrator.feature_flags import FeatureFlags
    from pathly_orchestrator.runner import resolve_argv, resolve_interactive_argv, read_last_agent_done

    feature_flags = FeatureFlags()
    # state.interactive is set by the UI (POST /runner/start body); falls back to env var default
    use_interactive = state.interactive
    if use_interactive and not feature_flags.early_advance:
        msg = "Interactive mode requires PATHLY_RUNNER_EARLY_ADVANCE=1"
        if broadcast_fn:
            try:
                broadcast_fn(state.topic, {"type": "RUNNER_WARNING", "message": msg})
            except Exception:
                pass
        raise RuntimeError(msg)

    if use_interactive:
        argv = resolve_interactive_argv(adapter, model, session=session, autonomy=autonomy)
    else:
        argv = resolve_argv(adapter, instructions, model, session=session, autonomy=autonomy, interactive=False)
    tab_id = f"runner-{run_id[-10:]}"
    label = f"{adapter} — {state.current_state or state.status}"
    with _lock:
        state.active_tab_id = tab_id
    try:
        payload = {
            "type": "TERMINAL_SPAWN",
            "topic": state.topic,
            "run_id": run_id,
            "tab_id": tab_id,
            "label": label,
            "adapter": adapter,
            "argv": argv,
            "cwd": state.project_root,
            "prompt": instructions,
            "stage": state.current_state,
            "interactive": use_interactive,
        }
        if broadcast_fn:
            broadcast_fn(state.topic, payload)
        with _lock:
            started = _terminal_started_events.setdefault(run_id, threading.Event())
            result_evt = _terminal_result_events.setdefault(run_id, threading.Event())
        if not started.wait(timeout=30):
            with _lock:
                _terminal_started_events.pop(run_id, None)
                _terminal_result_events.pop(run_id, None)
            raise RuntimeError(
                f"terminal_spawn_timeout: Studio did not spawn PTY for {tab_id} within 30s"
            )

        if feature_flags.early_advance:
            feature_dir = Path(state.project_root) / "pathly" / "plans" / state.topic
            feature = state.topic

            # Capture current max seq so the watcher only sees new AGENT_DONE events
            last_seq = 0
            try:
                from pathly_orchestrator import db as _db
                _db_conn = _db.get_db()
                row = _db_conn.execute(
                    "SELECT MAX(seq) FROM fsm_events WHERE project_root=? AND feature=?",
                    (state.project_root, feature)
                ).fetchone()
                last_seq = row[0] or 0
            except Exception as exc:
                logger.warning("_run_stage_via_terminal: could not read last_seq: %s", exc)

            # Register agent_done signal event before starting the watcher
            with _lock:
                agent_done_evt = _agent_done_events.setdefault(run_id, threading.Event())

            watcher_t = threading.Thread(
                target=_agent_done_watcher,
                args=(run_id, feature_dir, feature, last_seq),
                daemon=True,
                name=f"agent-done-watcher-{run_id}",
            )
            watcher_t.start()

            # Race: AGENT_DONE vs PTY result (poll in short bursts to avoid busy-wait)
            elapsed = 0.0
            _POLL_INTERVAL = 0.05
            fired_early = False
            while elapsed < _TERMINAL_RESULT_TIMEOUT:
                if agent_done_evt.wait(timeout=_POLL_INTERVAL):
                    fired_early = True
                    break
                if result_evt.is_set():
                    break
                elapsed += _POLL_INTERVAL

            if fired_early:
                # Fast path: AGENT_DONE detected — advance FSM, start reconciliation window
                storage_path = (
                    Path(state.project_root)
                    / "pathly" / "plans" / state.topic
                )
                agent_done_data = read_last_agent_done(storage_path) or {}
                result_for_fsm = {
                    "cost_usd": agent_done_data.get("cost_usd", 0.0),
                    "session_id": agent_done_data.get("session_id"),
                    "result": agent_done_data.get("summary", ""),
                }

                if broadcast_fn:
                    broadcast_fn(state.topic, {
                        "type": "TERMINAL_AGENT_DONE",
                        "tab_id": tab_id,
                        "run_id": run_id,
                        "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    })

                if use_interactive:
                    if broadcast_fn:
                        broadcast_fn(state.topic, {
                            "type": "TERMINAL_KILL",
                            "tab_id": tab_id,
                            "run_id": run_id,
                            "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                        })
                    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    try:
                        _eventlog.append_event(
                            str(feature_dir),
                            {
                                "type": TYPE_STAGE_INTERACTIVE_DONE,
                                "topic": state.topic,
                                "stage": state.current_state,
                                "ts": now_ts,
                            },
                        )
                    except Exception as exc:
                        logger.warning("_run_stage_via_terminal: failed to write STAGE_INTERACTIVE_DONE: %s", exc)
                    _cleanup_run_id(run_id)
                else:
                    events_path_for_recon = str(feature_dir / "EVENTS.jsonl")
                    recon_t = threading.Thread(
                        target=_sup._reconciliation_window,
                        args=(run_id, state.current_state, state.topic, events_path_for_recon),
                        daemon=True,
                        name=f"recon-window-{run_id}",
                    )
                    recon_t.start()
                return result_for_fsm

            # Slow path: PTY result arrived first (or timeout) — cancel watcher
            with _lock:
                stop_evt = _agent_done_stop_events.get(run_id)
            if stop_evt is not None:
                stop_evt.set()

            if not result_evt.is_set():
                # Timed out waiting for PTY result
                with _lock:
                    _terminal_started_events.pop(run_id, None)
                    _terminal_result_events.pop(run_id, None)
                    _agent_done_events.pop(run_id, None)
                    _agent_done_stop_events.pop(run_id, None)
                raise RuntimeError(
                    f"terminal_result_timeout: PTY for {tab_id} did not report a result within "
                    f"{_TERMINAL_RESULT_TIMEOUT}s — the process likely crashed without sending an exit callback"
                )

            with _lock:
                data = _terminal_result_data.pop(run_id, {})
                _terminal_started_events.pop(run_id, None)
                _terminal_result_events.pop(run_id, None)
                _agent_done_events.pop(run_id, None)
                _agent_done_stop_events.pop(run_id, None)
            exit_code = data.get("exit_code")
            if exit_code is not None and exit_code != 0:
                raise RuntimeError(
                    f"terminal_exit_nonzero: PTY for {tab_id} exited with code {exit_code}"
                )
            return data.get("result", {})

        # ── Slow path (early_advance disabled) ────────────────────────────────
        # Wait up to 30 min for the PTY to report its result.
        # Without a timeout, a crashed or unresponsive terminal hangs the supervisor forever.
        # (The PTY exit handler in terminal.ts POSTs /runner/terminal/result; if that POST
        # never arrives — e.g. the process exited before the exit handler fired, or the POST
        # failed — result_evt is never set and the thread blocks indefinitely.)
        # NOTE: _terminal_result_events[run_id] is never touched by the watcher path, so
        # the /runner/terminal/result POST handler will always find it during any active
        # reconciliation window — returning 200, not 404.
        if not result_evt.wait(timeout=_TERMINAL_RESULT_TIMEOUT):
            with _lock:
                _terminal_started_events.pop(run_id, None)
                _terminal_result_events.pop(run_id, None)
            raise RuntimeError(
                f"terminal_result_timeout: PTY for {tab_id} did not report a result within "
                f"{_TERMINAL_RESULT_TIMEOUT}s — the process likely crashed without sending an exit callback"
            )
        with _lock:
            data = _terminal_result_data.pop(run_id, {})
            _terminal_started_events.pop(run_id, None)
            _terminal_result_events.pop(run_id, None)
        exit_code = data.get("exit_code")
        if exit_code is not None and exit_code != 0:
            raise RuntimeError(
                f"terminal_exit_nonzero: PTY for {tab_id} exited with code {exit_code}"
            )
        return data.get("result", {})
    finally:
        with _lock:
            state.active_tab_id = ""
