"""Terminal stage execution — spawn a CLI for one stage and return its result.

This module owns the SPAWN. Its neighbours own what happens around it:
  * ``terminal_identity``  — the run-identity row opened/settled per spawn
  * ``terminal_reconcile`` — early-advance AGENT_DONE detection + billing reconciliation
  * ``terminal_billing``   — per-spawn otel span + PTY-result cost patch
  * ``terminal_phase``     — supervisor-authored phase summaries

The names below are re-exported deliberately: ``supervisor/__init__`` and the test-suite import
them from ``supervisor.terminal``, and ``_reconciliation_window`` is monkeypatched in THIS
module's namespace — so it must be called as a bare name here, never via its defining module.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

from pathly_orchestrator import eventlog as _eventlog

from .state import RunnerState, logger
from .registry import (
    _lock,
    create_run,
    drop_run,
    _TERMINAL_RESULT_TIMEOUT,
)
from .terminal_identity import (
    _record_spawn_identity,
    _record_spawn_prompt,
    _settle_spawn_identity,
    _run_board_scope,
)
from .terminal_reconcile import (
    _agent_done_watcher,
    _reconciliation_window,
    _synthesize_agent_done_if_missing,
)
from .terminal_argv import _resolve_spawn_argv
from .terminal_billing import _emit_executor_telemetry, _reconcile_billing_now
from .terminal_phase import _write_supervisor_phase_summary

__all__ = [
    "_run_stage_via_terminal",
    "_agent_done_watcher",
    "_reconciliation_window",
    "_synthesize_agent_done_if_missing",
    "_write_supervisor_phase_summary",
    "_record_spawn_identity",
    "_run_board_scope",
]


def _pty_return(data: dict) -> dict:
    """The PTY's result dict with the CLI exit_code relayed in.

    Reached only on a zero/absent exit code — a nonzero exit raises upstream — so this never
    masks a failure; it makes the returned-dict contract uniform so a caller that inspects the
    result (the loop executor's _outcome_is_failure) always sees the exit code. The extra key
    is inert for the FSM/team consumer, which reads only cost_usd/session_id/result."""
    result = data.get("result")
    result = dict(result) if isinstance(result, dict) else {}
    exit_code = data.get("exit_code")
    if exit_code is not None:
        result.setdefault("exit_code", exit_code)
    return result


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
    from pathly_orchestrator.runner import read_last_agent_done

    feature_flags = FeatureFlags()
    # Thread run_id into the prompt so the completion-report AGENT_DONE carries it. The gate's
    # BILLING_UPDATE (see _reconciliation_window → _patch_last_agent_done) uses the SAME run_id, so
    # the invocation projection folds real cost/tokens onto the right AGENT_DONE exactly — instead
    # of the fragile (agent, conversation) match that orphaned billing into empty "agent" rows.
    if instructions:
        instructions = instructions.replace("<run_id>", run_id or "")
    # run-identity: one identity row per spawn (FSM stages, loop tasks, board runs all
    # pass through here with their own run_id); settled done/error in the finally below.
    _spawn_identity = _record_spawn_identity(state, run_id, adapter)
    _record_spawn_prompt(state, run_id, instructions)
    use_interactive = state.interactive
    argv = _resolve_spawn_argv(
        state,
        instructions,
        adapter,
        model,
        session,
        autonomy,
        feature_flags.early_advance,
        broadcast_fn,
    )

    tab_id = f"runner-{run_id[-10:]}"
    label = f"{adapter} — {state.current_state or state.status}"
    with _lock:
        state.active_tab_id = tab_id

    run = create_run(run_id)
    try:
        # Early-advance baseline — capture feature_dir / feature / last_seq BEFORE the spawn
        # broadcast below. The AGENT_DONE watcher only reports events with seq > last_seq; if the
        # baseline is read AFTER the spawn, a fast AGENT_DONE (the test writes one ~50ms after
        # TERMINAL_SPAWN; a real agent under CI DB contention likewise) can land at/under the
        # baseline, and the watcher then waits the full timeout. Reading it here — before anything
        # can spawn — makes "seq > last_seq" race-free.
        ea_feature_dir = None
        ea_feature = ""
        ea_last_seq = 0
        if feature_flags.early_advance:
            from pathly_orchestrator.fsm_ops import _resolve_storage_path

            ea_feature_dir = (
                Path(state.storage_path)
                if state.storage_path
                else _resolve_storage_path(None, state.project_root, state.topic)
            )
            # Event-log key = storage-dir basename (run slug), NOT state.topic (a goal run's topic
            # is the nested features/<f>/goals/<slug> path; append_event keys by the basename).
            ea_feature = ea_feature_dir.name
            try:
                from pathly_orchestrator import db as _db

                _row = (
                    _db.get_db()
                    .execute(
                        "SELECT MAX(seq) FROM fsm_events WHERE project_root=? AND feature=?",
                        (state.project_root, ea_feature),
                    )
                    .fetchone()
                )
                ea_last_seq = _row[0] or 0
            except Exception as exc:
                logger.warning(
                    "_run_stage_via_terminal: could not read last_seq: %s", exc
                )

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
            # Monitor category for this engine. Board one-shots (single-agent / evaluator /
            # decompose) run with flow=='board-run' → 'single'; FSM pipeline stages → 'flow'.
            # Without this the frontend tags EVERY registered runner tab 'flow' (terminal.ts
            # buildEngineMeta), so a board single-agent run showed up as a FLOW run.
            "category": "single" if (state.flow or "") == "board-run" else "flow",
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
            # Baseline (feature_dir / feature / last_seq) was captured BEFORE the spawn broadcast
            # above — reuse it. Re-reading it here would reintroduce the watcher-vs-AGENT_DONE race
            # that hung goal/loop runs for the full terminal-result timeout under CI DB contention.
            feature_dir = ea_feature_dir
            feature = ea_feature
            last_seq = ea_last_seq

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
                    Path(state.storage_path)
                    if state.storage_path
                    else _resolve_storage_path(None, state.project_root, state.topic)
                )
                agent_done_data = read_last_agent_done(storage_path) or {}
                result_for_fsm = {
                    "cost_usd": agent_done_data.get("cost_usd", 0.0),
                    "session_id": agent_done_data.get("session_id"),
                    "result": agent_done_data.get("summary", ""),
                }
                # Relay the agent's self-reported outcome so the loop executor's
                # _outcome_is_failure can FAIL a task whose agent reported failure but exited
                # cleanly (silent-failure guard #2). Early-advance returns before the PTY exits,
                # so the AGENT_DONE outcome — not an exit code — is the authoritative signal here.
                # Only relayed when present; an absent outcome stays success (back-compat).
                for _k in ("outcome", "error"):
                    _v = agent_done_data.get(_k)
                    if _v:
                        result_for_fsm[_k] = _v

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
                    try:
                        from pathly_orchestrator.supervisor.artifact_reconcile import (
                            reconcile_artifacts,
                        )

                        _bfn = (
                            (lambda payload: broadcast_fn(state.topic, payload))
                            if broadcast_fn
                            else None
                        )
                        # Resolve the just-completed stage's declared <out_path> from the FSM's own
                        # composition manifest so reconcile can attach it directly (state-one-authority:
                        # replaces the retired ARTIFACTS.jsonl ledger — no disk mirror). Best-effort.
                        _out_path = None
                        try:
                            from pathly_orchestrator.fsm_compose import (
                                resolve_stage_out_path,
                            )
                            from pathly_orchestrator.fsm_ops import _load_flow

                            _out_path = resolve_stage_out_path(
                                _load_flow(state.flow or "team"),
                                state.current_state,
                                storage_path,
                            )
                        except Exception:
                            _out_path = None
                        reconcile_artifacts(
                            storage_path,
                            state.topic,
                            goal_id=(state.goal_id or None),
                            broadcast_fn=_bfn,
                            out_path=_out_path,
                        )
                    except Exception as exc:
                        logger.warning(
                            "_run_stage_via_terminal: artifact reconcile failed: %s",
                            exc,
                        )
                    events_path_for_recon = str(feature_dir / "EVENTS.jsonl")
                    recon_t = threading.Thread(
                        target=_reconciliation_window,
                        args=(
                            run,
                            state.current_state,
                            state.topic,
                            events_path_for_recon,
                        ),
                        kwargs={
                            "model": model,
                            # run-identity: the gate's BILLING_UPDATE carries the spawn-issued
                            # board scope so the projection can fill it when the anchor lacks it.
                            "board_scope": _run_board_scope(state, feature_dir),
                        },
                        daemon=True,
                        name=f"recon-window-{run_id}",
                    )
                    recon_t.start()
                _emit_executor_telemetry(state, run_id, agent_done_data, 0.0)
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
            _synthesize_agent_done_if_missing(state, run_id, model, data)
            _reconcile_billing_now(state, run_id, model, data)
            _emit_executor_telemetry(
                state,
                run_id,
                data.get("result") or {},
                float(data.get("wall_seconds") or 0),
            )
            return _pty_return(data)

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
        _synthesize_agent_done_if_missing(state, run_id, model, data)
        _reconcile_billing_now(state, run_id, model, data)
        _emit_executor_telemetry(
            state,
            run_id,
            data.get("result") or {},
            float(data.get("wall_seconds") or 0),
        )
        return _pty_return(data)
    finally:
        with _lock:
            state.active_tab_id = ""
        _settle_spawn_identity(state, run_id, _spawn_identity)
