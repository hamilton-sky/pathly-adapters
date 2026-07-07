"""Regression tests for the _VEC_AVAILABLE stale-binding bug (CT6).

comms_embeddings.py used to do ``from ..connection import _VEC_AVAILABLE`` — binding
the flag BY VALUE at import time, when it was still the module default ``False``. When
get_db() later set ``connection._VEC_AVAILABLE = True``, this module's copy stayed
``False`` forever, so ``store_embedding``/``store_chunk_embeddings`` silently no-op'd
and ``search_by_embedding`` always took the recency fallback. Result: 0 embeddings ever
written and semantic vector search never ran. The fix references
``_connection_module._VEC_AVAILABLE`` live at each call site.
"""

from __future__ import annotations

import pytest


def test_no_stale_vec_available_binding():
    """comms_embeddings must NOT hold its own _VEC_AVAILABLE name (the by-value copy)."""
    import pathly_orchestrator.db.queries.comms_embeddings as E

    assert not hasattr(E, "_VEC_AVAILABLE"), (
        "comms_embeddings re-introduced a by-value `from ..connection import "
        "_VEC_AVAILABLE`; reference connection._VEC_AVAILABLE live instead (it latched "
        "False at import and made store_embedding a permanent no-op)."
    )


def test_store_embedding_persists_when_vec_available():
    """With vec available, store_embedding actually writes a row — not a no-op."""
    import pathly_orchestrator.db.connection as _conn_mod
    from pathly_orchestrator.db.queries.comms_embeddings import store_embedding

    conn = _conn_mod.get_db()
    if not _conn_mod._VEC_AVAILABLE:
        pytest.skip("sqlite-vec not available on this build")

    mid = "regress-embed-persist-1"
    conn.execute("DELETE FROM comms_embeddings WHERE message_id=?", (mid,))
    conn.commit()
    store_embedding(
        conn, mid, [0.05] * 384, chunk_index=0, chunk_text="regression probe"
    )
    n = conn.execute(
        "SELECT COUNT(*) FROM comms_embeddings WHERE message_id=?", (mid,)
    ).fetchone()[0]
    conn.execute("DELETE FROM comms_embeddings WHERE message_id=?", (mid,))
    conn.commit()
    assert n == 1, (
        "store_embedding must persist when connection._VEC_AVAILABLE is True; got 0 "
        "rows — the stale-binding no-op has regressed."
    )


def test_retrieval_status_shape():
    """retrieval_status() exposes vec/fts availability + embedding count for /health."""
    from pathly_orchestrator.db.connection import get_db, retrieval_status

    st = retrieval_status(get_db())
    assert set(st) >= {"vec_available", "fts_available", "embeddings_rows"}
    assert isinstance(st["vec_available"], bool)
