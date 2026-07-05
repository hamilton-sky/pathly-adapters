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
    # Keep the object spanning FURTHEST into the string. For a single (possibly nested)
    # result object that is the whole top-level object; for a multi-object stream
    # (stream-json) it is the last complete object. The previous "last successful decode"
    # returned an INNER object for nested JSON (e.g. the last `modelUsage` entry), silently
    # dropping top-level fields like `total_cost_usd` / `modelUsage`.
    best: dict[str, Any] = {}
    best_end = -1
    for idx in range(len(cleaned)):
        if cleaned[idx] not in "{[":
            continue
        try:
            payload, end = decoder.raw_decode(cleaned, idx)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and end > best_end:
            best, best_end = payload, end
    return best


def _normalize_model_usage(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalize an adapter's per-model usage map to
    ``{model: {tokens_in, tokens_out, cost_usd}}``.

    Tolerant of camelCase/snake_case keys and missing fields; ``tokens_in`` folds cache
    read/creation tokens in (matching the lump ``tokens_in`` convention). Skips non-dict
    entries; never raises.
    """
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return out
    for model, u in raw.items():
        if not isinstance(u, dict):
            continue
        t_in = int(
            (u.get("inputTokens") or u.get("input_tokens") or 0)
            + (u.get("cacheReadInputTokens") or u.get("cache_read_input_tokens") or 0)
            + (u.get("cacheCreationInputTokens") or u.get("cache_creation_input_tokens") or 0)
        )
        t_out = int(u.get("outputTokens", 0) or u.get("output_tokens", 0))
        try:
            c = float(u.get("costUSD") or u.get("cost_usd") or 0.0)
        except (TypeError, ValueError):
            c = 0.0
        out[str(model)] = {"tokens_in": t_in, "tokens_out": t_out, "cost_usd": c}
    return out


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

    # Per-model usage breakdown (claude emits `modelUsage`: {model: {inputTokens,
    # outputTokens, cache*, costUSD}}). Capture it for per-model cost attribution, and use
    # it as an accuracy fallback: if the adapter reported NO lump cost/tokens but DID report
    # a per-model breakdown, derive the totals by summing it.
    model_usage = _normalize_model_usage(
        payload.get("modelUsage") or payload.get("model_usage") or {}
    )
    if model_usage:
        if not cost_usd:
            cost_usd = round(sum(m["cost_usd"] for m in model_usage.values()), 6)
        if not tokens_in:
            tokens_in = sum(m["tokens_in"] for m in model_usage.values())
        if not tokens_out:
            tokens_out = sum(m["tokens_out"] for m in model_usage.values())

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
        "model_usage": model_usage,
    }
