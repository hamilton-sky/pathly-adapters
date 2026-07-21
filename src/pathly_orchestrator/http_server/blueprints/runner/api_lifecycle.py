"""Runner lifecycle endpoints: start, terminal-started, terminal-result, abort, status."""

from __future__ import annotations

import logging

from flask import jsonify, request

from ...sse import _broadcast_runner
from ._runner_bp import _topic_from_body, _validate_stage_overrides, bp


def _write_stage_telemetry(
    runner_state, parsed: dict, agent_done, wall_seconds
) -> None:
    """Best-effort: persist ONE OTEL span per completed FSM stage (for the Traces tab).

    The agent_invocation row is NO LONGER written here — every FSM stage emits an
    AGENT_DONE event, and the universal projector (``invocation_projection`` via
    ``append_event``) derives the invocation row from that event stream, folding in
    the superseding BILLING_UPDATE. Writing an invocation here too would double-count.
    This still writes the span so the trace tree is intact. It never raises —
    telemetry must not break the terminal-result callback.
    """
    try:
        import json as _json
        from datetime import datetime, timedelta, timezone

        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.otel_spans import write_otel_span

        ad = agent_done or {}
        stage = runner_state.current_state or "stage"
        agent_role = ad.get("agent") or stage
        cost = parsed.get("cost_usd") or ad.get("cost_usd") or 0.0
        tin = parsed.get("tokens_in") or ad.get("tokens_in") or 0
        tout = parsed.get("tokens_out") or ad.get("tokens_out") or 0
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(seconds=float(wall_seconds or 0))

        conn = _get_db()
        write_otel_span(
            conn,
            runner_state.project_root,
            runner_state.topic,
            name=stage,
            trace_id=runner_state.trace_id or None,
            span_id=runner_state.span_id or None,
            parent_span_id=None,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            attributes=_json.dumps(
                {
                    "agent": agent_role,
                    "adapter": runner_state.current_adapter,
                    "cost_usd": cost,
                    "tokens_in": tin,
                    "tokens_out": tout,
                }
            ),
        )
    except Exception:
        logging.getLogger("pathly.http").debug(
            "stage telemetry write skipped", exc_info=True
        )


@bp.route("/runner/start", methods=["POST"])
def runner_start():
    """Start a supervised run for a topic."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"topic", "flow", "project_root", "max_iterations", "max_cost_usd"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        topic = data.get("topic", "")
        if not isinstance(topic, str) or not topic.strip():
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        for field_name in ("flow", "project_root"):
            val = data.get(field_name, "")
            if not isinstance(val, str) or not val.strip():
                return (
                    jsonify(
                        {"error": f"Field '{field_name}' must be a non-empty string"}
                    ),
                    400,
                )

        max_iterations = data.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            return (
                jsonify({"error": "Field 'max_iterations' must be a positive integer"}),
                400,
            )

        max_cost_usd = data.get("max_cost_usd")
        if not isinstance(max_cost_usd, (int, float)) or max_cost_usd <= 0:
            return (
                jsonify({"error": "Field 'max_cost_usd' must be a positive number"}),
                400,
            )

        model = data.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"
        timeout = data.get("timeout", 600)
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = 600
        autonomy = data.get("autonomy", {})
        if not isinstance(autonomy, dict):
            autonomy = {}
        interactive = data.get("interactive", True)
        if not isinstance(interactive, bool):
            interactive = bool(interactive)

        # Flow-gate-preview (P2): transient per-stage prompt overrides — zero-cost when
        # absent (the common case; the gate only sends the key when non-empty).
        stage_overrides = _validate_stage_overrides(
            data.get("stage_overrides"), data.get("flow", ""), data.get("project_root", "")
        )

        # Reject up-front if a headless run routes any stage to an adapter with no headless
        # mode (copilot/antigravity today), so it fails fast with a clear message instead of
        # dying opaquely mid-pipeline when resolve_command raises. Interactive runs are exempt
        # (they launch a visible REPL, not a one-shot argv).
        if not interactive:
            try:
                from pathly_orchestrator.adapters import unsupported_headless_adapters
                from pathly_orchestrator.fsm_ops import _load_flow

                flow_cfg = _load_flow(data["flow"], data["project_root"] or None) or {}
                adapter_map = flow_cfg.get("adapter_map") or {}
                bad = unsupported_headless_adapters(list(adapter_map.values()))
                if bad:
                    return (
                        jsonify(
                            {
                                "error": (
                                    f"Flow {data['flow']!r} routes stage(s) to adapter(s) with "
                                    f"no headless mode: {', '.join(bad)}. Use claude or codex, or "
                                    f"remove them from the flow's adapter_map."
                                )
                            }
                        ),
                        400,
                    )
            except Exception:
                logging.debug("adapter pre-flight check skipped", exc_info=True)

        state = _sup.start_run(
            topic=topic,
            flow=data["flow"],
            project_root=data["project_root"],
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=float(max_cost_usd),
            autonomy=autonomy,
            broadcast_fn=_broadcast_runner,
            interactive=interactive,
            stage_overrides=stage_overrides,
        )
        try:
            import time as _time
            from pathly_orchestrator.db.connection import get_db as _get_db
            from pathly_orchestrator.db.queries.run_history import (
                upsert_run as _upsert_run,
            )

            _now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
            _upsert_run(
                _get_db(),
                project_root=data["project_root"],
                feature=topic,
                run_id=state.run_id,
                status="running",
                started_at=_now,
                adapter=data.get("flow"),
            )
        except Exception:
            logging.debug("run_history upsert (start) error", exc_info=True)
        return (
            jsonify({"status": "started", "topic": topic, "run_id": state.run_id}),
            200,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_start error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/terminal/started", methods=["POST"])
def runner_terminal_started():
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        run_id = data.get("run_id", "")
        if not topic or not isinstance(run_id, str) or not run_id:
            return jsonify({"error": "unknown run_id"}), 404
        run = _sup.get_run(run_id)
        if run is None:
            return jsonify({"error": "unknown run_id"}), 404
        run.mark_started()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_terminal_started error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/terminal/result", methods=["POST"])
def runner_terminal_result():
    try:
        from pathly_orchestrator import supervisor as _sup
        from pathly_orchestrator.runner import parse_result

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        run_id = data.get("run_id", "")
        if not topic or not isinstance(run_id, str) or not run_id:
            return jsonify({"error": "unknown run_id"}), 404

        run = _sup.get_run(run_id)
        if run is None:
            return jsonify({"error": "unknown run_id"}), 404
        with _sup._lock:
            runner_state = _sup._registry.get(topic)
        # Parse with the adapter that SPAWNED this run — the client sends it in the body.
        # Inferring from runner_state.current_adapter is RACY: with early-advance the FSM may
        # already have moved to the NEXT stage's engine by the time this result POSTs back, so a
        # codex stage's output would be parsed by the claude parser (skipping _codex_usage) and
        # record 0 tokens / $0. Fall back to current_adapter, then 'claude', for older clients.
        adapter = (data.get("adapter") or "").strip().lower()
        if not adapter:
            adapter = (
                runner_state.current_adapter if runner_state is not None else ""
            ) or "claude"
            if runner_state is None:
                import logging as _logging

                _logging.getLogger("pathly.http").warning(
                    "runner_terminal_result: no adapter in body + no RunnerState for topic %r → 'claude'",
                    topic,
                )

        parsed = parse_result(adapter, data.get("stdout_tail", ""))
        agent_done = None

        if runner_state is not None:
            try:
                from pathly_orchestrator.runner import (
                    read_last_agent_done,
                    _storage_path,
                )

                storage = _storage_path(
                    runner_state.flow, runner_state.project_root, runner_state.topic
                )
                agent_done = read_last_agent_done(storage)
                if agent_done is not None:
                    summary = agent_done.get("summary", "")
                    if summary:
                        parsed["result"] = summary
                    if (
                        not parsed.get("cost_usd")
                        and agent_done.get("cost_usd", 0.0) > 0.0
                    ):
                        parsed["cost_usd"] = agent_done["cost_usd"]
                    if (
                        not parsed.get("tokens_in")
                        and agent_done.get("tokens_in", 0) > 0
                    ):
                        parsed["tokens_in"] = agent_done["tokens_in"]
                    if (
                        not parsed.get("tokens_out")
                        and agent_done.get("tokens_out", 0) > 0
                    ):
                        parsed["tokens_out"] = agent_done["tokens_out"]
                    if (
                        not parsed.get("tool_uses")
                        and agent_done.get("tool_uses", 0) > 0
                    ):
                        parsed["tool_uses"] = agent_done["tool_uses"]

                    # ── Authoritative, run-keyed billing (adapter-agnostic) ──────────────
                    # This handler is the ONE chokepoint every runner spawn (any adapter) hits.
                    # Write a BILLING_UPDATE from the parsed CLI stdout for THIS run, keyed by
                    # run_id, so the invocation projection folds the REAL cost/tokens onto this
                    # run's AGENT_DONE — overriding the agent's (often-wrong) self-estimate and
                    # NOT depending on the claude-only stop hook's "most recent feature" guess.
                    # claude → real cost; codex → tokens (cost estimated downstream). Runs here
                    # reliably even when the supervisor's own reconcile races run completion
                    # (which is why the consultation planner/codex stages were $0). The
                    # supervisor's _reconcile_billing_now is now a redundant belt (same values).
                    _b_cost = float(parsed.get("cost_usd") or 0.0)
                    _b_tin = int(parsed.get("tokens_in") or 0)
                    _b_tout = int(parsed.get("tokens_out") or 0)
                    if _b_cost > 0 or (_b_tin + _b_tout) > 0:
                        from pathly_orchestrator.runner import (
                            _patch_last_agent_done as _plad,
                        )

                        _mu = parsed.get("model_usage") or {}
                        _plad(
                            storage,
                            _b_cost,
                            _b_tin,
                            _b_tout,
                            int(data.get("wall_seconds") or 0),
                            int(parsed.get("tool_uses") or 0),
                            model=(next(iter(_mu), "") if _mu else ""),
                            run_id=run_id,
                        )
            except Exception as exc:
                logging.getLogger("pathly.http").warning(
                    "runner_terminal_result: EVENTS.jsonl read / billing failed: %s",
                    exc,
                )

        # Fill the otel_spans + agent_invocations trace tables (one span + one invocation
        # per completed stage). Best-effort — never blocks the result callback.
        if runner_state is not None:
            _write_stage_telemetry(
                runner_state, parsed, agent_done, data.get("wall_seconds")
            )

        tab_id = runner_state.active_tab_id if runner_state is not None else ""
        if tab_id and topic:
            _broadcast_runner(
                topic,
                {
                    "type": "STAGE_RESULT",
                    "topic": topic,
                    "run_id": run_id,
                    "tab_id": tab_id,
                    "result": parsed.get("result", ""),
                    "total_cost_usd": parsed.get("cost_usd", 0.0),
                    "duration_ms": int((data.get("wall_seconds") or 0) * 1000),
                    "usage": parsed.get("usage", {}),
                },
            )

        run.mark_pty_result(
            {
                "result": parsed,
                "exit_code": data.get("exit_code"),
                "wall_seconds": data.get("wall_seconds"),
                "user_initiated": data.get("user_initiated"),
            }
        )

        # Killing the runner tab means "stop this run", not "advance to the next stage".
        # Without this, a multi-stage goal run (consultation decompose, team executor)
        # just re-spawns the next stage after early-advance, so the run never reaches a
        # terminal status, its on_done never fires, and the board's "Decomposing…/Running…"
        # timer pill ticks forever. Abort the run (if still active) so the loop stops and
        # on_done clears the pill. Board-run / single executors hold no RunnerState in the
        # registry — they already terminate via the non-zero exit code — so the guard makes
        # this a no-op for them.
        if data.get("user_initiated"):
            try:
                st = _sup.get_state(topic)
                if st is not None and st.status in (
                    "running",
                    "paused",
                    "awaiting_decision",
                ):
                    _sup.abort_run(topic)
            except Exception:
                logging.debug("user_initiated tab-kill abort failed", exc_info=True)

        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_terminal_result error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/abort", methods=["POST"])
def runner_abort():
    """Hard-abort an active run."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.abort_run(topic)
        return jsonify({"status": "aborting", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_abort error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/status", methods=["GET"])
def runner_status():
    """Return the current RunnerState for a topic."""
    try:
        from pathly_orchestrator import supervisor as _sup

        topic = request.args.get("topic", "").strip()
        if not topic:
            return jsonify({"error": "Query parameter 'topic' is required"}), 400

        state = _sup.get_state(topic)
        if state is None:
            return jsonify({"error": "No run found for topic"}), 404

        return jsonify(state.public_dict()), 200
    except Exception as exc:
        logging.exception("runner_status error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
