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
        import os

        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        try:
            import transformers.utils.logging as _hf_log

            _hf_log.set_verbosity_error()
        except Exception:
            pass
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

            store_embedding(
                get_db(), message_id, vector, chunk_index=0, chunk_text=text
            )
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def chunk_summary(summary: str) -> list[str]:
    """Split a summary into retrievable CHILD chunks by its natural structure:
    detailed → one chunk per ``###`` section; topic-map → one chunk per bullet; gist → none.
    Returns [] when there are no meaningful sub-units (the parent vector already covers it)."""
    if not summary or not summary.strip():
        return []
    lines = summary.splitlines()
    if any(ln.lstrip().startswith("###") for ln in lines):
        chunks: list[str] = []
        cur: list[str] = []
        for ln in lines:
            if ln.lstrip().startswith("###"):
                if cur:
                    chunks.append("\n".join(cur).strip())
                cur = [ln]
            else:
                cur.append(ln)
        if cur:
            chunks.append("\n".join(cur).strip())
        return [c for c in chunks if c]
    bullets = [
        ln.strip()
        for ln in lines
        if ln.lstrip()[:2] in ("- ", "* ") or ln.lstrip().startswith("• ")
    ]
    return bullets if len(bullets) >= 2 else []


def embed_artifact_async(message_id: str, parent_text: str, summary: str) -> None:
    """Embed an artifact in a daemon thread: a PARENT vector (whole message text + summary) for
    thematic recall, plus one CHILD vector per summary chunk (per-bullet / per-section) for
    subtopic recall. Empty pieces are skipped; never raises (retrieval falls back gracefully)."""

    def _worker():
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.comms import (
                store_chunk_embeddings,
                store_embedding,
            )

            conn = get_db()
            parent = embed(parent_text)
            if parent is not None:
                store_embedding(
                    conn, message_id, parent, chunk_index=0, chunk_text=parent_text
                )
            pairs: list[tuple[str, list[float]]] = []
            for chunk in chunk_summary(summary):
                vec = embed(chunk)
                if vec is not None:
                    pairs.append((chunk, vec))
            store_chunk_embeddings(conn, message_id, pairs)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def warm() -> None:
    """Trigger the one-time model load in the current thread (call at server startup)."""
    with _model_lock:
        _load_model()
