"""Per-goal slug generation and persistence.

Supervisor-layer helper: may import db; MUST NOT import http_server.
"""
from __future__ import annotations

import re
import sqlite3
import uuid

from pathly_orchestrator.db.queries.comms_messages import read_message_slug, set_message_slug


def _slugify(text: str) -> str:
    """Lowercase text, replace runs of non-[a-z0-9] with '-', strip leading/trailing '-',
    cap at 48 chars. Returns 'goal' for empty/symbol-only text."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "goal")[:48]


def ensure_goal_slug(conn, goal_id: str) -> str:
    """Return the slug for this goal, creating and persisting one if absent.

    All reads and writes happen inside a single write-lock block so racing callers
    converge on one slug — the partial UNIQUE index on comms_messages.slug is the
    collision backstop.
    """
    from pathly_orchestrator.db.connection import _get_write_lock

    with _get_write_lock(conn):
        row = read_message_slug(conn, goal_id)
        if row is None:
            # Goal row not found — return a deterministic fallback without writing
            return f"goal-{goal_id[:8]}"

        existing = row.get("slug") or ""
        if existing:
            return existing

        base = _slugify(row.get("text") or "")[:48]
        candidate = f"{base}-{goal_id[:8]}"
        # Truncate the whole slug to 64 chars maximum
        candidate = candidate[:64]

        for tail_len in (8, 10, 12):
            try:
                set_message_slug(conn, goal_id, candidate)
                return candidate
            except sqlite3.IntegrityError:
                # Collision — try a longer id tail
                candidate = f"{base}-{goal_id[:tail_len]}"[:64]

        # Final fallback: uuid4 hex tail
        candidate = f"{base}-{uuid.uuid4().hex}"[:64]
        set_message_slug(conn, goal_id, candidate)
        return candidate
