"""Parse and extract JSON output from adapter subprocesses."""

from __future__ import annotations

import json
import re
from typing import Any, Generator

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
            + (
                u.get("cacheCreationInputTokens")
                or u.get("cache_creation_input_tokens")
                or 0
            )
        )
        t_out = int(u.get("outputTokens", 0) or u.get("output_tokens", 0))
        try:
            c = float(u.get("costUSD") or u.get("cost_usd") or 0.0)
        except (TypeError, ValueError):
            c = 0.0
        out[str(model)] = {"tokens_in": t_in, "tokens_out": t_out, "cost_usd": c}
    return out


def _recover_truncated_claude_usage(raw_output: str) -> tuple[float, int, int]:
    """Regex-recover cost + tokens from a claude ``--output-format=json`` envelope whose LEADING
    brace was dropped.

    A large run (heavy cache reads → a big envelope) overflows the PTY tail buffer
    (``terminal.ts`` keeps only the last ~500 chunks), so the retained tail starts mid-object.
    ``_extract_json_payload`` then falls back to an INNER object (a lone ``modelUsage`` entry) with
    no top-level ``total_cost_usd`` and no ``modelUsage`` map — and ``parse_result`` reads
    cost=0 / tokens=0 despite the numbers being present as text. Recover them by regex: the last
    ``total_cost_usd`` (or the sum of per-model ``costUSD``), and the summed camelCase ``modelUsage``
    token fields (the top-level ``usage`` block is snake_case, so this never double-counts).
    Returns ``(cost_usd, tokens_in, tokens_out)``; zeros when nothing is recoverable.
    """
    text = raw_output or ""

    def _floats(pat: str) -> list[float]:
        vals: list[float] = []
        for x in re.findall(pat, text):
            try:
                vals.append(float(x))
            except ValueError:
                continue
        return vals

    def _sum_ints(pat: str) -> int:
        total = 0
        for x in re.findall(pat, text):
            try:
                total += int(x)
            except ValueError:
                continue
        return total

    tc = _floats(r'"total_cost_usd"\s*:\s*([0-9.eE+-]+)')
    cost = tc[-1] if tc else round(sum(_floats(r'"costUSD"\s*:\s*([0-9.eE+-]+)')), 6)
    tin = (
        _sum_ints(r'"inputTokens"\s*:\s*([0-9]+)')
        + _sum_ints(r'"cacheReadInputTokens"\s*:\s*([0-9]+)')
        + _sum_ints(r'"cacheCreationInputTokens"\s*:\s*([0-9]+)')
    )
    tout = _sum_ints(r'"outputTokens"\s*:\s*([0-9]+)')
    return cost, tin, tout


def _iter_json_objects(raw: str) -> Generator[dict[str, Any], None, None]:
    """Yield every top-level JSON object in a (possibly JSONL) string.

    Tolerant of ANSI escapes and non-JSON text interleaved between objects (codex
    `exec --json` interleaves progress lines with JSONL events). Only attempts a
    decode at a `{`/`[` character — matching ``_extract_json_payload``'s scan — and
    skips forward past each decoded object's span so a nested object is never
    re-yielded as a sibling top-level event.
    """
    cleaned = _ANSI_RE.sub("", raw or "").strip()
    if not cleaned:
        return
    decoder = json.JSONDecoder()
    idx = 0
    n = len(cleaned)
    while idx < n:
        if cleaned[idx] not in "{[":
            idx += 1
            continue
        try:
            payload, end = decoder.raw_decode(cleaned, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        if isinstance(payload, dict):
            yield payload
        idx = max(end, idx + 1)


def _codex_usage(raw_output: str) -> tuple[int, int]:
    """Scan codex `exec --json` JSONL output for a token-usage event.

    DEFENSIVE: codex's usage shape varies by CLI version (unconfirmed offline) — tolerate
    a top-level ``usage`` object, a nested ``info.total_token_usage``, or a typed
    ``token_count``/``token_usage`` event whose own fields ARE the usage. Field names are
    tried in both snake_case and camelCase. Keeps the LAST non-zero usage event seen
    (later events carry the running/final total). Returns (0, 0) when none is found.
    """
    tokens_in = tokens_out = 0
    for obj in _iter_json_objects(raw_output):
        usage = obj.get("usage")
        if not isinstance(usage, dict):
            info = obj.get("info")
            if isinstance(info, dict) and isinstance(
                info.get("total_token_usage"), dict
            ):
                usage = info["total_token_usage"]
            elif obj.get("type") in ("token_count", "token_usage"):
                usage = obj
        if not isinstance(usage, dict):
            continue
        u_in = int(
            (
                usage.get("input_tokens")
                or usage.get("prompt_tokens")
                or usage.get("inputTokens")
                or 0
            )
            + (
                usage.get("cached_input_tokens")
                or usage.get("cache_read_input_tokens")
                or 0
            )
        )
        u_out = int(
            (
                usage.get("output_tokens")
                or usage.get("completion_tokens")
                or usage.get("outputTokens")
                or 0
            )
            # Reasoning tokens ARE billed as output (o-series / gpt-5 with reasoning). The real
            # codex `turn.completed` usage carries them separately as reasoning_output_tokens —
            # add them or a reasoning-heavy run undercounts (verified against live codex output).
            + (
                usage.get("reasoning_output_tokens")
                or usage.get("reasoning_tokens")
                or 0
            )
        )
        if u_in or u_out:
            tokens_in, tokens_out = u_in, u_out
    return tokens_in, tokens_out


# ── TOKEN-COUNT STRATEGY REGISTRY (per adapter) — the ONE place token counting lives ──
# Tokens are the UNIVERSAL, must-capture primitive; cost is derived SEPARATELY (db/pricing.py,
# the cost registry). Each engine reports usage differently — or not at all (antigravity/agy) —
# so extraction is a strategy per adapter. Adding a new engine = adding one entry to
# _TOKEN_STRATEGIES below; nothing else changes.


def _claude_tokens(payload: dict[str, Any], raw_output: str) -> tuple[int, int]:
    """Claude: lump ``usage`` from the result envelope (input + cache, output), with the
    per-model ``modelUsage`` breakdown as a fallback when the lump is absent/partial."""
    usage = payload.get("usage") or payload.get("inputUsage") or {}
    tin = int(
        (usage.get("input_tokens") or usage.get("inputTokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
    )
    tout = int(usage.get("output_tokens", 0) or usage.get("outputTokens", 0))
    if not tin or not tout:
        mu = _normalize_model_usage(
            payload.get("modelUsage") or payload.get("model_usage") or {}
        )
        if mu:
            tin = tin or sum(m["tokens_in"] for m in mu.values())
            tout = tout or sum(m["tokens_out"] for m in mu.values())
    return tin, tout


def _codex_tokens(payload: dict[str, Any], raw_output: str) -> tuple[int, int]:
    """Codex ``exec --json``: token usage from the JSONL event stream."""
    return _codex_usage(raw_output)


def estimate_tokens_from_text(text: str) -> int:
    """Rough LOCAL token count for engines that report no usage: ~4 chars/token (an English
    heuristic; deliberately provider-neutral). Swap for a real tokenizer per-adapter later.
    """
    t = _ANSI_RE.sub("", text or "").strip()
    return (len(t) + 3) // 4 if t else 0


def _agy_tokens(payload: dict[str, Any], raw_output: str) -> tuple[int, int]:
    """Antigravity / agy emits NO usage telemetry — ESTIMATE output tokens from the response
    text with a local tokenizer, so even this engine yields a token count (marked estimated
    downstream). The prompt isn't in stdout, so input stays 0 until the gate threads it.
    """
    return 0, estimate_tokens_from_text(raw_output)


# adapter (lowercased) → token-extraction strategy. Unknown/unlisted → the claude/generic
# envelope parser. ``copilot`` is a multi-provider proxy with no usage of its own.
_TOKEN_STRATEGIES: dict[str, Any] = {
    "claude": _claude_tokens,
    "codex": _codex_tokens,
    "antigravity": _agy_tokens,
    "agy": _agy_tokens,
    "gemini": _agy_tokens,
}


def extract_tokens(
    adapter: str, payload: dict[str, Any], raw_output: str
) -> tuple[int, int]:
    """The single entry point for per-adapter token counting (Strategy A). Returns
    ``(tokens_in, tokens_out)``. Dispatches to the adapter's strategy in _TOKEN_STRATEGIES;
    an unknown adapter falls back to the claude/generic envelope parser. Never raises.
    """
    fn = _TOKEN_STRATEGIES.get((adapter or "claude").strip().lower(), _claude_tokens)
    try:
        return fn(payload, raw_output)
    except Exception:
        return 0, 0


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

    # Tokens — Strategy A: the per-adapter token registry (extract_tokens). Each engine's
    # extraction (incl. claude's modelUsage token-fallback + codex JSONL + agy estimate) lives
    # in its strategy above; adapter dispatch is no longer inlined here.
    tokens_in, tokens_out = extract_tokens(adapter, payload, raw_output)

    # Per-model usage breakdown (claude emits `modelUsage`). Kept for per-model attribution and
    # a COST fallback only: when the CLI reported no lump cost but a per-model breakdown, sum it.
    # Token totals come from the strategy above (cost is a separate concern — Strategy B,
    # db/pricing.py).
    model_usage = _normalize_model_usage(
        payload.get("modelUsage") or payload.get("model_usage") or {}
    )
    if model_usage and not cost_usd:
        cost_usd = round(sum(m["cost_usd"] for m in model_usage.values()), 6)

    # Truncation recovery (claude/generic): a large envelope overflows the PTY tail buffer so
    # _extract_json_payload returns an inner object with no usable top-level fields — cost/tokens
    # then read 0 even though the numbers are present as text. Recover by regex. Fires ONLY when
    # the structured parse found nothing, so it never double-counts. (codex has its own JSONL path.)
    if adapter != "codex" and (cost_usd <= 0 or (tokens_in + tokens_out) == 0):
        _rc, _rin, _rout = _recover_truncated_claude_usage(raw_output)
        if cost_usd <= 0 and _rc > 0:
            cost_usd = _rc
        if (tokens_in + tokens_out) == 0 and (_rin or _rout):
            tokens_in, tokens_out = _rin, _rout

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
