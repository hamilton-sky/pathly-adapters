"""HTTP client and CLI bridge for the Pathly FSM server."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_SERVER_MODULE = "pathly_orchestrator.http_server"
_HEALTH_PATH = "/health"
_NEXT_ACTION_PATH = "/next_action"
_COMPLETE_STAGE_PATH = "/complete_stage"
_RECORD_ACTIVITY_PATH = "/record_activity"


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _request_raw(
    method: str,
    path: str,
    payload: dict | None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
) -> str:
    url = _base_url(host, port) + path
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body or exc.reason
        raise RuntimeError(f"fsm-call error ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"fsm-call error: {exc.reason}") from exc


def _request_json(
    method: str,
    path: str,
    payload: dict | None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
) -> dict:
    raw = _request_raw(method, path, payload, host=host, port=port, timeout=timeout)
    if not raw.strip():
        return {}
    return json.loads(raw)


def _health_ok(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    try:
        payload = _request_json("GET", _HEALTH_PATH, None, host=host, port=port, timeout=1.0)
    except Exception:
        return False
    return payload.get("status") == "ok"


def _start_server() -> None:
    try:
        subprocess.Popen(
            [sys.executable, "-m", _SERVER_MODULE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise RuntimeError(
            "FSM server unavailable. Start it with:\n"
            "  python -m pathly_orchestrator.http_server\n"
            "(Run in a separate terminal, then retry.)"
        ) from exc


def ensure_server_running(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    if _health_ok(host=host, port=port):
        return

    _start_server()
    time.sleep(2)
    if _health_ok(host=host, port=port):
        return

    raise RuntimeError(
        "FSM server unavailable. Start it with:\n"
        "  python -m pathly_orchestrator.http_server\n"
        "(Run in a separate terminal, then retry.)"
    )


def next_action(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    ensure_server_running(host=host, port=port)
    return _request_json("POST", _NEXT_ACTION_PATH, payload, host=host, port=port)


def complete_stage(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    ensure_server_running(host=host, port=port)
    return _request_json("POST", _COMPLETE_STAGE_PATH, payload, host=host, port=port)


def record_activity(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    ensure_server_running(host=host, port=port)
    return _request_json("POST", _RECORD_ACTIVITY_PATH, payload, host=host, port=port)


def _filter_none(values: dict[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


def _add_common_net_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=DEFAULT_HOST, help="FSM host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="FSM port (default: 8765)")


def _main_next_action(args: argparse.Namespace) -> int:
    ensure_server_running(host=args.host, port=args.port)
    payload = {
        "flow": args.flow,
        "topic": args.topic,
        "project_root": args.project_root,
    }
    raw = _request_raw("POST", _NEXT_ACTION_PATH, payload, host=args.host, port=args.port)
    print(raw)
    return 0


def _main_complete_stage(args: argparse.Namespace) -> int:
    ensure_server_running(host=args.host, port=args.port)
    payload = {
        "flow": args.flow,
        "topic": args.topic,
        "project_root": args.project_root,
        "decision": args.decision,
        "resolved_files": args.resolved_file or None,
    }
    raw = _request_raw(
        "POST",
        _COMPLETE_STAGE_PATH,
        _filter_none(payload),
        host=args.host,
        port=args.port,
    )
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
        "POST",
        _RECORD_ACTIVITY_PATH,
        payload,
        host=args.host,
        port=args.port,
    )
    print(raw)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pathly-fsm-call",
        description="HTTP bridge for Pathly FSM actions and telemetry.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    next_action_parser = subparsers.add_parser(
        "next-action",
        help="Call POST /next_action.",
    )
    next_action_parser.add_argument("--flow", required=True)
    next_action_parser.add_argument("--topic", required=True)
    next_action_parser.add_argument("--project-root", required=True)
    _add_common_net_args(next_action_parser)
    next_action_parser.set_defaults(func=_main_next_action)

    complete_stage_parser = subparsers.add_parser(
        "complete-stage",
        help="Call POST /complete_stage.",
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
        "record-activity",
        help="Call POST /record_activity.",
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

    args = parser.parse_args()
    try:
        raise SystemExit(args.func(args))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
