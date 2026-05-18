"""Pathly telemetry MCP server.

Zero external dependencies — implements the MCP stdio protocol (JSON-RPC 2.0
with Content-Length framing) directly. Works with Claude Code and Codex.

Run via:  python -m pathly_telemetry
"""
from __future__ import annotations

import json
import sys

from .storage import append_activity

_MAX_BODY = 1_048_576  # 1 MiB

import os as _os
_STDIN_FD = 0
_STDOUT_FD = 1

_TOOLS = [
    {
        "name": "record_activity",
        "description": (
            "Record that a Pathly agent completed a task. "
            "Call this at the end of your work."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Your agent name (e.g. 'builder', 'reviewer')",
                },
                "feature": {
                    "type": "string",
                    "description": "Feature or task name you worked on",
                },
                "summary": {
                    "type": "string",
                    "description": "One-line summary of what you accomplished",
                },
                "input_tokens": {
                    "type": "integer",
                    "description": "Estimated input tokens (0 if unknown)",
                    "default": 0,
                },
                "output_tokens": {
                    "type": "integer",
                    "description": "Estimated output tokens (0 if unknown)",
                    "default": 0,
                },
            },
            "required": ["agent", "feature", "summary"],
        },
    }
]


def _fd_write_all(data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        n = _os.write(_STDOUT_FD, view[offset:])
        offset += n


def _fd_read_exact(n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = _os.read(_STDIN_FD, n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _fd_readline() -> bytes | None:
    buf = bytearray()
    while True:
        ch = _os.read(_STDIN_FD, 1)
        if not ch:
            return None if not buf else bytes(buf)
        buf.extend(ch)
        if ch == b"\n":
            return bytes(buf)


def _send(obj: dict) -> None:
    body = json.dumps(obj)
    encoded = body.encode("utf-8")
    header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("utf-8")
    _fd_write_all(header + encoded)


def _read_message() -> dict | None:
    headers: dict[str, str] = {}

    try:
        while True:
            raw = _fd_readline()
            if raw is None:
                return None
            line = raw.rstrip(b"\r\n").decode("utf-8", errors="replace")
            if not line:
                if not headers:
                    continue
                break
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
                return None
            if ":" in line:
                key, _, val = line.partition(":")
                headers[key.strip().lower()] = val.strip()

        try:
            length = int(headers.get("content-length", 0))
        except ValueError:
            return None
        if length <= 0 or length > _MAX_BODY:
            return None

        body_bytes = _fd_read_exact(length)
        if body_bytes is None:
            return None
        try:
            return json.loads(body_bytes.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None
    except OSError:
        return None


def _handle(req: dict) -> dict | None:
    rid = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pathly-telemetry", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": _TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "record_activity":
            try:
                append_activity(
                    agent=args["agent"],
                    feature=args["feature"],
                    summary=args.get("summary", ""),
                    input_tokens=int(args.get("input_tokens", 0)),
                    output_tokens=int(args.get("output_tokens", 0)),
                )
                text = "Activity recorded."
            except Exception as exc:
                text = f"Error recording activity: {exc}"
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": text}]},
            }

        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Unknown tool: {name}"},
        }

    # Notifications have no id — swallow silently
    if rid is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def run() -> None:
    while True:
        msg = _read_message()
        if msg is None:
            break
        response = _handle(msg)
        if response is not None:
            _send(response)
