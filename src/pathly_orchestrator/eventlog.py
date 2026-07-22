"""
EventLog — DB-first event/state access for a feature (state-one-authority).

The central SQLite DB (fsm_events / fsm_state) is the single runtime authority.
The per-feature disk files are one-way DB->disk EXPORTs, never read back here:
STATE.json is written as a snapshot by write_state, EVENTS.jsonl by event_mirror
(debounced, queued from append_event).

This module provides:
  - append_event(storage_path, event_dict, flow=None)  — insert into fsm_events (+ queue the EVENTS.jsonl export)
  - write_state(storage_path, state_dict, flow=None)   — write fsm_state (+ STATE.json snapshot)
  - read_events(storage_path) / read_state(storage_path) — read from the DB
  - summary(storage_path)                              — print token/cost table (Bash-callable)

CLI usage (called by LLM via Bash or by the retro skill):
  python -m pathly_orchestrator.eventlog summary pathly/features/security-fixes
  python -m pathly_orchestrator.eventlog events pathly/features/security-fixes
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
    "STATE_TRANSITION": ("info", lambda e: f"{e.get('from','?')} → {e.get('to','?')}"),
    "AGENT_DONE": (
        "success",
        lambda e: (e.get("summary") or e.get("result") or "Agent done")[:80],
    ),
    "GATE_FAILED": (
        "warning",
        lambda e: f"Gate blocked: {(e.get('reason') or e.get('gate',''))[:60]}",
    ),
    "FEEDBACK_RESOLVED": (
        "info",
        lambda e: f"Feedback resolved: {e.get('file','')[:50]}",
    ),
    "RETRY": ("info", lambda e: f"Retrying stage: {e.get('stage','')}"),
}


def _norm_root(path: "str | Path") -> str:
    """Normalize project_root to forward slashes so Windows and HTTP paths match in SQLite."""
    return str(path).replace("\\", "/")


def _plans_dir() -> Path:
    return Path("pathly") / "plans"


# bare feature names auto-resolved to pathly/plans/<name>/ for backward compat
def _resolve_path(storage_path: str) -> Path:
    import pathly_orchestrator.eventlog as _self

    if "/" not in storage_path and "\\" not in storage_path:
        return _self._plans_dir() / storage_path
    return Path(storage_path)


def _project_root_of(feature_dir: Path) -> str:
    """Project root for a feature/run dir at ANY nesting depth.

    A run lives under ``<project_root>/pathly/…`` — flat (``pathly/features/<n>``) or nested
    (``pathly/project/<kind>/<n>``, ``pathly/features/<f>/<kind>/<n>``). The root is the ancestor
    directly ABOVE the ``pathly/`` segment, located by finding that segment rather than counting a
    fixed number of levels. The old ``feature_dir.parent.parent.parent`` matched only the flat depth
    and mis-derived nested runs — keying ``fsm_state``/events by ``<root>/pathly`` and orphaning the
    authoritative row (the board-scoped-storage split-brain). Behavior is IDENTICAL for flat/legacy
    paths; only genuinely-nested paths change. Falls back to the legacy 3-levels-up when there is no
    ``pathly/`` segment (unchanged for those)."""
    parts = feature_dir.parts
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] == "pathly":
            return _norm_root(Path(*parts[:i]))
    return _norm_root(feature_dir.parent.parent.parent)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_event(
    storage_path: str, event: dict, flow: dict | None = None, create_dir: bool = True
) -> None:
    """Append an event to the central DB (keyed by project_root + feature name).

    ``create_dir`` (default True) materializes the feature dir. The event itself is DB-backed,
    so the mkdir is only a convenience for callers that also drop files there. Pass
    ``create_dir=False`` when the caller only has a feature NAME and the feature's real on-disk
    home may live outside ``pathly/features/`` (debug/fix/goal runs): mkdir-ing the resolved
    ``features/<name>`` default would plant an empty decoy that then wins
    ``_resolve_storage_path``'s existence probe and hijacks that topic's real storage.
    """
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

    if create_dir:
        feature_dir.mkdir(parents=True, exist_ok=True)
    conn = _db.get_db()
    feature = feature_dir.name
    project_root = _project_root_of(feature_dir)
    # Full event dict is stored as a JSON blob in the payload column — no key whitelisting.
    # New optional fields (cost_source, cache_read_tokens, cache_write_tokens) pass through transparently.
    _db.append_event(conn, project_root, feature, event)

    # DB -> disk EXPORT hook (state-one-authority): queue this feature's EVENTS.jsonl for a
    # debounced rewrite from the DB. Best-effort — a mirror-export failure must never break
    # event logging. event_mirror reads events via db.queries directly (never imports eventlog),
    # and is keyed by the already-resolved feature_dir so debug/explore/goal runs export correctly.
    try:
        from pathly_orchestrator import event_mirror

        event_mirror.mark_event_dirty(feature_dir, project_root, feature)
    except Exception:
        pass  # export hook is best-effort — never crash event logging

    try:
        from pathly_orchestrator.event_bus import _bus

        _bus.publish(f"FSM_EVENT:{project_root}:{feature}", event)
        _bus.publish(event.get("type", ""), event)
    except Exception:
        pass  # bus notifications are best-effort

    event_type = event.get("type", "")
    if event_type in _TOAST_EVENTS:
        level, msg_fn = _TOAST_EVENTS[event_type]
        try:
            from pathly_orchestrator.http_server.sse import _broadcast_runner

            _broadcast_runner(
                feature,
                {
                    "type": "TOAST",
                    "level": level,
                    "message": msg_fn(event),  # type: ignore[operator]
                    "feature": feature,
                },
            )
        except Exception:
            pass  # SSE is best-effort — never crash event logging


def _write_state_db(feature_dir: Path, feature: str, state: dict) -> None:
    """Write state to SQLite (and STATE.json as a snapshot). Called by write_state() after validation."""
    feature_dir = feature_dir.resolve()
    feature_dir.mkdir(parents=True, exist_ok=True)
    if "updated_at" not in state:
        state["updated_at"] = _now()
    conn = _db.get_db()
    project_root = _project_root_of(feature_dir)
    _db.write_state(conn, project_root, feature, state)
    # Always write STATE.json — agents and the scope gate read it directly.
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
    project_root = _project_root_of(feature_dir)
    conn = _db.get_db()
    events = _db.read_events(conn, project_root, feature_dir.name)
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
    project_root = _project_root_of(feature_dir)
    conn = _db.get_db()
    return _db.read_state(conn, project_root, feature_dir.name)


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
