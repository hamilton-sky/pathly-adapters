"""Named menu and metrics endpoints."""
from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify, request

from ..sse import _NO_FEATURE_MENU, _schedule_push_clear, _broadcast_sse, _push_menu_to_sse
from ..middleware import _metrics, _metrics_lock

logger = logging.getLogger("pathly.http")

bp = Blueprint("menu", __name__)


@bp.route("/menu/<name>", methods=["GET"])
def get_named_menu(name: str):
    """Return a pre-defined named menu, broadcast it as MENU_PUSH via SSE, start TTL.

    Query params:
      feature (optional): substituted into {feature} placeholders in title/descriptions.
      state   (optional): FSM state name (e.g. BUILDING); items whose `states:` list
                          does not include this state are filtered out.  Items with no
                          `states:` field are always included.

    The Studio Conductor shows the menu until TTL expires (MENU_CLEAR SSE event)
    or the user dismisses it.  Skills call this endpoint instead of rendering
    ASCII menus in the terminal.
    """
    feature = request.args.get("feature", "").strip()
    state = request.args.get("state", "").strip().upper()

    try:
        from importlib.resources import files as _res_files
        import yaml as _yaml
        all_menus = _yaml.safe_load(
            _res_files("pathly_data").joinpath("core/menus.yaml").read_text(encoding="utf-8")
        ) or {}
    except Exception:
        logger.debug("get_named_menu: failed to load menus.yaml", exc_info=True)
        return jsonify({"error": "Menu registry unavailable"}), 503

    if name not in all_menus:
        return jsonify({"error": f"Unknown menu: '{name}'"}), 404

    raw = all_menus[name]
    ttl = float(raw.get("ttl", 60))
    pushed_at_ms = int(time.time() * 1000)

    def sub(text: str) -> str:
        return text.replace("{feature}", feature) if feature and isinstance(text, str) else (text or "")

    menu = {
        "state": name,
        "feature": feature,
        "agent": "director",
        "title": sub(raw.get("title", name)),
        "subtitle": sub(raw.get("subtitle", "")),
        "items": [
            {
                "label": item.get("label", ""),
                "description": sub(item.get("description", "")),
                "command": item.get("command", ""),
                "terminal_kind": item.get("terminal_kind", "claude"),
            }
            for item in raw.get("items", [])
            if not item.get("states") or not state or state in [s.upper() for s in item["states"]]
        ],
        "empty_message": raw.get("empty_message", "No options available."),
        "ttl": ttl,
        "pushed_at": pushed_at_ms,
    }

    _broadcast_sse({"type": "MENU_PUSH", "menu": menu})
    _schedule_push_clear(ttl)

    return jsonify({"status": "pushed", "menu": menu}), 200


@bp.route("/metrics", methods=["GET"])
def metrics_endpoint():
    """Prometheus text-format metrics endpoint (HTTP + pipeline counters)."""
    from flask import Response
    from pathly_orchestrator.metrics import _collector

    with _metrics_lock:
        http_snap = dict(_metrics)
    pipe = _collector.snapshot()

    lines = [
        "# HELP pathly_requests_total Total HTTP requests received",
        "# TYPE pathly_requests_total counter",
        f"pathly_requests_total {http_snap.get('pathly_requests_total', 0)}",
        "# HELP pathly_requests_rate_limited_total Requests rejected by rate limiter",
        "# TYPE pathly_requests_rate_limited_total counter",
        f"pathly_requests_rate_limited_total {http_snap.get('pathly_requests_rate_limited_total', 0)}",
        "# HELP pathly_request_errors_total HTTP 5xx responses",
        "# TYPE pathly_request_errors_total counter",
        f"pathly_request_errors_total {http_snap.get('pathly_request_errors_total', 0)}",
        "# HELP pathly_sse_clients_active Currently connected SSE clients",
        "# TYPE pathly_sse_clients_active gauge",
        f"pathly_sse_clients_active {http_snap.get('pathly_sse_clients_active', 0)}",
        # Pipeline counters
        "# HELP pathly_cost_usd_total Agent cost since server start (USD)",
        "# TYPE pathly_cost_usd_total counter",
        f"pathly_cost_usd_total {pipe['cost_usd']}",
        "# HELP pathly_tokens_total Input + output tokens since server start",
        "# TYPE pathly_tokens_total counter",
        f"pathly_tokens_total {pipe['tokens_in'] + pipe['tokens_out']}",
        "# HELP pathly_pipelines_started_total Pipeline runs initiated",
        "# TYPE pathly_pipelines_started_total counter",
        f"pathly_pipelines_started_total {pipe['pipelines_started']}",
        "# HELP pathly_pipelines_done_total Pipelines that reached DONE",
        "# TYPE pathly_pipelines_done_total counter",
        f"pathly_pipelines_done_total {pipe['pipelines_done']}",
        "# HELP pathly_feedback_loops_total Rework transitions (e.g. REVIEWING→BUILDING)",
        "# TYPE pathly_feedback_loops_total counter",
        f"pathly_feedback_loops_total {pipe['feedback_loops']}",
        "# HELP pathly_gate_failures_total Gate blocks that halted a stage",
        "# TYPE pathly_gate_failures_total counter",
        f"pathly_gate_failures_total {pipe['gate_failures']}",
    ]
    # Per-stage visit counts (labelled)
    if pipe["stage_visits"]:
        lines += [
            "# HELP pathly_stage_visits_total Entries into each FSM state",
            "# TYPE pathly_stage_visits_total counter",
        ]
        for state, count in sorted(pipe["stage_visits"].items()):
            lines.append(f'pathly_stage_visits_total{{state="{state}"}} {count}')
    # Per-agent invocation counts (labelled)
    if pipe["agent_invocations"]:
        lines += [
            "# HELP pathly_agent_invocations_total Agent invocations by role",
            "# TYPE pathly_agent_invocations_total counter",
        ]
        for agent, count in sorted(pipe["agent_invocations"].items()):
            lines.append(f'pathly_agent_invocations_total{{agent="{agent}"}} {count}')

    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")


@bp.route("/metrics/json", methods=["GET"])
def metrics_json():
    """JSON metrics — pipeline counters for Studio and dashboards."""
    from pathly_orchestrator.metrics import _collector

    with _metrics_lock:
        http_snap = dict(_metrics)
    pipe = _collector.snapshot()
    return jsonify({**http_snap, **pipe}), 200
