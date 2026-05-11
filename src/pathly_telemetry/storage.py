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
) -> None:
    ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "feature": feature,
        "summary": summary,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    with open(ACTIVITY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
