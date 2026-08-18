"""Making the event log agree with what the CLI actually did.

Three cooperating pieces, all post-spawn:
  * ``_agent_done_watcher``    — early-advance detection of the agent's own AGENT_DONE
  * ``_reconciliation_window`` — fold the REAL cost/tokens onto that AGENT_DONE
  * ``_synthesize_agent_done_if_missing`` — write one when the agent reported none, so an
    executor-owned run still gets an invocation row instead of vanishing unbilled

Split from ``terminal`` because this is reconciliation, not execution: it runs after the PTY
has settled and never influences whether the stage itself succeeds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pathly_orchestrator import eventlog as _eventlog

from .state import RunnerState, logger
from .registry import TerminalRun, drop_run, _TERMINAL_RESULT_TIMEOUT
from .terminal_identity import _run_board_scope


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
    model: str = "",
    board_scope: str = "",
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
                    model=model,
                    run_id=run.run_id,
                    board_scope=board_scope,
                )
            except Exception as exc:
                logger.warning(
                    "_reconciliation_window: _patch_last_agent_done failed: %s", exc
                )
            # Reconcile the executor invocation written provisionally at AGENT_DONE
            # (cost=0 / tokens=0 — the CLI billing wasn't known yet) with the real
            # figures now that the PTY billing has arrived. Without this the rollups
            # show cost/tokens=0 for every early-advance (loop/single/board) agent.
            try:
                from pathly_orchestrator.db.connection import get_db
                from pathly_orchestrator.db.queries.invocations import (
                    update_invocation_billing,
                )

                billed_cost, billed_source = cost_usd, (
                    "provider_reported" if cost_usd > 0 else "unpriced"
                )
                if cost_usd == 0 and (tokens_in + tokens_out) > 0 and model:
                    from pathly_orchestrator.db.pricing import estimate_cost

                    est_cost, est_source = estimate_cost(model, tokens_in, tokens_out)
                    if est_source == "estimated":
                        billed_cost, billed_source = est_cost, est_source

                update_invocation_billing(
                    get_db(),
                    run.run_id,
                    cost_usd=billed_cost,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_source=billed_source,
                    provider=model or None,
                )
            except Exception as exc:
                logger.debug(
                    "_reconciliation_window: invocation billing update skipped: %s", exc
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


def _synthesize_agent_done_if_missing(
    state: RunnerState, run_id: str, model: str, data: Optional[dict]
) -> None:
    """Safety net: give an executor-owned run (board/single/loop) a telemetry row even when
    its agent wrote NO AGENT_DONE. The invocation projection is keyed on AGENT_DONE, so a run
    that self-reports none has no row — it never appears in the Monitor's RECENT list and its
    cost is unbilled (the board evaluator/consolidate were exactly this before they got
    completion-report). When a real AGENT_DONE for THIS run_id already exists, do nothing (the
    agent self-reported — never overwrite its identity or figures). Otherwise write a synthetic
    AGENT_DONE carrying the PTY billing, keyed by run_id + board_scope (run-identity: the
    spawner knows both), so the projector creates a fully-identified invocation and the
    reconciliation BILLING_UPDATE folds onto IT — not a stale same-feature AGENT_DONE. Runs
    BEFORE _reconcile_billing_now so _patch_last_agent_done sees this as the last event.
    Best-effort; never raises into the loop.
    """
    if not getattr(state, "executor_owned_telemetry", False):
        return
    try:
        import time as _time

        from pathly_orchestrator.fsm_ops import _resolve_storage_path
        from pathly_orchestrator.runner import read_last_agent_done as _read_last

        storage = (
            Path(state.storage_path)
            if state.storage_path
            else _resolve_storage_path(None, state.project_root, state.topic)
        )
        last = _read_last(storage)
        if last and last.get("run_id") == run_id:
            return  # the agent self-reported this run — nothing to synthesize
        billing = (data or {}).get("result") or {}
        if not isinstance(billing, dict):
            billing = {}
        tin = int(billing.get("tokens_in") or 0)
        tout = int(billing.get("tokens_out") or 0)
        event = {
            "type": "AGENT_DONE",
            "agent": state.current_state or "agent",
            "model": model or None,
            "run_id": run_id,
            # run-identity: the board scope issued at spawn (NULL only when unresolvable).
            "board_scope": _run_board_scope(state, storage) or None,
            # Executor-owned run TYPE for the Monitor's RECENT bucketing (goal-loop → loop,
            # board/single runs → single) — mirrors the completion-report <run_category>.
            "category": (
                "loop" if (state.flow or "").lower() == "goal-loop" else "single"
            ),
            "conversation": 0,
            "result": "DONE",
            "outcome": "success",
            "summary": str(billing.get("summary") or "")[:2000],
            "cost_usd": float(billing.get("cost_usd") or 0.0),
            "tokens_in": tin,
            "tokens_out": tout,
            "total_tokens": tin + tout,
            "wall_seconds": int((data or {}).get("wall_seconds") or 0),
            "tool_uses": int(billing.get("tool_uses") or 0),
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "schema_version": 1,
            "synthetic": True,
        }
        _eventlog.append_event(str(storage), event)
        logger.info(
            "synthesized AGENT_DONE for executor run %s (agent wrote none)",
            run_id[:8],
        )
    except Exception as exc:
        logger.debug("_synthesize_agent_done_if_missing skipped: %s", exc)
