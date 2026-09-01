"""
pathly-back — roll back the FSM one state with confirmation.

DB-first (state-one-authority): the prior state comes from the DB event log and
the rollback is written DB-first via eventlog (which also refreshes the
STATE.json export) — no direct mirror reads.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from pathly_orchestrator import eventlog
from pathly_orchestrator.cli._compiled import (
    exit_no_features as _exit_no_features,
    exit_topic_not_found as _exit_topic_not_found,
)
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
            _exit_topic_not_found(cwd, args.topic, "roll back")
        storage_path, flow = result
        topic = args.topic
    else:
        found = _find_most_recent_state(cwd)
        if found is None:
            _exit_no_features(cwd, "roll back")
        storage_path, topic, flow = found

    prior_state: str | None = None
    for event in reversed(eventlog.read_events(str(storage_path))):
        if event.get("type") == "STATE_TRANSITION":
            prior_state = event.get("from")
            break

    if prior_state is None:
        print(f"No previous state to roll back to for {topic}.")
        sys.exit(0)

    state_data = eventlog.read_state(str(storage_path))
    if state_data is None:
        print(f"No recorded state for {topic} in the DB.")
        sys.exit(1)
    current = state_data["current"]

    print(f"Roll back {topic}:  {current} → {prior_state}")
    print("Note: git commits and transition_actions are NOT undone by this command.")
    answer = input("Proceed? (y/n): ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)

    now_ts = datetime.now(timezone.utc).isoformat()
    new_state = {**state_data, "current": prior_state, "updated_at": now_ts}

    # A rollback is intentionally a BACKWARD move, so bypass write_state's
    # forward-transition validation via its documented raw-writer alias —
    # DB first, then the STATE.json export (same path every transition takes).
    eventlog.write_state.__wrapped__(  # type: ignore[attr-defined]
        storage_path, storage_path.name, new_state
    )

    rollback_event = {
        "type": "STATE_ROLLBACK",
        "from": current,
        "to": prior_state,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    eventlog.append_event(str(storage_path), rollback_event)

    print(f"Rolled back {topic}: {current} → {prior_state}")
    print("Run /pathly go or pathly-ff to resume.")
    sys.exit(0)
