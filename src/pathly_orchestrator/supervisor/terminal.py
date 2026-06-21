"""Terminal stage execution: spawn, watcher, reconciliation."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from pathly_orchestrator import eventlog as _eventlog

from .state import RunnerState, logger
from .registry import (
    _lock,
    TerminalRun,
    create_run,
    drop_run,
    _cleanup_run_id,
    _TERMINAL_RESULT_TIMEOUT,
)


def _write_supervisor_phase_summary(
    *,
    project_root: str,
    topic: str,
    stage: str,
    agent: str,
    text: str,
    broadcast_fn=None,
) -> None:
    """Write a PHASE_SUMMARY event to the feature's SQLite DB and broadcast to Studio via SSE."""
    import time as _time

    if not project_root or not topic:
        return
    try:
        from pathly_orchestrator import db as _db

        feature_dir = Path(project_root) / "pathly" / "plans" / topic
        if not feature_dir.exists():
            return
        conn = _db.get_db()
        phase = stage.lower().replace("-", "_") if stage else ""
        event: dict = {
            "schema_version": 1,
            "type": "PHASE_SUMMARY",
            "feature": topic,
            "agent": agent,
            "text": text,
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        if phase:
            event["phase"] = phase
        _db.append_event(conn, project_root, topic, event)
        # Broadcast to Studio so live log cards update in headless mode
        if broadcast_fn:
            try:
                broadcast_fn(topic, event)
            except Exception:
                pass
    except Exception:
        logger.debug("_write_supervisor_phase_summary failed", exc_info=True)


def _agent_done_watcher(
    run: TerminalRun,
    feature_dir: Path,
    feature: str,
    last_seq: int,
) -> None:
    """Poll SQLite fsm_events for AGENT_DONE; call run.mark_agent_done() on first match.

    Runs as a daemon thread when feature_flags.early_advance is True.
    Stops when run.request_stop_watcher() is called or after _TERMINAL_RESULT_TIMEOUT seconds.
    The caller passes the TerminalRun object directly so the watcher keeps a live
    reference even if drop_run() removes it from the registry.
    """
    from pathly_orchestrator import db as _db

    try:
        conn = _db.get_db()
    except Exception as exc:
        logger.warning("_agent_done_watcher: cannot open DB for %s: %s", feature, exc)
        return

    project_root = str(feature_dir.parent.parent.parent)
    _POLL = 0.15
    elapsed = 0.0
    seq = last_seq

    while elapsed < _TERMINAL_RESULT_TIMEOUT:
        if run.stop_watcher:
            return
        try:
            rows = _db.read_events(conn, project_root, feature, since_seq=seq)
        except Exception:
            rows = []
        for row in rows:
            if row.get("seq", 0) > seq:
                seq = row["seq"]
            if row.get("type") == "AGENT_DONE":
                run.mark_agent_done()
                return
        run.wait_watcher_stop_signal(_POLL)
        elapsed += _POLL


def _reconciliation_window(
    run: TerminalRun,
    stage: str,
    topic: str,
    events_path: str,
    timeout: float = 600,
) -> None:
    """Wait up to `timeout` seconds for PTY billing POST after early FSM advance.

    If billing data arrives: patch last AGENT_DONE via _patch_last_agent_done.
    If timeout: write TYPE_STAGE_RECONCILIATION_FAILURE to EVENTS.jsonl.
    Always drops the run from the registry.
    """
    import datetime
    from pathly_orchestrator.events import TYPE_STAGE_RECONCILIATION_FAILURE
    from pathly_orchestrator.runner import _patch_last_agent_done

    arrived = run.wait_pty_result(timeout=timeout)

    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if arrived:
            data = run.pty_result or {}
            billing_record = data.get("result") or {}
            cost_usd = float(
                (billing_record.get("cost_usd") or 0.0)
                if isinstance(billing_record, dict)
                else 0.0
            )
            tokens_in = int(
                (billing_record.get("tokens_in") or 0)
                if isinstance(billing_record, dict)
                else 0
            )
            tokens_out = int(
                (billing_record.get("tokens_out") or 0)
                if isinstance(billing_record, dict)
                else 0
            )
            tool_uses = int(
                (billing_record.get("tool_uses") or 0)
                if isinstance(billing_record, dict)
                else 0
            )
            wall_seconds = int(data.get("wall_seconds") or 0)
            try:
                _patch_last_agent_done(
                    Path(events_path).parent,
                    cost_usd,
                    tokens_in,
                    tokens_out,
                    wall_seconds,
                    tool_uses,
                )
            except Exception as exc:
                logger.warning(
                    "_reconciliation_window: _patch_last_agent_done failed: %s", exc
                )
        else:
            try:
                _eventlog.append_event(
                    str(Path(events_path).parent),
                    {
                        "type": TYPE_STAGE_RECONCILIATION_FAILURE,
                        "topic": topic,
                        "stage": stage,
                        "run_id": run.run_id,
                        "exit_code": -1,
                        "ts": now_ts,
                    },
                )
            except Exception as exc:
                logger.warning("_reconciliation_window: failed to write event: %s", exc)
    finally:
        drop_run(run.run_id)


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
    from pathly_orchestrator.events import TYPE_STAGE_INTERACTIVE_DONE
    from pathly_orchestrator.feature_flags import FeatureFlags
    from pathly_orchestrator.runner import (
        resolve_argv,
        resolve_interactive_argv,
        read_last_agent_done,
    )

    feature_flags = FeatureFlags()
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
        argv = resolve_interactive_argv(
            adapter, model, session=session, autonomy=autonomy
        )
    else:
        argv = resolve_argv(
            adapter,
            instructions,
            model,
            session=session,
            autonomy=autonomy,
            interactive=False,
        )

    tab_id = f"runner-{run_id[-10:]}"
    label = f"{adapter} — {state.current_state or state.status}"
    with _lock:
        state.active_tab_id = tab_id

    run = create_run(run_id)

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

        _write_supervisor_phase_summary(
            project_root=state.project_root,
            topic=state.topic,
            stage=state.current_state or "",
            broadcast_fn=broadcast_fn,
            agent="supervisor",
            text=f"Starting {(state.current_state or 'stage').lower()} — {adapter} agent spawned",
        )

        if not run.wait_started(timeout=30):
            drop_run(run_id)
            raise RuntimeError(
                f"terminal_spawn_timeout: Studio did not spawn PTY for {tab_id} within 30s"
            )

        if feature_flags.early_advance:
            feature_dir = Path(state.project_root) / "pathly" / "plans" / state.topic
            feature = state.topic

            last_seq = 0
            try:
                from pathly_orchestrator import db as _db

                _db_conn = _db.get_db()
                row = _db_conn.execute(
                    "SELECT MAX(seq) FROM fsm_events WHERE project_root=? AND feature=?",
                    (state.project_root, feature),
                ).fetchone()
                last_seq = row[0] or 0
            except Exception as exc:
                logger.warning(
                    "_run_stage_via_terminal: could not read last_seq: %s", exc
                )

            watcher_t = threading.Thread(
                target=_agent_done_watcher,
                args=(run, feature_dir, feature, last_seq),
                daemon=True,
                name=f"agent-done-watcher-{run_id}",
            )
            watcher_t.start()

            outcome = run.wait_result_or_agent_done(timeout=_TERMINAL_RESULT_TIMEOUT)

            if outcome == "timeout":
                run.request_stop_watcher()
                drop_run(run_id)
                raise RuntimeError(
                    f"terminal_result_timeout: PTY for {tab_id} did not report a result within "
                    f"{_TERMINAL_RESULT_TIMEOUT}s — the process likely crashed without sending an exit callback"
                )

            if outcome == "agent_done":
                storage_path = (
                    Path(state.project_root) / "pathly" / "plans" / state.topic
                )
                agent_done_data = read_last_agent_done(storage_path) or {}
                result_for_fsm = {
                    "cost_usd": agent_done_data.get("cost_usd", 0.0),
                    "session_id": agent_done_data.get("session_id"),
                    "result": agent_done_data.get("summary", ""),
                }

                if broadcast_fn:
                    broadcast_fn(
                        state.topic,
                        {
                            "type": "TERMINAL_AGENT_DONE",
                            "tab_id": tab_id,
                            "run_id": run_id,
                            "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                        },
                    )

                if use_interactive:
                    if broadcast_fn:
                        broadcast_fn(
                            state.topic,
                            {
                                "type": "TERMINAL_KILL",
                                "tab_id": tab_id,
                                "run_id": run_id,
                                "ts": datetime.datetime.now(
                                    datetime.timezone.utc
                                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            },
                        )
                    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
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
                        logger.warning(
                            "_run_stage_via_terminal: failed to write STAGE_INTERACTIVE_DONE: %s",
                            exc,
                        )
                    drop_run(run_id)
                else:
                    events_path_for_recon = str(feature_dir / "EVENTS.jsonl")
                    recon_t = threading.Thread(
                        target=_reconciliation_window,
                        args=(
                            run,
                            state.current_state,
                            state.topic,
                            events_path_for_recon,
                        ),
                        daemon=True,
                        name=f"recon-window-{run_id}",
                    )
                    recon_t.start()
                return result_for_fsm

            # outcome == "pty_result" — PTY arrived first; cancel watcher and return
            run.request_stop_watcher()
            data = run.pty_result or {}
            drop_run(run_id)
            exit_code = data.get("exit_code")
            if exit_code is not None and exit_code != 0:
                raise RuntimeError(
                    f"terminal_exit_nonzero: PTY for {tab_id} exited with code {exit_code}"
                )
            return data.get("result", {})

        # ── Slow path (early_advance disabled) ────────────────────────────────
        # Wait for PTY to report its result.  Without a timeout a crashed terminal
        # hangs the supervisor forever.
        if not run.wait_pty_result(timeout=_TERMINAL_RESULT_TIMEOUT):
            drop_run(run_id)
            raise RuntimeError(
                f"terminal_result_timeout: PTY for {tab_id} did not report a result within "
                f"{_TERMINAL_RESULT_TIMEOUT}s — the process likely crashed without sending an exit callback"
            )
        data = run.pty_result or {}
        drop_run(run_id)
        exit_code = data.get("exit_code")
        if exit_code is not None and exit_code != 0:
            raise RuntimeError(
                f"terminal_exit_nonzero: PTY for {tab_id} exited with code {exit_code}"
            )
        return data.get("result", {})
    finally:
        with _lock:
            state.active_tab_id = ""
