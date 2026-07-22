"""Event log access and patching for runner."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Generator

import logging

logger = logging.getLogger("pathly.runner")


def _patch_last_agent_done(
    storage_path: Path,
    cost_usd: float,
    tokens_in: int,
    tokens_out: int,
    wall_seconds: int,
    tool_uses: int = 0,
    model: str = "",
    run_id: str = "",
    board_scope: str = "",
) -> None:
    """Append a BILLING_UPDATE event with real cost/token data to DB.

    The events table is append-only — we do not mutate the original AGENT_DONE row.
    Instead we emit BILLING_UPDATE which supersedes it for cost/token display.

    ``board_scope`` (run-identity) rides along like ``model``/``run_id`` — the spawner
    knows it, the agent may not have reported it. The projection folds it onto the
    anchor AGENT_DONE **only when the anchor lacks one** (COALESCE — an agent-provided
    value is never overwritten).
    """
    # --- find last AGENT_DONE for agent/conv identification ---
    patched_agent: str | None = None
    patched_conv: int | None = None
    try:
        from pathly_orchestrator.db import get_db as _get_db
        from pathly_orchestrator.db import read_last_agent_done as _db_read_last

        conn = _get_db()
        feature = storage_path.name
        project_root = str(storage_path.parent.parent.parent)
        last = _db_read_last(conn, project_root, feature)
        if last:
            patched_agent = last.get("agent")
            patched_conv = last.get("conversation")
    except Exception:
        pass

    billing: dict[str, object] = {
        "type": "BILLING_UPDATE",
        "agent": patched_agent,
        "conversation": patched_conv,
        "cost_usd": cost_usd,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "wall_seconds": wall_seconds,
        "tool_uses": tool_uses,
        "model": model or None,
        "run_id": run_id or None,
        "board_scope": board_scope or None,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "schema_version": 1,
    }

    # --- write BILLING_UPDATE to DB ---
    try:
        from pathly_orchestrator.eventlog import append_event as _ae

        _ae(str(storage_path), billing)
    except Exception as exc:
        logger.warning("_patch_last_agent_done: DB write failed: %s", exc)


def read_last_agent_done(storage_path: Path) -> dict[str, Any] | None:
    """Return the last AGENT_DONE event for the feature, or None if absent.

    Reads exclusively from the central SQLite DB.
    """
    try:
        from pathly_orchestrator.db import get_db as _get_db
        from pathly_orchestrator.db import read_last_agent_done as _db_read_last

        conn = _get_db()
        feature = storage_path.name
        project_root = str(storage_path.parent.parent.parent)
        return _db_read_last(conn, project_root, feature)
    except Exception:
        return None


def tail_agent_done(
    path: str,
    after_ts: str,
    stop_evt: threading.Event,
    poll_interval: float = 0.1,
) -> Generator[dict, None, None]:
    """
    Tail EVENTS.jsonl and yield AGENT_DONE events with ts >= after_ts.
    Tracks byte offset so no event is yielded twice.
    Stops when stop_evt is set and no new bytes remain.
    Does not raise if the file does not exist yet — waits until it does.
    """
    offset = 0
    while True:
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                new_bytes = f.read()
        except OSError:
            new_bytes = b""
        if new_bytes:
            offset += len(new_bytes)
            for raw_line in new_bytes.split(b"\n"):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if (
                    event.get("type") == "AGENT_DONE"
                    and event.get("ts", "") >= after_ts
                ):
                    yield event
            time.sleep(poll_interval)
        else:
            if stop_evt.is_set():
                return
            time.sleep(poll_interval)
