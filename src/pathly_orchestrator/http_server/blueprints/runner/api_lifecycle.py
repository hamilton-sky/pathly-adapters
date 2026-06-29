"""Runner lifecycle endpoints: start, terminal-started, terminal-result, abort, status."""

from __future__ import annotations

import logging

from flask import jsonify, request

from ...sse import _broadcast_runner
from ._runner_bp import _topic_from_body, bp


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
            if runner_state is not None:
                adapter = runner_state.current_adapter or "claude"
            else:
                import logging as _logging

                _logging.getLogger("pathly.http").warning(
                    "runner_terminal_result: no RunnerState found for topic %r, falling back to 'claude'",
                    topic,
                )
                adapter = "claude"

        parsed = parse_result(adapter, data.get("stdout_tail", ""))

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
            except Exception as exc:
                logging.getLogger("pathly.http").warning(
                    "runner_terminal_result: EVENTS.jsonl read failed: %s", exc
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
