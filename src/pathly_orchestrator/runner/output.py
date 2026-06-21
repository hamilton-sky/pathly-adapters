"""Parse and extract JSON output from adapter subprocesses."""

from __future__ import annotations

import json
import re
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _extract_json_payload(raw_output: str) -> dict[str, Any]:
    cleaned = _ANSI_RE.sub("", raw_output or "").strip()
    if not cleaned:
        return {}
    decoder = json.JSONDecoder()
    last: dict[str, Any] = {}
    for idx in range(len(cleaned)):
        if cleaned[idx] not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned, idx)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            last = payload
    return last


def parse_result(adapter: str, raw_output: str) -> dict[str, Any]:
    payload = _extract_json_payload(raw_output)
    if adapter == "codex":
        cost = payload.get("cost_usd", payload.get("cost", 0.0))
        session_id = payload.get("session_id") or payload.get("sessionId")
    else:
        cost = (
            payload.get("cost_usd")
            or payload.get("total_cost_usd")
            or payload.get("totalCost")
            or payload.get("total_cost")
            or 0.0
        )
        session_id = payload.get("session_id") or payload.get("sessionId")
    try:
        cost_usd = float(cost or 0.0)
    except (TypeError, ValueError):
        cost_usd = 0.0

    # Extract AskUserQuestion denial if present
    permission_denials = payload.get("permission_denials") or []
    ask_user_question = None
    for denial in (permission_denials if isinstance(permission_denials, list) else []):
        if isinstance(denial, dict) and denial.get("tool_name") == "AskUserQuestion":
            ask_user_question = denial
            break

    usage = payload.get("usage") or payload.get("inputUsage") or {}
    tokens_in = int(
        (usage.get("input_tokens") or usage.get("inputTokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
    )
    tokens_out = int(usage.get("output_tokens", 0) or usage.get("outputTokens", 0))
    messages = payload.get("messages", [])
    tool_uses = sum(
        1
        for msg in messages
        for block in (
            msg.get("content", []) if isinstance(msg.get("content"), list) else []
        )
        if isinstance(block, dict) and block.get("type") == "tool_use"
    )

    return {
        "cost_usd": cost_usd,
        "session_id": session_id or None,
        "ask_user_question": ask_user_question,
        "result": payload.get("result", ""),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tool_uses": tool_uses,
    }
