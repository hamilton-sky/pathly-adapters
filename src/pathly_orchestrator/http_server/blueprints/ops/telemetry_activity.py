"""Telemetry activity endpoint: /record_activity."""

from __future__ import annotations

import logging
import time

from flask import jsonify, request

from ._telemetry_bp import (
    PricingRegistry,
    _db_append_event,
    _get_db,
    _infer_adapter,
    append_activity,
    bp,
    eventlog,
    flags,
    logger,
)


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
    cost_source: str = "unpriced",
    trace_id: str = "",
    span_id: str = "",
) -> None:
    """Append an AGENT_DONE event to the DB via the shared event-append path (eventlog).

    EVENTS.jsonl is a downstream DB->disk export, not this function's target; SSE
    subscribers are notified through the same append path."""
    try:
        from pathly_orchestrator.fsm_ops import _resolve_storage_path

        feature_dir = _resolve_storage_path(None, project_root, feature)
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
            "cost_source": cost_source,
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

        _model = str(data.get("model", ""))
        _provider = str(data.get("provider", "")) or _infer_adapter(_model)
        if not data.get("provider"):
            logger.warning(
                "record_activity: 'provider' field absent; inferred %r from model %r",
                _provider,
                _model,
            )

        if float(cost_usd_val) > 0.0:
            cost_source = "provider_reported"
        else:
            _tokens_in = int(data.get("input_tokens", 0) or data.get("tokens_in", 0))
            _tokens_out = int(data.get("output_tokens", 0) or data.get("tokens_out", 0))
            _computed, cost_source = PricingRegistry().compute(
                _provider, _model, _tokens_in, _tokens_out
            )
            if cost_source == "estimated":
                cost_usd_val = _computed

        wall_seconds = int(data.get("wall_seconds", 0))
        duration_ms = int(data.get("duration_ms", 0))
        if wall_seconds == 0 and duration_ms > 0:
            wall_seconds = duration_ms // 1000

        if flags.telemetry:
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
                provider=_provider,
                cost_source=cost_source,
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
                cost_source=cost_source,
                trace_id=str(trace_id) if trace_id else "",
                span_id=str(span_id) if span_id else "",
            )
            try:
                from pathly_orchestrator import otel_export as _otel

                _otel.export_span_async(
                    {
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
                        "provider": _provider,
                        "conversation": data.get("conversation"),
                        "summary": str(data.get("summary", "")),
                        "trace_id": str(data.get("trace_id", "")),
                        "span_id": str(data.get("span_id", "")),
                    }
                )
            except Exception:
                logger.debug("otel_export hook error", exc_info=True)
            try:
                import json as _json

                _now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _attrs = _json.dumps(
                    {
                        "gen_ai.agent.name": str(data["agent"]),
                        "gen_ai.usage.input_tokens": tokens_in,
                        "gen_ai.usage.output_tokens": tokens_out,
                        "gen_ai.request.model": str(data.get("model", "")),
                        "pathly.cost_usd": float(cost_usd_val),
                        "pathly.wall_seconds": wall_seconds,
                        "pathly.result": str(data.get("result", "DONE")),
                    }
                )
                _conn = _get_db()
                _conn.execute(
                    "INSERT INTO otel_spans "
                    "(project_root, feature, trace_id, span_id, parent_span_id, "
                    " name, start_time, end_time, attributes) "
                    "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                    (
                        str(project_root),
                        str(data["feature"]),
                        str(trace_id) if trace_id else None,
                        str(span_id) if span_id else None,
                        f"agent.{data['agent']}",
                        _now,
                        _now,
                        _attrs,
                    ),
                )
                _conn.commit()
            except Exception:
                logger.debug("otel_spans local write error", exc_info=True)

        return jsonify({"status": "recorded", "cost_source": cost_source}), 200
    except Exception as e:
        logging.exception("record_activity error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
