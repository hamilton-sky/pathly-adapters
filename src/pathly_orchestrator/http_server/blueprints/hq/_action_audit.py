"""Audit log for executed HQ operator actions (local-operator ticket 05).

One board message per EXECUTED action — a confirmed click whose action ran,
whether it succeeded or failed. Proposals, cancellations, stale cards and reads
write nothing. Home: the board HQ was answering about, as a ``status`` post
from ``local-operator`` (server-written, so the system provenance stamp). The
board is already where people look for what happened and agents read it as
recent events; a separate log would be a second place nobody watches.

The write never goes through the model: the route calls ``record`` after the
action returns. Results are one line, never a payload.
"""

from __future__ import annotations

import json
import logging

ACTOR = "local-operator"


def audit_text(name: str, args: dict, ok: bool, summary: str) -> str:
    """``⚡ HQ operator · stop_run {"run_id": "…"} → done: Stopped run … · confirmed in chat``."""
    shown = {k: v for k, v in args.items() if k != "project_root"}
    outcome = "done" if ok else "failed"
    return (
        f"⚡ HQ operator · {name} {json.dumps(shown, ensure_ascii=False)} "
        f"→ {outcome}: {summary} · confirmed in chat"
    )


def record(
    conn, board: str, name: str, args: dict, ok: bool, summary: str
) -> str | None:
    """Post the audit entry on *board*; returns its message id, None on failure
    (the action already ran — a failed audit is logged, never raised)."""
    from pathly_orchestrator.runner.provenance import post_system

    from ...sse import _broadcast_comms

    try:
        message_id = post_system(
            conn,
            board="feature",
            scope=board,
            from_agent=ACTOR,
            type="status",
            text=audit_text(name, args, ok, summary),
        )
    except Exception:
        logging.exception("hq operator audit write failed")
        return None
    try:
        _broadcast_comms(
            board,
            {
                "type": "COMMS_UPDATE",
                "event": "hq_operator_action",
                "message_id": message_id,
                "board": "feature",
                "scope": board,
            },
        )
    except Exception:
        logging.debug("hq operator audit broadcast failed", exc_info=True)
    return message_id
