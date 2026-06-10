"""Embedding worker for comms board messages.

Lazy-loads SentenceTransformer('all-MiniLM-L6-v2') on first use.
If sentence-transformers is not installed, embed() returns None and
all callers fall back to recency-based retrieval.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_model = None
_model_lock = threading.Lock()
_model_load_attempted = False


def _load_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return
    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        _model = None


def embed(text: str) -> list[float] | None:
    """Return a 384-dimensional embedding for *text*, or None if unavailable."""
    if not text or not text.strip():
        return None
    with _model_lock:
        _load_model()
        if _model is None:
            return None
        result = _model.encode(text, convert_to_numpy=True)
        return result.tolist()


def embed_async(message_id: str, text: str) -> None:
    """Compute the embedding for *text* in a daemon thread and store it."""
    def _worker():
        vector = embed(text)
        if vector is None:
            return
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.comms import store_embedding
            store_embedding(get_db(), message_id, vector, chunk_index=0, chunk_text=text)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def warm() -> None:
    """Trigger the one-time model load in the current thread (call at server startup)."""
    with _model_lock:
        _load_model()
