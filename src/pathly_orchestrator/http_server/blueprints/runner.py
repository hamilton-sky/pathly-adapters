"""Runner control endpoints (/runner/*)."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from ..sse import _broadcast_runner

bp = Blueprint("runner", __name__)


def _topic_from_body(data: dict) -> str | None:
    topic = data.get("topic", "")
    return topic if isinstance(topic, str) and topic.strip() else None


@bp.route("/runner/start", methods=["POST"])
def runner_start():
    """Start a supervised run for a topic.

    Required body fields: topic, flow, project_root, max_iterations, max_cost_usd.
    Returns 409 if a run for that topic is already active.
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"topic", "flow", "project_root", "max_iterations", "max_cost_usd"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        topic = data.get("topic", "")
        if not isinstance(topic, str) or not topic.strip():
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        for field_name in ("flow", "project_root"):
            val = data.get(field_name, "")
            if not isinstance(val, str) or not val.strip():
                return jsonify({"error": f"Field '{field_name}' must be a non-empty string"}), 400

        max_iterations = data.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            return jsonify({"error": "Field 'max_iterations' must be a positive integer"}), 400

        max_cost_usd = data.get("max_cost_usd")
        if not isinstance(max_cost_usd, (int, float)) or max_cost_usd <= 0:
            return jsonify({"error": "Field 'max_cost_usd' must be a positive number"}), 400

        model = data.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"
        timeout = data.get("timeout", 600)
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = 600
        autonomy = data.get("autonomy", {})
        if not isinstance(autonomy, dict):
            autonomy = {}
        # interactive: True = visible PTY killed on AGENT_DONE, False = headless/reconciliation
        interactive = data.get("interactive", True)
        if not isinstance(interactive, bool):
            interactive = bool(interactive)

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
            from pathly_orchestrator.db.queries.run_history import upsert_run as _upsert_run
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
        return jsonify({"status": "started", "topic": topic, "run_id": state.run_id}), 200
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
        with _sup._lock:
            evt = _sup._terminal_started_events.get(run_id)
            if evt is None:
                return jsonify({"error": "unknown run_id"}), 404
            evt.set()
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

        with _sup._lock:
            evt = _sup._terminal_result_events.get(run_id)
            if evt is None:
                return jsonify({"error": "unknown run_id"}), 404
            runner_state = _sup._registry.get(topic)
            if runner_state is not None:
                adapter = runner_state.current_adapter or "claude"
            else:
                import logging as _logging
                _logging.getLogger("pathly.http").warning(
                    "runner_terminal_result: no RunnerState found for topic %r, falling back to 'claude'", topic
                )
                adapter = "claude"

        # Parse stdout result (session_id + cost_usd) — outside the lock
        parsed = parse_result(adapter, data.get("stdout_tail", ""))

        # Enrich with EVENTS.jsonl summary (authoritative, never truncated)
        if runner_state is not None:
            try:
                from pathly_orchestrator.runner import read_last_agent_done, _storage_path
                storage = _storage_path(runner_state.flow, runner_state.project_root, runner_state.topic)
                agent_done = read_last_agent_done(storage)
                if agent_done is not None:
                    summary = agent_done.get("summary", "")
                    if summary:
                        parsed["result"] = summary
                    # Use EVENTS.jsonl cost as fallback when stdout didn't capture it
                    if not parsed.get("cost_usd") and agent_done.get("cost_usd", 0.0) > 0.0:
                        parsed["cost_usd"] = agent_done["cost_usd"]
            except Exception as exc:
                logging.getLogger("pathly.http").warning("runner_terminal_result: EVENTS.jsonl read failed: %s", exc)

        # Broadcast STAGE_RESULT so Studio renderer can update the stageLog
        # directly — this is the reliable path when PTY stdout parsing fails
        # (e.g. long-running builds where the final JSON scrolls out of the buffer).
        tab_id = runner_state.active_tab_id if runner_state is not None else ""
        if tab_id and topic:
            _broadcast_runner(topic, {
                "type": "STAGE_RESULT",
                "topic": topic,
                "run_id": run_id,
                "tab_id": tab_id,
                "result": parsed.get("result", ""),
                "total_cost_usd": parsed.get("cost_usd", 0.0),
                "duration_ms": int((data.get("wall_seconds") or 0) * 1000),
                "usage": parsed.get("usage", {}),
            })

        with _sup._lock:
            _sup._terminal_result_data[run_id] = {
                "result": parsed,
                "exit_code": data.get("exit_code"),
                "wall_seconds": data.get("wall_seconds"),
                "user_initiated": data.get("user_initiated"),
            }
            evt.set()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_terminal_result error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/pause", methods=["POST"])
def runner_pause():
    """Pause an active run at its next boundary."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.pause_run(topic)
        return jsonify({"status": "pausing", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": f"No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_pause error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/resume", methods=["POST"])
def runner_resume():
    """Resume a paused run."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.resume_run(topic)
        return jsonify({"status": "resumed", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_resume error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/advance", methods=["POST"])
def runner_advance():
    """Advance a paused run by one stage (resume + re-pause after next boundary).

    This is a thin control shim — it unpauses the loop; the boundary logic in
    the supervisor handles the actual step semantics.
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.resume_run(topic)
        return jsonify({"status": "advancing", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_advance error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/decision", methods=["POST"])
def runner_decision():
    """Supply a decision for an awaiting_decision run.

    Required: topic, decision (must be a key in pending_menu.options).
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        decision = data.get("decision", "")
        if not isinstance(decision, str) or not decision.strip():
            return jsonify({"error": "Field 'decision' must be a non-empty string"}), 400

        state = _sup.get_state(topic)
        if state is None:
            return jsonify({"error": "No run found for topic"}), 404
        if state.status != "awaiting_decision":
            return jsonify({"error": f"Run is not awaiting a decision (status={state.status})"}), 409

        if state.pending_menu:
            options = state.pending_menu.get("options", {})
            if options and decision not in options:
                return jsonify({"error": f"Invalid decision {decision!r}; valid options: {list(options)}"}), 400

        _sup.supply_decision(topic, decision)
        return jsonify({"status": "accepted", "topic": topic, "decision": decision}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_decision error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/agent-answer", methods=["POST"])
def runner_agent_answer():
    """Supply a user answer for a stage that asked a question via AskUserQuestion (denied in headless mode)."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        answer = data.get("answer", "")
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        if not isinstance(answer, str) or not answer.strip():
            return jsonify({"error": "Field 'answer' must be a non-empty string"}), 400

        _sup.supply_agent_answer(topic, answer.strip())
        return jsonify({"status": "accepted", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_agent_answer error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/reroute", methods=["POST"])
def runner_reroute():
    """Override the adapter for the next stage of an active run."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        adapter = data.get("adapter", "")
        if not isinstance(adapter, str) or not adapter.strip():
            return jsonify({"error": "Field 'adapter' must be a non-empty string"}), 400

        _sup.reroute_run(topic, adapter)
        return jsonify({"status": "rerouted", "topic": topic, "adapter": adapter}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_reroute error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/retry", methods=["POST"])
def runner_retry():
    """Retry a run that ended in error by starting it fresh.

    Thin wrapper: clears error state from registry then delegates to start_run
    with the same parameters.  Requires full start params (caps required).
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        state = _sup.get_state(topic)
        if state is not None and state.status in {"running", "paused", "awaiting_decision"}:
            return jsonify({"error": f"Run is currently active (status={state.status}); abort it first"}), 409

        # Evict from registry so start_run won't reject it as active
        from pathly_orchestrator.supervisor import _lock, _registry
        with _lock:
            _registry.pop(topic, None)

        required = {"flow", "project_root", "max_iterations", "max_cost_usd"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        max_iterations = data.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            return jsonify({"error": "Field 'max_iterations' must be a positive integer"}), 400

        max_cost_usd = data.get("max_cost_usd")
        if not isinstance(max_cost_usd, (int, float)) or max_cost_usd <= 0:
            return jsonify({"error": "Field 'max_cost_usd' must be a positive number"}), 400

        model = data.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"
        timeout = data.get("timeout", 600)
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = 600
        autonomy = data.get("autonomy", {})
        if not isinstance(autonomy, dict):
            autonomy = {}

        _sup.start_run(
            topic=topic,
            flow=data["flow"],
            project_root=data["project_root"],
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=float(max_cost_usd),
            autonomy=autonomy,
            broadcast_fn=_broadcast_runner,
        )
        return jsonify({"status": "retried", "topic": topic}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_retry error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/abort", methods=["POST"])
def runner_abort():
    """Hard-abort an active run; kills in-flight subprocess within ~2s."""
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


@bp.route("/runner/event", methods=["POST"])
def runner_event():
    """Accept an event from an agent and persist it via eventlog.

    Required body fields: type, feature, project_root, payload (dict).
    Returns {"ok": true} on success.
    """
    try:
        from pathlib import Path
        from pathly_orchestrator import eventlog as _evtlog

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"type", "feature", "project_root", "payload"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        feature = data["feature"]
        project_root = data["project_root"]
        payload = data["payload"]

        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400
        if not isinstance(project_root, str) or not project_root.strip():
            return jsonify({"error": "Field 'project_root' must be a non-empty string"}), 400
        if not isinstance(payload, dict):
            return jsonify({"error": "Field 'payload' must be a JSON object"}), 400

        storage_path = str(Path(project_root) / "pathly" / "plans" / feature)
        _evtlog.append_event(storage_path, payload)
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_event error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/status", methods=["GET"])
def runner_status():
    """Return the current RunnerState for a topic.

    Query param: topic (required).
    """
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
