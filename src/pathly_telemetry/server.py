"""Pathly telemetry MCP server.

Uses the official MCP Python SDK for correct protocol handling.

Run via:  python -m pathly_telemetry
"""

from __future__ import annotations

import asyncio
import json

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .storage import append_activity

server = Server("pathly-telemetry")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="record_activity",
            description=(
                "Record that a Pathly agent completed a task. "
                "Call this at the end of your work."
            ),
            inputSchema={
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
        )
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: dict | None = None
) -> list[types.TextContent]:
    args = arguments or {}
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
        return [types.TextContent(type="text", text=text)]

    raise ValueError(f"Unknown tool: {name}")


async def _amain() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run() -> None:
    asyncio.run(_amain())
