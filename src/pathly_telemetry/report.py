"""pathly-tokens CLI — display agent activity log from ~/.pathly/activity.jsonl."""

from __future__ import annotations

import json
from collections import defaultdict

from .storage import ACTIVITY_FILE

# Same prefix table as telemetry.py — infer adapter from model for legacy entries.
_ADAPTER_PREFIXES: list[tuple[tuple[str, ...], str]] = [
    (("claude-",),                   "claude"),
    (("gpt-", "o1-", "o3-", "o4-"), "codex"),
    (("gemini-",),                   "google"),
    (("copilot-",),                  "copilot"),
]


def _infer_adapter(model: str) -> str:
    m = (model or "").lower()
    for prefixes, name in _ADAPTER_PREFIXES:
        if any(m.startswith(p) for p in prefixes):
            return name
    return "unknown" if model else "n/a"


def _adapter_for(entry: dict) -> str:
    """Return adapter name: explicit field first, then inferred from model."""
    return entry.get("adapter") or _infer_adapter(entry.get("model", ""))


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

    W = 80
    print(f"\n{'-' * W}")
    print(
        f"  Pathly Agent Activity   ({len(entries)} event(s) across {len(by_feature)} feature(s))"
    )
    print(f"{'-' * W}")

    # -- Per-adapter summary ----------------------------------------------------
    by_adapter: dict[str, dict] = defaultdict(
        lambda: {"runs": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0}
    )
    for e in entries:
        adapter = _adapter_for(e)
        by_adapter[adapter]["runs"] += 1
        by_adapter[adapter]["cost_usd"] += e.get("cost_usd", 0.0)
        by_adapter[adapter]["tokens_in"] += e.get("input_tokens", 0)
        by_adapter[adapter]["tokens_out"] += e.get("output_tokens", 0)

    if len(by_adapter) > 1 or (len(by_adapter) == 1 and list(by_adapter.keys())[0] not in ("—", "unknown")):
        print("\n  >> By adapter / CLI")
        print(f"    {'Adapter':<14} {'Runs':>5}  {'Cost (USD)':>12}  {'Tokens In':>10}  {'Tokens Out':>10}")
        print(f"    {'-'*12}  {'-'*5}  {'-'*12}  {'-'*10}  {'-'*10}")
        for adapter, stats in sorted(by_adapter.items()):
            cost_str = f"${stats['cost_usd']:.4f}" if stats["cost_usd"] else "n/a"
            tok_in   = f"{stats['tokens_in']:,}" if stats["tokens_in"] else "n/a"
            tok_out  = f"{stats['tokens_out']:,}" if stats["tokens_out"] else "n/a"
            print(f"    {adapter:<14} {stats['runs']:>5}  {cost_str:>12}  {tok_in:>10}  {tok_out:>10}")

    # -- Per-feature detail -----------------------------------------------------
    total_in_all = total_out_all = 0.0
    total_cost_all = 0.0

    for feature, events in sorted(by_feature.items()):
        feat_in   = sum(e.get("input_tokens",  0)   for e in events)
        feat_out  = sum(e.get("output_tokens", 0)   for e in events)
        feat_cost = sum(e.get("cost_usd",      0.0) for e in events)
        total_in_all   += feat_in
        total_out_all  += feat_out
        total_cost_all += feat_cost

        print(f"\n  >> {feature}  ({len(events)} run(s))")
        print(
            f"    {'Timestamp':<18} {'Adapter':<10} {'Agent':<16} "
            f"{'In':>7} {'Out':>7} {'Cost':>9}  Summary"
        )
        print(
            f"    {'-'*16}  {'-'*8}  {'-'*14}  "
            f"{'-'*7}  {'-'*7}  {'-'*9}  {'-'*24}"
        )

        for e in sorted(events, key=lambda x: x.get("ts", "")):
            ts      = (e.get("ts", "") or "")[:16].replace("T", " ")
            adapter = _adapter_for(e)[:8]
            agent   = (e.get("agent", "?"))[:14]
            inp     = e.get("input_tokens",  0)
            out     = e.get("output_tokens", 0)
            cost    = e.get("cost_usd",      0.0)
            summary = (e.get("summary", "") or "")[:36]
            tok_in  = f"{inp:,}"     if inp  else "n/a"
            tok_out = f"{out:,}"     if out  else "n/a"
            cost_s  = f"${cost:.4f}" if cost else "n/a"
            print(
                f"    {ts:<18} {adapter:<10} {agent:<16} "
                f"{tok_in:>7}  {tok_out:>7}  {cost_s:>9}  {summary}"
            )

        tok_note = (
            f"{feat_in:,} in / {feat_out:,} out tokens"
            if feat_in or feat_out
            else "no token counts reported"
        )
        cost_note = f"  |  ${feat_cost:.4f}" if feat_cost else ""
        print(f"\n    Subtotal: {tok_note}{cost_note}")

    print(f"\n{'-' * W}")
    grand_tok = (
        f"{total_in_all:,.0f} in / {total_out_all:,.0f} out tokens"
        if total_in_all or total_out_all
        else "no token counts reported"
    )
    grand_cost = f"  |  ${total_cost_all:.4f} total" if total_cost_all else ""
    print(f"  Grand total: {grand_tok}{grand_cost}")
    print(f"{'-' * W}\n")
