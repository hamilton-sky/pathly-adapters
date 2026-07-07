"""CLI entry point for the pathly-fsm-call tool.

The HTTP client primitives live in fsm_http_client.py. This module owns argument
parsing and the `main()` entry point registered as the `pathly-fsm-call` console script.
"""

from __future__ import annotations

import argparse
import json
import sys

from .fsm_http_client import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    _ServerUnreachable,
    _filter_none,
    _inprocess,
    _request_raw,
    _CODE_QUERY_PATH,
    _COMPLETE_STAGE_PATH,
    _NEXT_ACTION_PATH,
    _RECORD_ACTIVITY_PATH,
    _RECORD_PHASE_PATH,
    ensure_server_running,
)


def _add_common_net_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="FSM host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="FSM port (default: 8765)"
    )


def _main_next_action(args: argparse.Namespace) -> int:
    payload = {
        "flow": args.flow,
        "topic": args.topic,
        "project_root": args.project_root,
    }
    try:
        ensure_server_running(host=args.host, port=args.port)
        raw = _request_raw(
            "POST", _NEXT_ACTION_PATH, payload, host=args.host, port=args.port
        )
    except _ServerUnreachable:
        print(json.dumps(_inprocess("next_action", payload)))
        return 0
    print(raw)
    return 0


def _main_complete_stage(args: argparse.Namespace) -> int:
    payload = _filter_none(
        {
            "flow": args.flow,
            "topic": args.topic,
            "project_root": args.project_root,
            "decision": args.decision,
            "resolved_files": args.resolved_file or None,
        }
    )
    try:
        ensure_server_running(host=args.host, port=args.port)
        raw = _request_raw(
            "POST", _COMPLETE_STAGE_PATH, payload, host=args.host, port=args.port
        )
    except _ServerUnreachable:
        print(json.dumps(_inprocess("complete_stage", payload)))
        return 0
    print(raw)
    return 0


def _main_record_activity(args: argparse.Namespace) -> int:
    ensure_server_running(host=args.host, port=args.port)
    payload = _filter_none(
        {
            "agent": args.agent,
            "feature": args.feature,
            "summary": args.summary,
            "conversation": args.conversation,
            "model": args.model,
            "cost_usd": args.cost_usd,
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "total_tokens": args.total_tokens,
            "tool_uses": args.tool_uses,
            "duration_ms": args.duration_ms,
            "wall_seconds": args.wall_seconds,
        }
    )
    raw = _request_raw(
        "POST", _RECORD_ACTIVITY_PATH, payload, host=args.host, port=args.port
    )
    print(raw)
    return 0


def _main_record_phase(args: argparse.Namespace) -> int:
    ensure_server_running(host=args.host, port=args.port)
    payload = _filter_none(
        {
            "feature": args.feature,
            "agent": args.agent,
            "phase": args.phase,
            "event_type": args.event_type,
            "conv": args.conv,
            "summary": args.summary,
            "project_root": getattr(args, "project_root", None),
        }
    )
    raw = _request_raw(
        "POST", _RECORD_PHASE_PATH, payload, host=args.host, port=args.port
    )
    print(raw)
    return 0


def _main_code_query(args: argparse.Namespace) -> int:
    payload = _filter_none(
        {
            "op": args.op,
            "target": args.target,
            "role": args.role,
            "scope": args.scope,
        }
    )
    try:
        ensure_server_running(host=args.host, port=args.port)
        # Code queries can shell out to a slow code-intel tool; allow more than
        # the 10s default so a legitimately-slow backend completes rather than
        # the client timing out mid-query.
        raw = _request_raw(
            "POST",
            _CODE_QUERY_PATH,
            payload,
            host=args.host,
            port=args.port,
            timeout=30.0,
        )
    except _ServerUnreachable:
        # Degrade to a safe-null envelope so the calling agent falls back to Grep
        # instead of crashing — mirrors the /code/query route's never-500 contract.
        print(
            json.dumps(
                {
                    "ok": True,
                    "result": None,
                    "backend": "none",
                    "reason": "server-unreachable",
                }
            )
        )
        return 0
    print(raw)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pathly-fsm-call",
        description="HTTP bridge for Pathly FSM actions and telemetry.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    next_action_parser = subparsers.add_parser(
        "next-action", help="Call POST /next_action."
    )
    next_action_parser.add_argument("--flow", required=True)
    next_action_parser.add_argument("--topic", required=True)
    next_action_parser.add_argument("--project-root", required=True)
    _add_common_net_args(next_action_parser)
    next_action_parser.set_defaults(func=_main_next_action)

    complete_stage_parser = subparsers.add_parser(
        "complete-stage", help="Call POST /complete_stage."
    )
    complete_stage_parser.add_argument("--flow", required=True)
    complete_stage_parser.add_argument("--topic", required=True)
    complete_stage_parser.add_argument("--project-root", required=True)
    complete_stage_parser.add_argument("--decision")
    complete_stage_parser.add_argument(
        "--resolved-file",
        action="append",
        dest="resolved_file",
        default=[],
        help="Feedback file to resolve; repeat for multiple files.",
    )
    _add_common_net_args(complete_stage_parser)
    complete_stage_parser.set_defaults(func=_main_complete_stage)

    record_activity_parser = subparsers.add_parser(
        "record-activity", help="Call POST /record_activity."
    )
    record_activity_parser.add_argument("--agent", required=True)
    record_activity_parser.add_argument("--feature", required=True)
    record_activity_parser.add_argument("--summary", required=True)
    record_activity_parser.add_argument("--conversation", type=int, default=0)
    record_activity_parser.add_argument("--model")
    record_activity_parser.add_argument("--cost-usd", type=float, dest="cost_usd")
    record_activity_parser.add_argument("--input-tokens", type=int, default=0)
    record_activity_parser.add_argument("--output-tokens", type=int, default=0)
    record_activity_parser.add_argument("--total-tokens", type=int, default=0)
    record_activity_parser.add_argument("--tool-uses", type=int, default=0)
    record_activity_parser.add_argument("--duration-ms", type=int, default=0)
    record_activity_parser.add_argument("--wall-seconds", type=int, default=0)
    _add_common_net_args(record_activity_parser)
    record_activity_parser.set_defaults(func=_main_record_activity)

    record_phase_parser = subparsers.add_parser(
        "record-phase",
        help="Call POST /record_phase (PHASE_START or PHASE_DONE event).",
    )
    record_phase_parser.add_argument("--feature", required=True)
    record_phase_parser.add_argument("--agent", required=True)
    record_phase_parser.add_argument("--phase", required=True)
    record_phase_parser.add_argument(
        "--event-type",
        required=True,
        dest="event_type",
        choices=["PHASE_START", "PHASE_DONE"],
    )
    record_phase_parser.add_argument("--conv", type=int, default=None)
    record_phase_parser.add_argument("--summary", default=None)
    record_phase_parser.add_argument(
        "--project-root", default=None, dest="project_root"
    )
    _add_common_net_args(record_phase_parser)
    record_phase_parser.set_defaults(func=_main_record_phase)

    code_query_parser = subparsers.add_parser(
        "code-query", help="Call POST /code/query (code-intelligence proxy)."
    )
    code_query_parser.add_argument(
        "--op", required=True, help="Query op: impact | callers | symbol | pattern."
    )
    code_query_parser.add_argument(
        "--target", required=True, help="File path or symbol the query is about."
    )
    code_query_parser.add_argument(
        "--role",
        default=None,
        help="Calling agent role (gates per-role tiering; Phase 8).",
    )
    code_query_parser.add_argument(
        "--scope",
        default=None,
        help="Feature/goal scope key for caching and board logging.",
    )
    _add_common_net_args(code_query_parser)
    code_query_parser.set_defaults(func=_main_code_query)

    args = parser.parse_args()
    try:
        raise SystemExit(args.func(args))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
