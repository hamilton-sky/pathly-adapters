"""pathly-tokens CLI — display agent activity log from ~/.pathly/activity.jsonl."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .storage import ACTIVITY_FILE


def main() -> None:
    if not ACTIVITY_FILE.exists():
        print(
            "No activity recorded yet.\n"
            "Run  pathly-setup --apply  then use your agents — "
            "they'll call record_activity when each task is done."
        )
        return

    entries: list[dict] = []
    with open(ACTIVITY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("Activity log is empty.")
        return

    by_feature: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_feature[e.get("feature", "unknown")].append(e)

    W = 72
    print(f"\n{'─' * W}")
    print(f"  Pathly Agent Activity Log   ({len(entries)} event(s) across {len(by_feature)} feature(s))")
    print(f"{'─' * W}")

    total_in_all = total_out_all = 0

    for feature, events in sorted(by_feature.items()):
        feat_in = sum(e.get("input_tokens", 0) for e in events)
        feat_out = sum(e.get("output_tokens", 0) for e in events)
        total_in_all += feat_in
        total_out_all += feat_out

        print(f"\n  ▸ {feature}  ({len(events)} run(s))")
        print(f"    {'Timestamp':<18} {'Agent':<18} {'In':>7} {'Out':>7}  Summary")
        print(f"    {'─'*16}  {'─'*16}  {'─'*7}  {'─'*7}  {'─'*24}")

        for e in sorted(events, key=lambda x: x.get("ts", "")):
            ts = (e.get("ts", "") or "")[:16].replace("T", " ")
            agent = (e.get("agent", "?"))[:16]
            inp = e.get("input_tokens", 0)
            out = e.get("output_tokens", 0)
            summary = (e.get("summary", "") or "")[:40]
            tok_in = str(inp) if inp else "—"
            tok_out = str(out) if out else "—"
            print(f"    {ts:<18} {agent:<18} {tok_in:>7}  {tok_out:>7}  {summary}")

        tok_note = (
            f"{feat_in:,} in / {feat_out:,} out tokens"
            if feat_in or feat_out
            else "no token counts reported"
        )
        print(f"\n    Subtotal: {tok_note}")

    print(f"\n{'─' * W}")
    grand = (
        f"{total_in_all:,} in / {total_out_all:,} out tokens"
        if total_in_all or total_out_all
        else "no token counts reported (agents passed 0)"
    )
    print(f"  Grand total: {grand}")
    print(f"{'─' * W}\n")
