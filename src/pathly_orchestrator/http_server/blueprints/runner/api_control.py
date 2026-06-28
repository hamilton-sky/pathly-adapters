"""Runner control endpoints: pause, resume, advance, decision, agent-answer, reroute, retry, event."""

from __future__ import annotations

import logging

from flask import jsonify, request

from ...sse import _broadcast_runner
from ._runner_bp import _topic_from_body, bp


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
        return jsonify({"error": "No run found for topic"}), 404
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
    """Advance a paused run by one stage."""
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
    """Supply a decision for an awaiting_decision run."""
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
            return (
                jsonify({"error": "Field 'decision' must be a non-empty string"}),
                400,
            )

        state = _sup.get_state(topic)
        if state is None:
            return jsonify({"error": "No run found for topic"}), 404
        if state.status != "awaiting_decision":
            return (
                jsonify(
                    {"error": f"Run is not awaiting a decision (status={state.status})"}
                ),
                409,
            )

        if state.pending_menu:
            options = state.pending_menu.get("options", {})
            if options and decision not in options:
                return (
                    jsonify(
                        {
                            "error": f"Invalid decision {decision!r}; valid options: {list(options)}"
                        }
                    ),
                    400,
                )

        _sup.supply_decision(topic, decision)
        return (
            jsonify({"status": "accepted", "topic": topic, "decision": decision}),
            200,
        )
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_decision error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/runner/agent-answer", methods=["POST"])
def runner_agent_answer():
    """Supply a user answer for a stage that asked a question."""
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
    """Retry a run that ended in error."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        state = _sup.get_state(topic)
        if state is not None and state.status in {
            "running",
            "paused",
            "awaiting_decision",
        }:
            return (
                jsonify(
                    {
                        "error": f"Run is currently active (status={state.status}); abort it first"
                    }
                ),
                409,
            )

        from pathly_orchestrator.supervisor import _lock, _registry

        with _lock:
            _registry.pop(topic, None)

        required = {"flow", "project_root", "max_iterations", "max_cost_usd"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
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


@bp.route("/runner/event", methods=["POST"])
def runner_event():
    """Accept an event from an agent and persist it via eventlog."""
    try:
        from pathlib import Path
        from pathly_orchestrator import eventlog as _evtlog

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"type", "feature", "project_root", "payload"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        feature = data["feature"]
        project_root = data["project_root"]
        payload = data["payload"]

        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400
        if not isinstance(project_root, str) or not project_root.strip():
            return (
                jsonify({"error": "Field 'project_root' must be a non-empty string"}),
                400,
            )
        if not isinstance(payload, dict):
            return jsonify({"error": "Field 'payload' must be a JSON object"}), 400

        storage_path = str(Path(project_root) / "pathly" / "plans" / feature)
        _evtlog.append_event(storage_path, payload)
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_event error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
