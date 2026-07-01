"""
pathly-back — roll back the FSM one state with confirmation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pathly_orchestrator.cli._discovery import (
    find_most_recent_state as _find_most_recent_state,
    find_topic_dir as _find_topic_dir,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pathly-back",
        description="Roll back the FSM one state with confirmation.",
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="Feature topic name (defaults to most recently modified).",
    )
    args = parser.parse_args()

    cwd = Path.cwd()

    if args.topic:
        result = _find_topic_dir(cwd, args.topic)
        if result is None:
            print(f"Topic '{args.topic}' not found in any scan root.")
            sys.exit(1)
        storage_path, flow = result
        topic = args.topic
    else:
        found = _find_most_recent_state(cwd)
        if found is None:
            print("No active features found.")
            sys.exit(1)
        storage_path, topic, flow = found

    events_file = storage_path / "EVENTS.jsonl"
    state_file = storage_path / "STATE.json"

    prior_state: str | None = None
    if events_file.exists():
        lines = [
            line.strip()
            for line in events_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("type") == "STATE_TRANSITION":
                prior_state = event.get("from")
                break

    if prior_state is None:
        print(f"No previous state to roll back to for {topic}.")
        sys.exit(0)

    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    current = state_data["current"]

    print(f"Roll back {topic}:  {current} → {prior_state}")
    print("Note: git commits and transition_actions are NOT undone by this command.")
    answer = input("Proceed? (y/n): ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)

    now_ts = datetime.now(timezone.utc).isoformat()
    new_state = {**state_data, "current": prior_state, "updated_at": now_ts}

    tmp_file = state_file.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
    tmp_file.replace(state_file)

    rollback_event = {
        "type": "STATE_ROLLBACK",
        "from": current,
        "to": prior_state,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with events_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rollback_event) + "\n")

    print(f"Rolled back {topic}: {current} → {prior_state}")
    print("Run /pathly go or pathly-ff to resume.")
    sys.exit(0)
