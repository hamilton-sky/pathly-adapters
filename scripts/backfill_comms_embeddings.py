"""Backfill comms_embeddings for existing embed-eligible messages.

Required after the ``_VEC_AVAILABLE`` stale-binding fix (comms_embeddings.py imported
the flag by value at import time, when it was still ``False``, so ``store_embedding``
silently no-op'd forever). Every message posted while the bug was live has no vector,
so semantic search fell back to recency. Run once to populate vectors.

Idempotent: skips messages that already have an embedding. Safe to run against a live DB.

    python scripts/backfill_comms_embeddings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Prefer the in-repo source over any stale site-packages install.
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

# Types that carry retrievable semantic content (mirrors messages_write._EMBED_TYPES).
_EMBED_TYPES = ("artifact", "decision", "warning", "discovery", "escalation", "constraint")


def main() -> int:
    from pathly_orchestrator.db.connection import get_db, retrieval_status
    from pathly_orchestrator.db.queries.comms_embeddings import store_embedding
    from pathly_orchestrator.runner.embeddings import embed

    conn = get_db()
    status = retrieval_status(conn)
    if not status["vec_available"]:
        print(
            "sqlite-vec unavailable in this process — aborting "
            "(store_embedding would no-op and nothing would persist)."
        )
        return 1

    placeholders = ",".join("?" * len(_EMBED_TYPES))
    rows = conn.execute(
        "SELECT id, text FROM comms_messages "
        f"WHERE type IN ({placeholders}) AND deleted_at IS NULL AND text IS NOT NULL",
        _EMBED_TYPES,
    ).fetchall()
    have = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT message_id FROM comms_embeddings"
        ).fetchall()
    }

    embedded = skipped = failed = 0
    for r in rows:
        mid, text = r["id"], (r["text"] or "").strip()
        if mid in have:
            skipped += 1
            continue
        if not text:
            failed += 1
            continue
        vec = embed(text)
        if vec is None:
            failed += 1
            continue
        store_embedding(conn, mid, vec, chunk_index=0, chunk_text=text)
        embedded += 1

    print(
        f"backfill: embedded={embedded} skipped_existing={skipped} "
        f"failed={failed} eligible_total={len(rows)}"
    )
    print("retrieval_status:", retrieval_status(conn))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
