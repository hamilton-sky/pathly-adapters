"""Telemetry endpoints: /record_activity, /record_phase, /record_phase_summary."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from flask import Blueprint, jsonify, request

from pathly_orchestrator import eventlog
from pathly_orchestrator.db import append_event as _db_append_event
from pathly_orchestrator.db.connection import get_db as _get_db
from pathly_orchestrator.feature_flags import flags
from pathly_telemetry.storage import append_activity
from ..pricing import MODEL_PRICING

bp = Blueprint("telemetry", __name__)

_VALID_PHASES = {"analyze", "build", "design", "implement", "plan", "review", "scout", "storm", "test"}
_VALID_EVENT_TYPES = {"PHASE_START", "PHASE_DONE"}

# Maps model-name prefixes to the adapter/CLI that runs them.
_ADAPTER_PREFIXES: list[tuple[tuple[str, ...], str]] = [
    (("claude-",),                          "claude"),
    (("gpt-", "o1-", "o3-", "o4-"),        "codex"),
    (("gemini-",),                          "google"),
    (("copilot-",),                         "copilot"),
]


def _infer_adapter(model: str) -> str:
    """Return a CLI/adapter name inferred from the model-name prefix."""
    m = model.lower()
    for prefixes, name in _ADAPTER_PREFIXES:
        if any(m.startswith(p) for p in prefixes):
            return name
    return "unknown" if model else ""

logger = logging.getLogger("pathly.http")


def _append_agent_done_event(
    *,
    project_root: str,
    feature: str,
    agent: str,
    model: str,
    result: str,
    conversation: object,
    total_tokens: int,
    tokens_in: int,
    tokens_out: int,
    tool_uses: int,
    wall_seconds: int,
    cost_usd: float,
    trace_id: str = "",
    span_id: str = "",
) -> None:
    """Append an AGENT_DONE event to the feature's EVENTS.jsonl so SSE subscribers see it."""
    try:
        feature_dir = Path(project_root) / "pathly" / "plans" / feature
        if not feature_dir.exists():
            return
        event: dict[str, object] = {
            "schema_version": 1,
            "type": "AGENT_DONE",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agent": agent,
            "model": model,
            "result": result,
            "total_tokens": total_tokens,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tool_uses": tool_uses,
            "wall_seconds": wall_seconds,
            "cost_usd": cost_usd,
        }
        if conversation is not None:
            event["conversation"] = conversation
        if trace_id:
            event["trace_id"] = trace_id
        if span_id:
            event["span_id"] = span_id
        eventlog.append_event(str(feature_dir), event)
    except Exception:
        logger.debug("_append_agent_done_event error", exc_info=True)


@bp.route("/record_activity", methods=["POST"])
def record_activity_endpoint():
    """Append an activity record to ~/.pathly/activity.jsonl."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"agent", "feature", "summary"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        for field in ("agent", "feature", "summary"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )
        for field in ("input_tokens", "output_tokens"):
            val = data.get(field, 0)
            if not isinstance(val, (int, float)) or val < 0:
                return (
                    jsonify(
                        {"error": f"Field '{field}' must be a non-negative number"}
                    ),
                    400,
                )
        for field in ("wall_seconds", "tool_uses"):
            val = data.get(field, 0)
            if not isinstance(val, int) or val < 0:
                return (
                    jsonify(
                        {"error": f"Field '{field}' must be a non-negative integer"}
                    ),
                    400,
                )
        for field in ("total_tokens", "duration_ms"):
            val = data.get(field, 0)
            if not isinstance(val, int) or val < 0:
                return (
                    jsonify(
                        {"error": f"Field '{field}' must be a non-negative integer"}
                    ),
                    400,
                )
        cost_usd_val = data.get("cost_usd", 0.0)
        if not isinstance(cost_usd_val, (int, float)) or cost_usd_val < 0:
            return (
                jsonify({"error": "Field 'cost_usd' must be a non-negative number"}),
                400,
            )

        # Server-side cost computation: if cost_usd is 0.0 but model + tokens are provided,
        # compute using the canonical Pathly pricing table (same table as log-agent-done skill).
        # Covers any adapter that passes model + tokens but not cost_usd.
        if float(cost_usd_val) == 0.0:
            _model = str(data.get("model", ""))
            _total = int(data.get("total_tokens", 0)) or int(data.get("input_tokens", 0)) + int(data.get("output_tokens", 0))
            if _model and _total > 0:
                _in_rate, _out_rate = next(
                    (v for k, v in MODEL_PRICING.items() if _model.startswith(k)),
                    (0.0, 0.0),
                )
                if _in_rate > 0:
                    _in_tok  = int(data.get("input_tokens",  0)) or round(_total * 0.8)
                    _out_tok = int(data.get("output_tokens", 0)) or round(_total * 0.2)
                    cost_usd_val = round(
                        (_in_tok / 1_000_000 * _in_rate) + (_out_tok / 1_000_000 * _out_rate), 6
                    )

        wall_seconds = int(data.get("wall_seconds", 0))
        duration_ms = int(data.get("duration_ms", 0))
        if wall_seconds == 0 and duration_ms > 0:
            wall_seconds = duration_ms // 1000

        if flags.telemetry:
            _model = str(data.get("model", ""))
            _adapter = str(data.get("adapter", "")) or _infer_adapter(_model)
            append_activity(
                agent=data["agent"],
                feature=data["feature"],
                summary=data["summary"],
                input_tokens=int(data.get("input_tokens", 0)),
                output_tokens=int(data.get("output_tokens", 0)),
                wall_seconds=wall_seconds,
                tool_uses=int(data.get("tool_uses", 0)),
                cost_usd=float(cost_usd_val),
                total_tokens=int(data.get("total_tokens", 0)),
                model=_model,
                adapter=_adapter,
            )

        trace_id = data.get("trace_id", "")
        span_id = data.get("span_id", "")

        project_root = data.get("project_root", "")
        if project_root and data.get("feature"):
            total_tokens = int(data.get("total_tokens", 0))
            tokens_in = int(data.get("input_tokens", 0))
            tokens_out = int(data.get("output_tokens", 0))
            if tokens_in == 0 and tokens_out == 0 and total_tokens > 0:
                tokens_in = total_tokens
            _append_agent_done_event(
                project_root=str(project_root),
                feature=str(data["feature"]),
                agent=str(data["agent"]),
                model=str(data.get("model", "")),
                result=str(data.get("result", "DONE")),
                conversation=data.get("conversation"),
                total_tokens=total_tokens,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                tool_uses=int(data.get("tool_uses", 0)),
                wall_seconds=wall_seconds,
                cost_usd=float(cost_usd_val),
                trace_id=str(trace_id) if trace_id else "",
                span_id=str(span_id) if span_id else "",
            )
            # OTel export — fire-and-forget; no-op if PATHLY_OTEL_ENDPOINT is unset
            try:
                from pathly_orchestrator import otel_export as _otel
                _otel.export_span_async({
                    "type": "AGENT_DONE",
                    "agent": str(data["agent"]),
                    "feature": str(data["feature"]),
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "result": str(data.get("result", "DONE")),
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": float(cost_usd_val),
                    "wall_seconds": wall_seconds,
                    "model": str(data.get("model", "")),
                    "conversation": data.get("conversation"),
                    "summary": str(data.get("summary", "")),
                    "trace_id": str(data.get("trace_id", "")),
                    "span_id": str(data.get("span_id", "")),
                })
            except Exception:
                logger.debug("otel_export hook error", exc_info=True)
            # Write span to local otel_spans table for Studio DB Explorer
            try:
                import json as _json
                _now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _attrs = _json.dumps({
                    "gen_ai.agent.name": str(data["agent"]),
                    "gen_ai.usage.input_tokens": tokens_in,
                    "gen_ai.usage.output_tokens": tokens_out,
                    "gen_ai.request.model": str(data.get("model", "")),
                    "pathly.cost_usd": float(cost_usd_val),
                    "pathly.wall_seconds": wall_seconds,
                    "pathly.result": str(data.get("result", "DONE")),
                })
                _conn = _get_db()
                _conn.execute(
                    "INSERT INTO otel_spans "
                    "(project_root, feature, trace_id, span_id, parent_span_id, "
                    " name, start_time, end_time, attributes) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                    (
                        str(project_root), str(data["feature"]),
                        str(trace_id) if trace_id else None,
                        str(span_id) if span_id else None,
                        f"agent.{data['agent']}", _now, _now, _attrs,
                    ),
                )
                _conn.commit()
            except Exception:
                logger.debug("otel_spans local write error", exc_info=True)

        return jsonify({"status": "recorded"}), 200
    except Exception as e:
        logging.exception("record_activity error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


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
                return jsonify({"error": f"Field '{field}' must be a non-empty string"}), 400

        event_type = data["event_type"]
        if event_type not in _VALID_EVENT_TYPES:
            return jsonify({"error": f"Invalid event_type '{event_type}'; must be one of {sorted(_VALID_EVENT_TYPES)}"}), 400

        phase = data["phase"]
        if phase not in _VALID_PHASES:
            return jsonify({"error": f"Invalid phase '{phase}'; must be one of {sorted(_VALID_PHASES)}"}), 400

        feature = data["feature"]
        project_root = data.get("project_root") or os.environ.get("PATHLY_PROJECT_ROOT", "")
        if project_root:
            feature_dir = Path(project_root) / "pathly" / "plans" / feature
        else:
            feature_dir = Path("pathly") / "plans" / feature

        if not feature_dir.exists():
            return jsonify({"error": f"Feature directory does not exist: {feature_dir}"}), 400

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
            if field not in data or not isinstance(data[field], str) or not data[field].strip():
                return jsonify({"error": f"Missing required field: '{field}'"}), 400

        text = data["text"]
        if len(text) > 2000:
            return jsonify({"error": "Field 'text' must not exceed 2000 characters"}), 400

        feature = data["feature"]
        agent = data["agent"]
        project_root = data.get("project_root") or os.environ.get("PATHLY_PROJECT_ROOT", "")
        feature_dir = Path(project_root) / "pathly" / "plans" / feature

        if not feature_dir.exists():
            return jsonify({"error": f"Feature directory does not exist: {feature_dir}"}), 400

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

        return jsonify({"status": "recorded", "seq": seq}), 200
    except Exception as e:
        logging.exception("record_phase_summary error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
