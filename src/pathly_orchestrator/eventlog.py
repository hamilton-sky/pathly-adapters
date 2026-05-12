"""
EventLog — read/write EVENTS.jsonl and STATE.json.

The LLM writes these files directly using its Write/Bash tools.
This module provides:
  - append_event(feature, event_dict)  — append one line to EVENTS.jsonl
  - write_state(feature, state_dict)   — overwrite STATE.json
  - read_events(feature)               — return list of event dicts
  - summary(feature)                   — print token/cost table (Bash-callable)

CLI usage (called by LLM via Bash or by the retro skill):
  python -m pathly_orchestrator.eventlog summary security-fixes
  python -m pathly_orchestrator.eventlog events security-fixes
"""

from __future__ import annotations
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from pathly_orchestrator.state import VALID_STATES, TRANSITIONS

_APPEND_LOCK = threading.Lock()


def _plans_dir() -> Path:
    return Path("plans")


def _feature_dir(feature: str) -> Path:
    return _plans_dir() / feature


def _events_path(feature: str) -> Path:
    return _feature_dir(feature) / "EVENTS.jsonl"


def _state_path(feature: str) -> Path:
    return _feature_dir(feature) / "STATE.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_event(feature: str, event: dict) -> None:
    if event.get("type") == "STATE_TRANSITION":
        to_state = event.get("to")
        if to_state is not None and to_state not in VALID_STATES:
            raise ValueError(
                f"Invalid state in STATE_TRANSITION: {to_state!r}. "
                f"Must be one of {sorted(VALID_STATES)}"
            )

    path = _events_path(feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    if "timestamp" not in event:
        event["timestamp"] = _now()
    line = json.dumps(event) + "\n"
    with _APPEND_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            try:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write(line)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            except ImportError:
                f.write(line)


def write_state(feature: str, state: dict) -> None:
    new_current = state.get("current")
    if new_current is not None and new_current not in VALID_STATES:
        raise ValueError(
            f"Invalid state: {new_current!r}. Must be one of {sorted(VALID_STATES)}"
        )

    path = _state_path(feature)
    if path.exists() and new_current is not None:
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            old_current = old.get("current")
            if old_current and old_current != new_current:
                allowed = TRANSITIONS.get(old_current, frozenset())
                if new_current not in allowed:
                    raise ValueError(
                        f"Invalid state transition: {old_current!r} → {new_current!r}. "
                        f"Allowed from {old_current!r}: {sorted(allowed)}"
                    )
        except json.JSONDecodeError:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    if "updated_at" not in state:
        state["updated_at"] = _now()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def read_events(feature: str) -> list[dict]:
    path = _events_path(feature)
    if not path.exists():
        return []
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


def read_state(feature: str) -> dict | None:
    path = _state_path(feature)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def summary(feature: str) -> dict:
    """Aggregate token/cost data from EVENTS.jsonl for the pipeline-walkthrough."""
    events = read_events(feature)
    agents: dict[str, dict] = {}
    total_cost = 0.0
    total_tokens = 0
    total_tool_uses = 0
    total_wall_seconds = 0

    for e in events:
        if e.get("type") != "AGENT_DONE":
            continue
        agent = e.get("agent", "unknown")
        conv = e.get("conversation", 0)
        key = f"{agent} (conv {conv})" if conv else agent
        if key not in agents:
            agents[key] = {
                "model": e.get("model", ""),
                "result": e.get("result", ""),
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "tool_uses": 0,
                "wall_seconds": 0,
            }
        agents[key]["tokens_in"] += e.get("tokens_in", 0)
        agents[key]["tokens_out"] += e.get("tokens_out", 0)
        agents[key]["cost_usd"] += e.get("cost_usd", 0.0)
        agents[key]["tool_uses"] += e.get("tool_uses", 0)
        agents[key]["wall_seconds"] += e.get("wall_seconds", 0)
        total_cost += e.get("cost_usd", 0.0)
        total_tokens += e.get("tokens_in", 0) + e.get("tokens_out", 0)
        total_tool_uses += e.get("tool_uses", 0)
        total_wall_seconds += e.get("wall_seconds", 0)

    return {
        "feature": feature,
        "agents": agents,
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_tool_uses": total_tool_uses,
        "total_wall_seconds": total_wall_seconds,
    }


def _print_summary(feature: str) -> None:
    data = summary(feature)
    if not data["agents"]:
        print(f"No AGENT_DONE events found in plans/{feature}/EVENTS.jsonl")
        return

    print(f"\n── Token & Cost Summary: {feature} ──\n")
    header = f"{'Agent':<30} {'Model':<22} {'In':>8} {'Out':>8} {'Total':>8} {'Tools':>6} {'Secs':>6} {'Cost':>8}"
    print(header)
    print("─" * len(header))
    for key, a in data["agents"].items():
        total = a["tokens_in"] + a["tokens_out"]
        print(
            f"{key:<30} {a['model']:<22} {a['tokens_in']:>8,} {a['tokens_out']:>8,} "
            f"{total:>8,} {a['tool_uses']:>6} {a['wall_seconds']:>6} "
            f"${a['cost_usd']:>7.4f}"
        )
    print("─" * len(header))
    print(
        f"{'TOTAL':<30} {'':<22} {data['total_tokens']:>8,} {'':>8} {'':>8} "
        f"{data['total_tool_uses']:>6} {data['total_wall_seconds']:>6} "
        f"${data['total_cost_usd']:>7.4f}"
    )


def _print_events(feature: str) -> None:
    events = read_events(feature)
    if not events:
        print(f"No events found in plans/{feature}/EVENTS.jsonl")
        return
    for e in events:
        print(json.dumps(e))


def _cli() -> None:
    if len(sys.argv) < 3:
        print("Usage: pathly-events <summary|events> <feature>")
        sys.exit(1)
    cmd, feat = sys.argv[1], sys.argv[2]
    if cmd == "summary":
        _print_summary(feat)
    elif cmd == "events":
        _print_events(feat)
    else:
        print(f"Unknown command: {cmd}. Use 'summary' or 'events'.")
        sys.exit(1)


def _state_cli() -> None:
    if len(sys.argv) < 2:
        print("Usage: pathly-state <feature>")
        sys.exit(1)
    feat = sys.argv[1]
    state = read_state(feat)
    if state is None:
        print(f"No STATE.json found in plans/{feat}/")
        sys.exit(0)
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    _cli()
