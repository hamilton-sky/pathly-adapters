"""
pathly-back — roll back the FSM one state with confirmation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


_SCAN_ROOTS = [
    ("pathly/plans", "team"),
    ("pathly/debugs", "debug"),
    ("pathly/explorations", "explore"),
]


def _find_most_recent_state(cwd: Path) -> tuple[Path, str, str] | None:
    best_mtime = -1.0
    best: tuple[Path, str, str] | None = None

    for root_rel, flow in _SCAN_ROOTS:
        root = cwd / root_rel
        if not root.is_dir():
            continue
        for state_file in root.glob("*/STATE.json"):
            if ".archive" in str(state_file):
                continue
            mtime = state_file.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best = (state_file.parent, state_file.parent.name, flow)

    return best


def _find_topic_dir(cwd: Path, topic: str) -> tuple[Path, str] | None:
    for root_rel, flow in _SCAN_ROOTS:
        root = cwd / root_rel
        candidate = root / topic
        if (candidate / "STATE.json").exists():
            return candidate, flow
    return None


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
