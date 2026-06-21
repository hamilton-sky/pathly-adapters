"""Pipeline history block builder."""

from __future__ import annotations

import json
from pathlib import Path


def build_pipeline_history_block(events_path: str, max_items: int = 10) -> str:
    """Return a markdown ## Pipeline History block from AGENT_DONE events in events_path.

    Accepts either a feature directory path or a direct EVENTS.jsonl file path.
    Returns "" if the source is absent or has no AGENT_DONE lines.
    Entries are ordered oldest-first; at most max_items are included.
    """
    path = Path(events_path)
    events: list[dict] = []

    if path.is_dir():
        try:
            from pathly_orchestrator import eventlog as _ev

            all_events = _ev.read_events(events_path)
            events = [e for e in all_events if e.get("type") == "AGENT_DONE"]
        except Exception:
            return ""
    else:
        # Legacy: events_path is a direct path to EVENTS.jsonl
        try:
            if not path.exists():
                return ""
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "AGENT_DONE":
                events.append(ev)

    entries = []
    for ev in events:
        agent = ev.get("agent", "?")
        conv = ev.get("conversation", "?")
        summary = ev.get("summary") or "(no summary)"
        entries.append(f"- **{agent} (conv {conv})**: {summary}")

    if not entries:
        return ""

    entries = entries[-max_items:]
    return "\n## Pipeline History\n\n" + "\n".join(entries)
