"""
EventLog — read/write EVENTS.jsonl and STATE.json.

The LLM writes these files directly using its Write/Bash tools.
This module provides:
  - append_event(storage_path, event_dict, flow=None)  — append one line to EVENTS.jsonl
  - write_state(storage_path, state_dict, flow=None)   — overwrite STATE.json
  - read_events(storage_path)                          — return list of event dicts
  - summary(storage_path)                              — print token/cost table (Bash-callable)

CLI usage (called by LLM via Bash or by the retro skill):
  python -m pathly_orchestrator.eventlog summary pathly/plans/security-fixes
  python -m pathly_orchestrator.eventlog events pathly/plans/security-fixes
"""

from __future__ import annotations
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("pathly.eventlog")

from pathly_orchestrator.state import (
    valid_states,
    flow_transitions,
    VALID_STATES,
    TRANSITIONS,
)
from pathly_orchestrator import db as _db

CURRENT_SCHEMA_VERSION = 1

_TOAST_EVENTS: dict[str, tuple[str, object]] = {
    "STATE_TRANSITION": ("info",    lambda e: f"{e.get('from','?')} → {e.get('to','?')}"),
    "AGENT_DONE":       ("success", lambda e: (e.get("summary") or e.get("result") or "Agent done")[:80]),
    "GATE_FAILED":      ("warning", lambda e: f"Gate blocked: {(e.get('reason') or e.get('gate',''))[:60]}"),
    "FEEDBACK_RESOLVED":("info",    lambda e: f"Feedback resolved: {e.get('file','')[:50]}"),
    "RETRY":            ("info",    lambda e: f"Retrying stage: {e.get('stage','')}"),
}


def _db_only() -> bool:
    """DB-only mode is on by default. Set PATHLY_DB_ONLY=0 to re-enable file fallbacks."""
    val = os.environ.get("PATHLY_DB_ONLY", "1").strip().lower()
    return val not in ("0", "false", "no")


def _plans_dir() -> Path:
    return Path("pathly") / "plans"


# bare feature names auto-resolved to pathly/plans/<name>/ for backward compat
def _resolve_path(storage_path: str) -> Path:
    import pathly_orchestrator.eventlog as _self

    if "/" not in storage_path and "\\" not in storage_path:
        return _self._plans_dir() / storage_path
    return Path(storage_path)


def _events_path(storage_path: str) -> Path:
    return _resolve_path(storage_path) / "EVENTS.jsonl"


def _state_path(storage_path: str) -> Path:
    return _resolve_path(storage_path) / "STATE.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_event(storage_path: str, event: dict, flow: dict | None = None) -> None:
    if event.get("type") == "STATE_TRANSITION":
        to_state = event.get("to")
        if to_state is not None:
            states = valid_states(flow) if flow is not None else VALID_STATES
            if to_state not in states:
                raise ValueError(
                    f"Invalid state in STATE_TRANSITION: {to_state!r}. "
                    f"Must be one of {sorted(states)}"
                )

    feature_dir = _resolve_path(storage_path).resolve()
    event.setdefault("schema_version", CURRENT_SCHEMA_VERSION)
    if "ts" not in event:
        event["ts"] = _now()

    feature_dir.mkdir(parents=True, exist_ok=True)
    conn = _db.get_db()
    feature = feature_dir.name
    project_root = str(feature_dir.parent.parent.parent)
    _db.append_event(conn, project_root, feature, event)

    event_type = event.get("type", "")
    if event_type in _TOAST_EVENTS:
        level, msg_fn = _TOAST_EVENTS[event_type]
        try:
            from pathly_orchestrator.http_server.sse import _broadcast_runner
            _broadcast_runner(feature, {
                "type": "TOAST",
                "level": level,
                "message": msg_fn(event),  # type: ignore[operator]
                "feature": feature,
            })
        except Exception:
            pass  # SSE is best-effort — never crash event logging


def _write_state_db(feature_dir: Path, feature: str, state: dict) -> None:
    """Write state to SQLite (and STATE.json as a snapshot). Called by write_state() after validation."""
    feature_dir = feature_dir.resolve()
    feature_dir.mkdir(parents=True, exist_ok=True)
    if "updated_at" not in state:
        state["updated_at"] = _now()
    conn = _db.get_db()
    project_root = str(feature_dir.parent.parent.parent)
    _db.write_state(conn, project_root, feature, state)
    if _db_only():
        return  # DB-only mode: skip STATE.json file write
    # Also write STATE.json as a human-readable snapshot (agents and tools read it directly)
    path = feature_dir / "STATE.json"
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def write_state(storage_path: str, state: dict, flow: dict | None = None) -> None:
    new_current = state.get("current")

    if new_current is not None:
        states = valid_states(flow) if flow is not None else VALID_STATES
        if new_current not in states:
            raise ValueError(
                f"Invalid state: {new_current!r}. Must be one of {sorted(states)}"
            )

    feature_dir = _resolve_path(storage_path).resolve()
    if new_current is not None:
        existing = read_state(storage_path)
        if existing is not None:
            old_current = existing.get("current")
            if old_current and old_current != new_current:
                if flow is not None:
                    transitions = flow_transitions(flow)
                    allowed = transitions.get(old_current, frozenset())
                else:
                    allowed = frozenset(TRANSITIONS.get(old_current, []))
                if new_current not in allowed:
                    raise ValueError(
                        f"Invalid state transition: {old_current!r} → {new_current!r}. "
                        f"Allowed from {old_current!r}: {sorted(allowed)}"
                    )

    _write_state_db(feature_dir, feature_dir.name, state)


write_state.__wrapped__ = _write_state_db  # type: ignore[attr-defined]


def read_events(storage_path: str) -> list[dict]:
    feature_dir = _resolve_path(storage_path).resolve()
    project_root = str(feature_dir.parent.parent.parent)
    conn = _db.get_db()
    events = _db.read_events(conn, project_root, feature_dir.name)
    if not events and not _db_only():
        # Fall back to EVENTS.jsonl for legacy feature dirs that predate SQLite.
        # Disabled when PATHLY_DB_ONLY=1 so the DB-only path can be verified.
        path = _events_path(storage_path)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    for event in events:
        schema_version = event.get("schema_version")
        if schema_version is None:
            logger.warning(
                "Event missing schema_version; assuming version %s: %s",
                CURRENT_SCHEMA_VERSION,
                event,
            )
        elif schema_version > CURRENT_SCHEMA_VERSION:
            logger.warning(
                "Event schema_version %s is newer than supported %s; some fields may not be recognized: %s",
                schema_version,
                CURRENT_SCHEMA_VERSION,
                event,
            )
    return events


def read_state(storage_path: str) -> dict | None:
    feature_dir = _resolve_path(storage_path).resolve()
    project_root = str(feature_dir.parent.parent.parent)
    conn = _db.get_db()
    result = _db.read_state(conn, project_root, feature_dir.name)
    if result is not None:
        return result
    if _db_only():
        return None  # DB-only mode: skip STATE.json fallback
    # Fall back to STATE.json for legacy feature dirs that predate SQLite
    path = _state_path(storage_path)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def summary(storage_path: str) -> dict:
    """Aggregate token/cost data from EVENTS.jsonl for the pipeline-walkthrough."""
    events = read_events(storage_path)
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
        "storage_path": storage_path,
        "agents": agents,
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_tool_uses": total_tool_uses,
        "total_wall_seconds": total_wall_seconds,
    }


def _print_summary(storage_path: str) -> None:
    data = summary(storage_path)
    if not data["agents"]:
        print(
            f"No AGENT_DONE events found in {_resolve_path(storage_path)}/EVENTS.jsonl"
        )
        return

    print(f"\n── Token & Cost Summary: {storage_path} ──\n")
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


def _print_events(storage_path: str) -> None:
    events = read_events(storage_path)
    if not events:
        print(f"No events found in {_resolve_path(storage_path)}/EVENTS.jsonl")
        return
    for e in events:
        print(json.dumps(e))


def _cli() -> None:
    if len(sys.argv) < 3:
        print("Usage: pathly-events <summary|events> <storage-path>")
        sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "summary":
        _print_summary(path)
    elif cmd == "events":
        _print_events(path)
    else:
        print(f"Unknown command: {cmd}. Use 'summary' or 'events'.")
        sys.exit(1)


def _state_cli() -> None:
    if len(sys.argv) < 2:
        print("Usage: pathly-state <storage-path>")
        sys.exit(1)
    path = sys.argv[1]
    state = read_state(path)
    if state is None:
        print(f"No STATE.json found in {_resolve_path(path)}/")
        sys.exit(0)
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    _cli()
