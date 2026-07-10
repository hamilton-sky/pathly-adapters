"""Embedding worker for comms board messages.

Lazy-loads SentenceTransformer('all-MiniLM-L6-v2') on first use.
If sentence-transformers is not installed, embed() returns None and
all callers fall back to recency-based retrieval.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_model = None
_model_lock = threading.Lock()
# A load failure used to latch _model=None PERMANENTLY on the first attempt, so one
# transient hiccup (a model-download blip) silently disabled semantic search for the
# whole process — indistinguishable from an honest "no matches". Now a transient
# failure is retried (up to _MAX_LOAD_ATTEMPTS); only a genuinely-absent library
# hard-latches, and embedder_status() surfaces the state to /health.
_model_load_attempts = 0
_model_unavailable = False
_MAX_LOAD_ATTEMPTS = 3

# A single global search fans out one /comms/search call PER board (features +
# project + global) — every one re-embeds the SAME query text. This bounded LRU
# dedupes that burst: the check happens INSIDE _model_lock, so during a burst only
# the first caller runs the model forward-pass and the rest return the cached vector.
_embed_cache: dict[str, list[float]] = {}
_embed_cache_order: list[str] = []
_EMBED_CACHE_MAX = 256


def _load_model():
    global _model, _model_load_attempts, _model_unavailable
    if _model is not None or _model_unavailable:
        return
    if _model_load_attempts >= _MAX_LOAD_ATTEMPTS:
        return  # gave up after repeated transient failures — see embedder_status()
    _model_load_attempts += 1
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
    except ImportError:
        _model_unavailable = True  # library truly absent → retrying cannot help
    except Exception:
        logging.getLogger("pathly").warning(
            "embedding model load failed (attempt %d/%d) — semantic search degraded "
            "until it loads",
            _model_load_attempts,
            _MAX_LOAD_ATTEMPTS,
            exc_info=True,
        )
        _model = None  # transient (download/init) → a later embed() retries


def embed(text: str) -> list[float] | None:
    """Return a 384-dimensional embedding for *text*, or None if unavailable."""
    if not text or not text.strip():
        return None
    with _model_lock:
        cached = _embed_cache.get(text)
        if cached is not None:
            return cached
        _load_model()
        if _model is None:
            return None
        result = _model.encode(text, convert_to_numpy=True).tolist()
        _embed_cache[text] = result
        _embed_cache_order.append(text)
        if len(_embed_cache_order) > _EMBED_CACHE_MAX:
            del _embed_cache[_embed_cache_order.pop(0)]
        return result


def embedder_status() -> dict:
    """Current query-embedder availability, for /health. Never triggers a load —
    it only reports state, so a health probe can't block on a model download."""
    return {
        "loaded": _model is not None,
        "unavailable": _model_unavailable,
        "load_attempts": _model_load_attempts,
    }


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
    Returns [] when there are no meaningful sub-units (the parent vector already covers it).
    """
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
    subtopic recall. Empty pieces are skipped; never raises (retrieval falls back gracefully).
    """

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
