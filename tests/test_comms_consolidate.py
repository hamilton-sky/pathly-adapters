"""Deterministic memory consolidation — dedupe_board + /comms/consolidate.

Seeds messages with embeddings and stubs the neighbour search to control distances,
so the supersede LOGIC (keep newest, protect structural types, idempotent) is tested
without the embedding model.
"""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.fixture()
def conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _insert(conn, scope, mtype, text, ts):
    from pathly_orchestrator.db.connection import _get_write_lock
    from pathly_orchestrator.db.queries.comms import store_embedding

    mid = str(uuid.uuid4())
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_messages (id, board, scope, from_agent, to_agent, type, text, ts) "
            "VALUES (?, 'feature', ?, 'a', '*', ?, ?, ?)",
            (mid, scope, mtype, text, ts),
        )
        conn.commit()
    store_embedding(conn, mid, [0.0] * 384, chunk_index=0, chunk_text=text)
    return mid


def _superseded_by(conn, mid):
    row = conn.execute(
        "SELECT superseded_by FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    return row["superseded_by"] if row else None


def test_dedupe_supersedes_older_keeps_newest_protects_task(conn, monkeypatch):
    from pathly_orchestrator.db.connection import _VEC_AVAILABLE
    if not _VEC_AVAILABLE:
        pytest.skip("sqlite-vec unavailable")
    import pathly_orchestrator.db.queries.comms as cq

    scope = f"dedup-{uuid.uuid4().hex[:8]}"
    old = _insert(conn, scope, "discovery", "API returns 500 on empty body", "2026-01-01T00:00:00Z")
    new = _insert(conn, scope, "discovery", "API returns 500 on empty body", "2026-02-01T00:00:00Z")
    task = _insert(conn, scope, "task", "Phase 1 build", "2026-01-15T00:00:00Z")

    # old & new are near-identical; the task must never be offered or touched.
    def fake_search(conn_, emb, boards, scopes, k=20):
        return [
            {"id": new, "ts": "2026-02-01T00:00:00Z", "_distance": 0.0},
            {"id": old, "ts": "2026-01-01T00:00:00Z", "_distance": 0.01},
        ]

    monkeypatch.setattr(cq, "search_by_embedding", fake_search)

    pairs = cq.dedupe_board(conn, "feature", scope, embed_fn=lambda t: [1.0] * 384)

    assert len(pairs) == 1
    assert pairs[0]["superseded"] == old and pairs[0]["by"] == new
    assert _superseded_by(conn, old) == new      # older collapsed into newer
    assert not _superseded_by(conn, new)         # newest kept
    assert not _superseded_by(conn, task)        # protected structural type untouched


def test_dedupe_idempotent(conn, monkeypatch):
    from pathly_orchestrator.db.connection import _VEC_AVAILABLE
    if not _VEC_AVAILABLE:
        pytest.skip("sqlite-vec unavailable")
    import pathly_orchestrator.db.queries.comms as cq

    scope = f"dedup2-{uuid.uuid4().hex[:8]}"
    old = _insert(conn, scope, "discovery", "dup", "2026-01-01T00:00:00Z")
    new = _insert(conn, scope, "discovery", "dup", "2026-02-01T00:00:00Z")

    def fake_search(conn_, emb, boards, scopes, k=20):
        # only return rows that are still active (mirror the real query's filter)
        out = []
        for mid, ts in ((new, "2026-02-01T00:00:00Z"), (old, "2026-01-01T00:00:00Z")):
            if not _superseded_by(conn, mid):
                out.append({"id": mid, "ts": ts, "_distance": 0.0})
        return out

    monkeypatch.setattr(cq, "search_by_embedding", fake_search)

    first = cq.dedupe_board(conn, "feature", scope, embed_fn=lambda t: [1.0] * 384)
    second = cq.dedupe_board(conn, "feature", scope, embed_fn=lambda t: [1.0] * 384)
    assert len(first) == 1
    assert second == []  # nothing new on a re-run


def test_consolidate_route_empty_board(client):
    r = client.post("/comms/consolidate", json={"board": "feature", "scope": f"empty-{uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True and body["superseded_count"] == 0


def test_consolidate_route_requires_scope(client):
    r = client.post("/comms/consolidate", json={"board": "feature"})
    assert r.status_code == 400
