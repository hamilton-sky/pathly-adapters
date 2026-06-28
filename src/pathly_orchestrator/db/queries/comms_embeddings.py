"""Embedding storage and semantic/hybrid search for the comms board.

Layer contract: this module is in db/ and must not import from runner/.
The dedupe_board function accepts an optional embed_fn callable — callers at the
http_server or runner layer inject it. Without it, dedup is a no-op.
"""

from __future__ import annotations

import sqlite3

from .. import connection as _connection_module
from ..connection import _VEC_AVAILABLE, _get_write_lock
from .comms_messages import supersede_message

_RRF_K = 60

# Types that carry structure or governance — NEVER auto-deduped.
_DEDUP_PROTECTED_TYPES = (
    "goal",
    "task",
    "decision",
    "escalation",
    "question",
    "answer",
)


def _dist_of(row: dict) -> float:
    """Cosine distance of a search row, or a large sentinel when no semantic score."""
    d = row.get("_distance")
    return d if d is not None else 9e9


def search_by_embedding(
    conn: sqlite3.Connection,
    embedding: list[float],
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """Return up to k messages ordered by semantic similarity (or recency when vec unavailable).

    Merges parent vector (whole summary) and child chunk vectors so a query matching
    one subtopic of a multi-topic artifact still retrieves it.
    """
    if not boards or not scopes:
        return []
    if _VEC_AVAILABLE:
        board_ph = ",".join("?" * len(boards))
        scope_ph = ",".join("?" * len(scopes))
        import struct

        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
        base: list = [embedding_bytes] + list(boards) + list(scopes)
        parent_sql = (
            "SELECT m.*, vec_distance_cosine(e.embedding, ?) AS _distance "  # nosec B608
            "FROM comms_messages m JOIN comms_embeddings e ON e.message_id = m.id "
            f"WHERE m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
            "AND m.deleted_at IS NULL ORDER BY _distance ASC LIMIT ?"
        )
        best: dict[str, dict] = {}
        for r in conn.execute(parent_sql, base + [k * 2]).fetchall():
            best[r["id"]] = dict(r)
        try:
            child_sql = (
                "SELECT m.*, vec_distance_cosine(c.embedding, ?) AS _distance, "  # nosec B608
                "c.chunk_text AS _matched_chunk "
                "FROM comms_messages m JOIN comms_chunk_embeddings c ON c.message_id = m.id "
                f"WHERE m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
                "AND m.deleted_at IS NULL ORDER BY _distance ASC LIMIT ?"
            )
            for r in conn.execute(child_sql, base + [k * 3]).fetchall():
                d = dict(r)
                prev = best.get(d["id"])
                if prev is None or _dist_of(d) < _dist_of(prev):
                    best[d["id"]] = d
        except sqlite3.OperationalError:
            pass  # chunk table absent (older DB) → parents only
        return sorted(best.values(), key=_dist_of)[:k]

    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT * FROM comms_messages "  # nosec B608
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        "AND deleted_at IS NULL "
        "ORDER BY ts DESC LIMIT ?"
    )
    params = list(boards) + list(scopes) + [k]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def search_by_keyword(
    conn: sqlite3.Connection,
    query_text: str,
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """BM25 full-text search via FTS5. Returns [] when FTS unavailable or inputs empty."""
    if not _connection_module._FTS_AVAILABLE or not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT m.* FROM comms_messages m "  # nosec B608
        "JOIN comms_fts ON comms_fts.rowid = m.rowid "
        f"WHERE comms_fts MATCH ? AND m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
        "AND m.deleted_at IS NULL "
        "ORDER BY rank LIMIT ?"
    )
    try:
        rows = conn.execute(
            sql, [query_text] + list(boards) + list(scopes) + [k]
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


def search_by_hybrid(
    conn: sqlite3.Connection,
    query_text: str,
    query_embedding: list[float] | None,
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """BM25 + cosine merged via Reciprocal Rank Fusion. Falls back gracefully."""
    bm25_rows = (
        search_by_keyword(conn, query_text, boards, scopes, k * 2) if query_text else []
    )
    sem_rows = (
        search_by_embedding(conn, query_embedding, boards, scopes, k * 2)
        if query_embedding is not None
        else []
    )

    if not bm25_rows and not sem_rows:
        return []

    scores: dict[str, dict] = {}
    for rank, row in enumerate(bm25_rows):
        mid = row["id"]
        scores.setdefault(mid, {"row": row, "bm25": 9999, "sem": 9999})
        scores[mid]["bm25"] = rank
    for rank, row in enumerate(sem_rows):
        mid = row["id"]
        scores.setdefault(mid, {"row": row, "bm25": 9999, "sem": 9999})
        scores[mid]["sem"] = rank

    ranked = sorted(
        scores.values(),
        key=lambda x: 1.0 / (_RRF_K + x["bm25"]) + 1.0 / (_RRF_K + x["sem"]),
        reverse=True,
    )
    sem_dist = {row["id"]: row.get("_distance") for row in sem_rows}
    out: list[dict] = []
    for r in ranked[:k]:
        row = dict(r["row"])
        if row.get("id") in sem_dist:
            row["_distance"] = sem_dist[row["id"]]
        out.append(row)
    return out


def store_embedding(
    conn: sqlite3.Connection,
    message_id: str,
    embedding: list[float],
    chunk_index: int = 0,
    chunk_text: str = "",
) -> None:
    """Insert or replace an embedding row in comms_embeddings. No-op if vec unavailable."""
    if not _VEC_AVAILABLE:
        return
    import struct

    embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR REPLACE INTO comms_embeddings (message_id, embedding, chunk_index, chunk_text) "
            "VALUES (?, ?, ?, ?)",
            (message_id, embedding_bytes, chunk_index, chunk_text),
        )
        conn.commit()


def store_chunk_embeddings(
    conn: sqlite3.Connection,
    message_id: str,
    chunks: list[tuple[str, list[float]]],
) -> None:
    """Replace child-chunk embeddings for *message_id*. No-op when vec unavailable."""
    if not _VEC_AVAILABLE:
        return
    import struct

    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM comms_chunk_embeddings WHERE message_id=?", (message_id,)
        )
        for i, (text, vector) in enumerate(chunks):
            eb = struct.pack(f"{len(vector)}f", *vector)
            conn.execute(
                "INSERT OR REPLACE INTO comms_chunk_embeddings "
                "(chunk_id, message_id, embedding, chunk_text) VALUES (?, ?, ?, ?)",
                (f"{message_id}:{i + 1}", message_id, eb, text),
            )
        conn.commit()


def dedupe_board(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    *,
    max_distance: float = 0.08,
    embed_fn=None,
) -> list[dict]:
    """Supersede near-duplicate free-form notes, keeping the newest of each cluster.

    embed_fn must be provided by the caller (http_server layer). When None, this
    is a no-op — db/ must not import from runner/. Returns the list of
    {"superseded", "by", "distance"} pairs applied.
    """
    if embed_fn is None:
        return []

    placeholders = ",".join("?" * len(_DEDUP_PROTECTED_TYPES))
    rows = conn.execute(
        "SELECT id, ts, text FROM comms_messages "  # nosec B608
        "WHERE board=? AND scope=? AND deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by='') "
        f"AND type NOT IN ({placeholders}) "
        "ORDER BY ts DESC",
        [board, scope, *_DEDUP_PROTECTED_TYPES],
    ).fetchall()

    superseded: set[str] = set()
    pairs: list[dict] = []
    for r in rows:
        keeper_id, keeper_ts = r["id"], r["ts"]
        if keeper_id in superseded:
            continue
        try:
            emb = embed_fn(r["text"] or "")
        except Exception:
            emb = None
        if emb is None:
            continue
        neighbours = search_by_embedding(conn, emb, [board], [scope], k=20)
        for n in neighbours:
            nid = n.get("id")
            if not nid or nid == keeper_id or nid in superseded:
                continue
            dist = n.get("_distance")
            if dist is None or dist > max_distance:
                continue
            if (n.get("ts") or "") >= keeper_ts:
                continue
            if supersede_message(conn, nid, keeper_id) == "ok":
                superseded.add(nid)
                pairs.append({"superseded": nid, "by": keeper_id, "distance": dist})
    return pairs
