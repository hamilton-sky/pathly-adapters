"""
pathly-log — readable timeline of FSM events for the active or named feature.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pathly_orchestrator.cli._compiled import (
    exit_no_features as _exit_no_features,
    exit_topic_not_found as _exit_topic_not_found,
)
from pathly_orchestrator.cli._discovery import (
    find_most_recent_state as _find_most_recent_state,
    find_topic_dir as _find_topic_dir,
)

_SEP = "─" * 57


def _ts(event: dict) -> str:
    raw = event.get("ts") or event.get("timestamp")
    if not raw:
        return "?"
    try:
        trimmed = raw[:19]
        dt = datetime.fromisoformat(trimmed)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return raw[:8] if len(raw) >= 8 else raw


def _render_event(event: dict) -> str:
    etype = event.get("type", "UNKNOWN")
    time_str = _ts(event)

    skip_keys = {"type", "ts", "timestamp"}

    if etype == "STATE_TRANSITION":
        frm = event.get("from", "?")
        to = event.get("to", "?")
        return f"  {time_str}  {etype:<22}  {frm} → {to}"

    if etype == "STATE_ROLLBACK":
        frm = event.get("from", "?")
        to = event.get("to", "?")
        return f"  {time_str}  {etype:<22}  {frm} → {to}"

    if etype == "DECIDE_ROUTING":
        chosen = event.get("chosen", "?")
        decision_input = event.get("decision_input", "")
        return (
            f'  {time_str}  {etype:<22}  chosen: {chosen}  (input: "{decision_input}")'
        )

    if etype == "NEEDS_CONTEXT":
        count = event.get("count", "?")
        return f"  {time_str}  {etype:<22}  count: {count}"

    if etype == "FEEDBACK_RESOLVED":
        fname = event.get("file", "?")
        agent = event.get("agent", "?")
        return f"  {time_str}  {etype:<22}  {fname}  agent: {agent}"

    extras = "  ".join(f"{k}: {v}" for k, v in event.items() if k not in skip_keys)
    return f"  {time_str}  {etype:<22}  {extras}"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pathly-log",
        description="Show FSM event log for a Pathly feature.",
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="Feature topic name (defaults to most recently modified).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Show full event history (default: last 20).",
    )
    args = parser.parse_args()

    cwd = Path.cwd()

    if args.topic:
        result = _find_topic_dir(cwd, args.topic)
        if result is None:
            _exit_topic_not_found(cwd, args.topic, "show")
        storage_path, flow = result
        topic = args.topic
    else:
        found = _find_most_recent_state(cwd)
        if found is None:
            _exit_no_features(cwd, "show")
        storage_path, topic, flow = found

    # pathly:allow-mirror-read: human CLI log display reads the exported log directly (DB-less cwd)
    events_file = storage_path / "EVENTS.jsonl"
    if not events_file.exists():
        print("No events recorded.")
        sys.exit(0)

    lines = [
        line.strip()
        for line in events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events: list[dict] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except Exception:
            continue

    total = len(events)
    limit = 20
    if args.show_all:
        displayed = events
    else:
        displayed = events[-limit:]

    print(_SEP)
    print(f"  Pathly log · {topic} · {flow}")
    print(_SEP)

    for event in displayed:
        print(_render_event(event))

    print(_SEP)
    shown = len(displayed)
    if args.show_all or total <= limit:
        print(f"  Showing all {total} events.")
    else:
        print(f"  Showing last {shown} of {total} events. Use --all for full history.")
    sys.exit(0)
