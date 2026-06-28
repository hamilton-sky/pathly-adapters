"""Telemetry phase endpoints: /telemetry/trends, /telemetry/pricing, /record_phase, /record_phase_summary."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from flask import jsonify, request

from ._telemetry_bp import (
    PricingRegistry,
    _VALID_EVENT_TYPES,
    _VALID_PHASES,
    _db_append_event,
    _get_db,
    bp,
    eventlog,
    logger,
)


@bp.route("/telemetry/trends", methods=["GET"])
def trends_endpoint():
    """Return daily aggregate trend data for a feature."""
    feature = request.args.get("feature")
    if feature is None:
        return jsonify({"error": "Missing required query param: feature"}), 400
    if not feature.strip():
        return jsonify({"trends": []}), 200

    days = request.args.get("days", 126, type=int)
    days = max(1, min(days, 365))

    try:
        from pathly_orchestrator.db.queries.trends import get_daily_trends

        conn = _get_db()
        buckets = get_daily_trends(conn, feature, days)
        return jsonify({"trends": buckets}), 200
    except Exception:
        logger.exception("trends_endpoint error")
        return jsonify({"trends": []}), 200


@bp.route("/telemetry/pricing", methods=["GET"])
def pricing_endpoint():
    """Return the full provider pricing table."""
    return jsonify({"providers": PricingRegistry().all_providers()}), 200


@bp.route("/record_phase", methods=["POST"])
def record_phase_endpoint():
    """Append a PHASE_START or PHASE_DONE event to the feature's EVENTS.jsonl."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = ("feature", "agent", "phase", "event_type")
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field: '{field}'"}), 400
            if not isinstance(data[field], str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )

        event_type = data["event_type"]
        if event_type not in _VALID_EVENT_TYPES:
            return (
                jsonify(
                    {
                        "error": f"Invalid event_type '{event_type}'; must be one of {sorted(_VALID_EVENT_TYPES)}"
                    }
                ),
                400,
            )

        phase = data["phase"]
        if phase not in _VALID_PHASES:
            return (
                jsonify(
                    {
                        "error": f"Invalid phase '{phase}'; must be one of {sorted(_VALID_PHASES)}"
                    }
                ),
                400,
            )

        feature = data["feature"]
        project_root = data.get("project_root") or os.environ.get(
            "PATHLY_PROJECT_ROOT", ""
        )
        if project_root:
            feature_dir = Path(project_root) / "pathly" / "plans" / feature
        else:
            feature_dir = Path("pathly") / "plans" / feature

        if not feature_dir.exists():
            return (
                jsonify({"error": f"Feature directory does not exist: {feature_dir}"}),
                400,
            )

        event: dict[str, object] = {
            "schema_version": 1,
            "type": event_type,
            "phase": phase,
            "agent": data["agent"],
            "feature": feature,
        }
        if data.get("conv") is not None:
            event["conv"] = data["conv"]
        if event_type == "PHASE_DONE":
            for field in ("total_tokens", "tool_uses", "scouts_count"):
                if data.get(field) is not None:
                    event[field] = data[field]
        if data.get("summary") is not None:
            event["summary"] = data["summary"]
        event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        eventlog.append_event(str(feature_dir), event)

        try:
            from ._phase_board import post_phase_to_board

            post_phase_to_board(
                feature, data["agent"], phase, event_type, data.get("conv")
            )
        except Exception:
            logging.debug("phase board post failed", exc_info=True)

        return jsonify({"status": "recorded"}), 200
    except Exception as e:
        logging.exception("record_phase error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/record_phase_summary", methods=["POST"])
def record_phase_summary_endpoint():
    """Store a PHASE_SUMMARY event in SQLite for the given feature."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        for field in ("feature", "agent", "text"):
            if (
                field not in data
                or not isinstance(data[field], str)
                or not data[field].strip()
            ):
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        text = data["text"]
        if len(text) > 2000:
            return (
                jsonify({"error": "Field 'text' must not exceed 2000 characters"}),
                400,
            )

        feature = data["feature"]
        agent = data["agent"]
        project_root = data.get("project_root") or os.environ.get(
            "PATHLY_PROJECT_ROOT", ""
        )
        feature_dir = Path(project_root) / "pathly" / "plans" / feature

        if not feature_dir.exists():
            return (
                jsonify({"error": f"Feature directory does not exist: {feature_dir}"}),
                400,
            )

        event: dict[str, object] = {
            "schema_version": 1,
            "type": "PHASE_SUMMARY",
            "feature": feature,
            "agent": agent,
            "text": text,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        phase = data.get("phase")
        if phase and isinstance(phase, str) and phase.strip():
            event["phase"] = phase

        conv = data.get("conv")
        if conv is not None:
            try:
                event["conv"] = int(conv)
            except (TypeError, ValueError):
                pass

        conn = _get_db()
        seq = _db_append_event(conn, str(project_root), feature, event)

        try:
            from pathly_orchestrator.http_server.sse import _broadcast_runner

            _broadcast_runner(feature, event)
        except Exception:
            pass

        return jsonify({"status": "recorded", "seq": seq}), 200
    except Exception as e:
        logging.exception("record_phase_summary error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
