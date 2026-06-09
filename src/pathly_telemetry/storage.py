"""Append activity records to ~/.pathly/activity.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ACTIVITY_FILE = Path.home() / ".pathly" / "activity.jsonl"


def append_activity(
    agent: str,
    feature: str,
    summary: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    wall_seconds: int = 0,
    tool_uses: int = 0,
    cost_usd: float = 0.0,
    total_tokens: int = 0,
    model: str = "",
    adapter: str = "",
) -> None:
    ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if ACTIVITY_FILE.exists() and ACTIVITY_FILE.stat().st_size > 5 * 1024 * 1024:
        ACTIVITY_FILE.rename(ACTIVITY_FILE.with_suffix('.jsonl.bak'))
    entry: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "feature": feature,
        "summary": summary,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "wall_seconds": wall_seconds,
        "tool_uses": tool_uses,
        "cost_usd": cost_usd,
        "total_tokens": total_tokens,
    }
    if model:
        entry["model"] = model
    if adapter:
        entry["adapter"] = adapter
    with open(ACTIVITY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
