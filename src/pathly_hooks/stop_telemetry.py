"""Stop hook: patch the last AGENT_DONE in EVENTS.jsonl with real session cost.

Claude Code fires this when the model stops. The payload on stdin contains
session usage data (tokens, cost). We find the most-recently-modified
EVENTS.jsonl under $PATHLY_PROJECT_ROOT/pathly/plans/ and patch the last
AGENT_DONE event with real counts.

Exits 0 always — telemetry failure must never block the user.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _find_active_events_file(project_root: str) -> Path | None:
    """Return the most recently modified EVENTS.jsonl under pathly/plans/."""
    plans = Path(project_root) / "pathly" / "plans"
    if not plans.exists():
        return None
    candidates = [p for p in plans.rglob("EVENTS.jsonl") if ".archive" not in p.parts]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _patch_last_agent_done(
    events_file: Path,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
) -> bool:
    """Patch the last AGENT_DONE line in EVENTS.jsonl. Returns True if patched."""
    try:
        lines = events_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "AGENT_DONE":
            # Only patch if values are still 0 (don't overwrite runner.py data)
            if event.get("tokens_in", 0) == 0 and event.get("cost_usd", 0.0) == 0.0:
                event["tokens_in"] = tokens_in
                event["tokens_out"] = tokens_out
                event["cost_usd"] = round(cost_usd, 6)
                lines[i] = json.dumps(event)
                # Atomic write
                tmp = events_file.with_suffix(".tmp")
                try:
                    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    tmp.replace(events_file)
                    return True
                except OSError:
                    tmp.unlink(missing_ok=True)
            return False  # already has data, skip
    return False


def main() -> None:
    # Read stop hook payload
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    # Extract usage — try multiple field layouts (Claude Code varies by version)
    usage = payload.get("usage") or {}
    tokens_in = int(
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )
    tokens_out = int(usage.get("output_tokens", 0))
    cost_usd = float(
        payload.get("total_cost_usd")
        or payload.get("cost_usd")
        or payload.get("totalCostUsd")
        or 0.0
    )

    # Nothing useful — exit cleanly
    if tokens_in == 0 and cost_usd == 0.0:
        sys.exit(0)

    project_root = os.environ.get("PATHLY_PROJECT_ROOT", "")
    if not project_root:
        sys.exit(0)

    events_file = _find_active_events_file(project_root)
    if not events_file:
        sys.exit(0)

    _patch_last_agent_done(events_file, tokens_in, tokens_out, cost_usd)
    sys.exit(0)


if __name__ == "__main__":
    main()
