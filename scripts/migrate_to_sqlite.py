"""
Migrate existing pathly/plans/ feature directories from .json/.jsonl files to SQLite.

CLI:
    python scripts/migrate_to_sqlite.py [--plans-dir PATH] [--dry-run]

Default --plans-dir: pathly/plans
For each feature subdirectory (skips .archive and non-directories):
  - Imports EVENTS.jsonl into fsm_events (idempotent within a run)
  - Imports STATE.json into fsm_state (if no row exists yet)
  - Imports RUNNER_STATE.json into runner_state (if no row exists yet)

Does NOT delete original files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def migrate_feature(feature_dir: Path, dry_run: bool) -> None:
    feature = feature_dir.name

    events_path = feature_dir / "EVENTS.jsonl"
    state_path = feature_dir / "STATE.json"
    runner_path = feature_dir / "RUNNER_STATE.json"

    event_count = 0
    state_status = "missing"
    runner_status = "missing"

    if dry_run:
        if events_path.exists():
            valid = 0
            with open(events_path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                        valid += 1
                    except json.JSONDecodeError:
                        print(f"  [WARN] {feature}/EVENTS.jsonl line {lineno}: malformed JSON, would skip")
            event_count = valid

        if state_path.exists():
            state_status = "ok"
        if runner_path.exists():
            runner_status = "ok"

        print(f"[dry-run] [{feature}]: events={event_count} state={state_status} runner={runner_status}")
        return

    # Live run — import into SQLite
    from pathly_orchestrator import db as _db

    conn = _db.get_db(feature_dir)

    if events_path.exists():
        seen: set[tuple[str, str]] = set()
        with open(events_path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print(f"  [WARN] {feature}/EVENTS.jsonl line {lineno}: malformed JSON, skipping")
                    continue
                ts = event.get("ts", "")
                etype = event.get("type", "")
                key = (ts, etype)
                if key in seen:
                    continue
                seen.add(key)
                _db.append_event(conn, feature, event)
                event_count += 1

    if state_path.exists():
        existing = _db.read_state(conn, feature)
        if existing is None:
            try:
                with open(state_path, encoding="utf-8") as f:
                    state_dict = json.load(f)
                _db.write_state(conn, feature, state_dict)
                state_status = "ok"
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [WARN] {feature}/STATE.json: could not import — {exc}")
        else:
            state_status = "ok"

    if runner_path.exists():
        existing_runner = _db.read_runner_state(conn, feature)
        if existing_runner is None:
            try:
                with open(runner_path, encoding="utf-8") as f:
                    runner_dict = json.load(f)
                _db.write_runner_state(conn, feature, runner_dict)
                runner_status = "ok"
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  [WARN] {feature}/RUNNER_STATE.json: could not import — {exc}")
        else:
            runner_status = "ok"

    print(f"[{feature}]: events={event_count} state={state_status} runner={runner_status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate pathly/plans/ feature dirs from .json/.jsonl to SQLite"
    )
    parser.add_argument(
        "--plans-dir",
        default="pathly/plans",
        help="Root directory containing feature subdirs (default: pathly/plans)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing anything",
    )
    args = parser.parse_args(argv)

    plans_dir = Path(args.plans_dir)
    if not plans_dir.is_dir():
        print(f"ERROR: plans-dir not found: {plans_dir}", file=sys.stderr)
        return 1

    for entry in sorted(plans_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        migrate_feature(entry, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
