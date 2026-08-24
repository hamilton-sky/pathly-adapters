"""Shape one ``AGENT_DONE`` event into an ``agent_invocations`` row.

Split out of ``invocation_projection.py`` under the 400-line SOLID ratchet. The projector
owns the STREAM (which events project, how a BILLING_UPDATE folds onto its anchor, the
upsert); this module owns the ROW — reading an event payload's fields and deciding a row's
scope tier. The two change for different reasons: a new event field touches this file, a
change to fold/supersede semantics touches the projector.
"""

from __future__ import annotations

import json
import sqlite3

from .fsm_events import _board_scope_of
from .invocation_pricing import num as _num


def _tier_for(conn: sqlite3.Connection, project_root: str, feature: str) -> str:
    """Best-effort board scope tier for (project_root, feature).

    AGENT_DONE events carry no scope tier, so we recover it from a sibling fact that
    does: a non-'feature' tier on any existing invocation or otel_span for this
    (project_root, feature). Defaults to 'feature' (correct for interactive runs).
    """
    for table in ("agent_invocations", "otel_spans"):
        try:
            row = conn.execute(
                f"SELECT scope_tier FROM {table} "  # nosec B608 - {table} is a hardcoded literal tuple; params are bound
                "WHERE project_root=? AND feature=? AND scope_tier IS NOT NULL "
                "AND scope_tier!='feature' LIMIT 1",
                (project_root, feature),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except sqlite3.OperationalError:
            continue
    return "feature"


def _agent_done_rec(payload: dict) -> dict:
    """Build the invocation fields an AGENT_DONE payload can supply."""
    total_tok = int(_num(payload.get("total_tokens")))
    # Run TYPE for the Monitor's RECENT bucketing. Guarded so an unsubstituted
    # <run_category> placeholder (a raw/interactive skill that skipped injection) lands as
    # NULL, not a junk bucket — the renderer then falls back to its scope_tier heuristic.
    cat = payload.get("category")
    if cat not in ("flow", "single", "loop"):
        cat = None
    return {
        "agent_role": payload.get("agent") or "agent",
        "conversation": payload.get("conversation"),
        "category": cat,
        # run-identity: the spawn-issued board scope, guarded like category (an
        # unsubstituted <feature> placeholder lands as NULL, never a junk identity).
        "board_scope": _board_scope_of(payload),
        "cost_usd": _num(payload.get("cost_usd")),
        # AGENT_DONE only ever carries total_tokens (never an in/out split); park the
        # total in tokens_in so SUM(tokens_in+tokens_out) is the true total. A later
        # BILLING_UPDATE overwrites both with the real split.
        "tokens_in": int(_num(payload.get("tokens_in"))) or total_tok,
        "tokens_out": int(_num(payload.get("tokens_out"))),
        "tool_uses": int(_num(payload.get("tool_uses"))),
        "summary": (payload.get("summary") or payload.get("result") or "")[:2000],
        "provider": payload.get("model") or payload.get("adapter") or None,
        "run_id": payload.get("run_id"),
        "ts": payload.get("ts") or "",
    }
