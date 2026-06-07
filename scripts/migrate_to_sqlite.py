"""
Migrate existing pathly/plans/ feature directories from STATE.json to SQLite.

CLI:
    python scripts/migrate_to_sqlite.py [--plans-dir PATH] [--limit N] [--dry-run]

Default --plans-dir: pathly/plans
--limit N: only process the N most recently modified features (default: all)

For each feature subdirectory (skips .archive and non-directories):
  - Imports EVENTS.jsonl into fsm_events (if present, idempotent)
  - Imports STATE.json into fsm_state (if no row exists yet)

Does NOT delete original files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _mtime(d: Path) -> float:
    try:
        return d.stat().st_mtime
    except OSError:
        return 0.0


def migrate_feature(
    feature_dir: Path,
    project_root: str,
    dry_run: bool,
) -> None:
    feature = feature_dir.name
    events_path = feature_dir / "EVENTS.jsonl"
    state_path = feature_dir / "STATE.json"

    event_count = 0
    state_status = "missing"

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

        state_status = "ok" if state_path.exists() else "missing"
        print(f"[dry-run] [{feature}]: events={event_count} state={state_status}")
        return

    from pathly_orchestrator import db as _db

    conn = _db.get_db()

    if events_path.exists():
        existing_events = _db.read_events(conn, project_root, feature)
        if existing_events:
            print(f"  [{feature}]: events=skipped ({len(existing_events)} rows already present)")
        else:
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
                    _db.append_event(conn, project_root, feature, event)
                    event_count += 1

    if state_path.exists():
        try:
            with open(state_path, encoding="utf-8") as f:
                state_dict = json.load(f)
            _db.write_state(conn, project_root, feature, state_dict)
            state_status = "ok"
        except (json.JSONDecodeError, OSError) as exc:
            state_status = f"error: {exc}"

    print(f"[{feature}]: events={event_count} state={state_status}")


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
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only migrate the N most recently modified features",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing anything",
    )
    args = parser.parse_args(argv)

    plans_dir = Path(args.plans_dir).resolve()
    if not plans_dir.is_dir():
        print(f"ERROR: plans-dir not found: {plans_dir}", file=sys.stderr)
        return 1

    # project_root is two levels up from pathly/plans/
    project_root = str(plans_dir.parent.parent)

    entries = sorted(
        (e for e in plans_dir.iterdir() if e.is_dir() and not e.name.startswith(".")),
        key=_mtime,
        reverse=True,
    )

    if args.limit is not None:
        entries = entries[: args.limit]
        print(f"Migrating {len(entries)} most recent feature(s) -> project_root={project_root}")
    else:
        print(f"Migrating {len(entries)} feature(s) -> project_root={project_root}")

    for entry in entries:
        migrate_feature(entry, project_root, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
