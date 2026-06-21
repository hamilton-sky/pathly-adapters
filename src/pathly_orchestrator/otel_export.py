import json
import logging
import os
import secrets
import threading
import urllib.request
from datetime import datetime
from importlib.metadata import version as _pkg_version

logger = logging.getLogger(__name__)

_STATUS_OK = 1
_STATUS_ERROR = 2


def _infer_vendor(model: str) -> str:
    """Return provider slug from model name prefix, or 'unknown'."""
    from pathly_orchestrator.http_server.telemetry_registry import _ADAPTER_PREFIXES

    for prefixes, slug in _ADAPTER_PREFIXES:
        if any(model.startswith(p) for p in prefixes):
            return slug
    return "unknown"


def _service_version() -> str:
    try:
        return _pkg_version("pathly-adapters")
    except Exception:
        return "unknown"


def _build_span_payload(event: dict) -> dict:
    trace_id = event.get("trace_id", "") or secrets.token_hex(16)
    span_id = event.get("span_id", "") or secrets.token_hex(8)
    agent = event.get("agent", "")
    feature = event.get("feature", "")
    vendor = event.get("provider", "") or _infer_vendor(str(event.get("model", "")))

    ts_str = event.get("ts", "")
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        start_ns = int(dt.timestamp() * 1_000_000_000)
    except Exception:
        start_ns = 0
    wall = event.get("wall_seconds", 0) or 0
    end_ns = start_ns + int(wall * 1_000_000_000)

    result = str(event.get("result", "")).lower()
    status_code = _STATUS_OK if result in {"pass", "done"} else _STATUS_ERROR

    tokens_in = event.get("tokens_in", 0) or 0
    tokens_out = event.get("tokens_out", 0) or 0
    total = event.get("total_tokens", 0) or 0
    if tokens_in == 0 and tokens_out == 0 and total:
        tokens_in = total

    attributes = [
        {"key": "gen_ai.agent.name", "value": {"stringValue": agent}},
        {"key": "gen_ai.workflow.name", "value": {"stringValue": feature}},
        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": tokens_in}},
        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": tokens_out}},
        {
            "key": "gen_ai.request.model",
            "value": {"stringValue": str(event.get("model", ""))},
        },
        {
            "key": "gen_ai.conversation.id",
            "value": {"stringValue": str(event.get("conversation", ""))},
        },
        {
            "key": "pathly.cost_usd",
            "value": {"doubleValue": float(event.get("cost_usd", 0.0) or 0.0)},
        },
        {
            "key": "pathly.tool_uses",
            "value": {"intValue": int(event.get("tool_uses", 0) or 0)},
        },
        {
            "key": "pathly.result",
            "value": {"stringValue": str(event.get("result", ""))},
        },
        {"key": "gen_ai.vendor", "value": {"stringValue": vendor}},
    ]

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "pathly"}},
                        {
                            "key": "service.version",
                            "value": {"stringValue": _service_version()},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "pathly.orchestrator"},
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "name": f"invoke_agent {agent}",
                                "kind": 1,
                                "startTimeUnixNano": str(start_ns),
                                "endTimeUnixNano": str(end_ns),
                                "attributes": attributes,
                                "status": {"code": status_code},
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _build_log_payload(event: dict, trace_id: str, span_id: str) -> dict:
    ts_str = event.get("ts", "")
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        time_ns = int(dt.timestamp() * 1_000_000_000)
    except Exception:
        time_ns = 0

    summary = str(event.get("summary", ""))[:65535]
    return {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "pathly"}}
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {"name": "pathly.orchestrator"},
                        "logRecords": [
                            {
                                "timeUnixNano": str(time_ns),
                                "traceId": trace_id,
                                "spanId": span_id,
                                "body": {"stringValue": summary},
                                "severityNumber": 9,
                                "severityText": "INFO",
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _do_export(event: dict, endpoint: str) -> None:
    span_payload = _build_span_payload(event)
    trace_id = span_payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"]
    span_id = span_payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["spanId"]
    agent = event.get("agent", "")
    feature = event.get("feature", "")

    body = json.dumps(span_payload).encode()
    req = urllib.request.Request(
        f"{endpoint}/v1/traces",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.debug(
                "otel span exported: %s %s (status=%s)", agent, feature, resp.status
            )
    except Exception as exc:
        logger.warning("otel export failed: %s", exc)
        return

    summary = event.get("summary", "") or ""
    if summary.strip():
        log_payload = _build_log_payload(event, trace_id, span_id)
        log_body = json.dumps(log_payload).encode()
        log_req = urllib.request.Request(
            f"{endpoint}/v1/logs",
            data=log_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(log_req, timeout=5) as resp:
                logger.debug(
                    "otel log exported: %s %s (status=%s)", agent, feature, resp.status
                )
        except Exception as exc:
            logger.warning("otel log export failed: %s", exc)


def export_span_async(event: dict) -> None:
    endpoint = os.environ.get("PATHLY_OTEL_ENDPOINT", "").strip()
    if not endpoint:
        return
    t = threading.Thread(target=_do_export, args=(event, endpoint), daemon=True)
    t.start()


def cli_main() -> None:
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="pathly-otel-export")
    parser.add_argument("--feature", required=True, help="feature name")
    parser.add_argument("--endpoint", required=True, help="OTLP endpoint base URL")
    parser.add_argument("--project-root", default=None, help="path to project root")
    parser.add_argument(
        "--dry-run", action="store_true", help="print without sending HTTP requests"
    )
    args = parser.parse_args()

    project_root = args.project_root if args.project_root is not None else os.getcwd()
    feature_dir = Path(project_root) / "pathly" / "plans" / args.feature

    if not feature_dir.exists():
        print(f"error: feature directory not found: {feature_dir}", file=sys.stderr)
        sys.exit(1)

    from pathly_orchestrator import db as _db

    conn = _db.get_db()
    events = _db.read_events(conn, project_root, args.feature)
    agent_done_events = [e for e in events if e.get("type") == "AGENT_DONE"]

    exported_count = 0
    failures = 0

    for event in agent_done_events:
        agent = event.get("agent", "?")
        seq = event.get("seq", "?")
        if args.dry_run:
            print(f"dry-run: would export span: invoke_agent {agent} (seq={seq})")
            exported_count += 1
            continue
        try:
            _do_export(event, args.endpoint)
            print(f"exported span: invoke_agent {agent} (seq={seq})")
            exported_count += 1
        except Exception as exc:
            logger.warning("export failed for seq=%s: %s", seq, exc)
            failures += 1

    print(f"done: {exported_count} spans exported")

    if failures:
        sys.exit(1)
    sys.exit(0)
