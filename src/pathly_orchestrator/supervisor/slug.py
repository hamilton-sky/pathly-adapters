"""Per-goal slug generation and persistence.

Supervisor-layer helper: may import db; MUST NOT import http_server.
"""
from __future__ import annotations

import re
import sqlite3
import uuid

from pathly_orchestrator.db.queries.comms_messages import read_message_slug, set_message_slug


# Trivial words dropped from a slug so the readable part is the meaningful head of the
# title (e.g. "The Frontend of the App" -> "frontend-app", not "the-frontend-of-the-app").
_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "to", "and", "for", "in", "on", "with", "from", "is", "it"}
)


def _slugify(text: str) -> str:
    """Short, HUMAN-READABLE slug base: the first few meaningful (non-stopword) words of
    ``text``, lowercased and '-'-joined, kept under ~32 chars without truncating mid-word.
    Returns 'goal' for empty/symbol-only text. The goal_id tail (added by
    ``ensure_goal_slug``) keeps the full slug unique, so the base only needs to be
    recognizable at a glance — 'backend-api', not the whole title + hash.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]
    out: list[str] = []
    for w in words[:4]:
        if out and len("-".join(out)) + 1 + len(w) > 32:
            break
        out.append(w)
    # Backstop the 32-char cap even for a single over-long word (the loop always
    # takes the first word); rstrip a hyphen left by truncation.
    return ("-".join(out)[:32].rstrip("-")) or "goal"


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

        base = _slugify(row.get("text") or "")
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
