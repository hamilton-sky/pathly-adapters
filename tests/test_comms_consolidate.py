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


# ── mode="dedup" (default) — unchanged behaviour ──────────────────────────────

def test_consolidate_mode_dedup_default_no_run_id(client):
    """Default mode must not spawn a board agent — no run_id in response."""
    scope = f"dedup-mode-{uuid.uuid4().hex[:6]}"
    r = client.post("/comms/consolidate", json={"board": "feature", "scope": scope})
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert "superseded_count" in body
    assert "run_id" not in body


def test_consolidate_mode_dedup_explicit_no_run_id(client):
    """Explicit mode='dedup' must not spawn a board agent."""
    scope = f"dedup-explicit-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/comms/consolidate",
        json={"board": "feature", "scope": scope, "mode": "dedup"},
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert "run_id" not in body


# ── mode="full" / "reflect" — spawn path ─────────────────────────────────────

def _fake_start_board_run(*args, **kwargs):
    """Stub for start_board_run: records calls and returns a canned success dict."""
    _fake_start_board_run.calls.append({"args": args, "kwargs": kwargs})
    return {"ok": True, "run_id": "x", "mode": "single-agent", "status": "started"}


_fake_start_board_run.calls = []


@pytest.fixture(autouse=False)
def patch_board_run(monkeypatch):
    """Monkeypatch start_board_run inside the comms blueprint's import namespace."""
    _fake_start_board_run.calls = []
    import pathly_orchestrator.http_server.blueprints.comms as comms_bp

    monkeypatch.setattr(
        comms_bp,
        "comms_consolidate",
        comms_bp.comms_consolidate,  # keep route handler; patch happens inside it
    )
    # Patch the module that the route handler imports from at call time
    import pathly_orchestrator.supervisor.board_run as br_mod

    monkeypatch.setattr(br_mod, "start_board_run", _fake_start_board_run)
    yield _fake_start_board_run


def test_consolidate_mode_full_spawns_board_run(client, patch_board_run):
    """mode='full' must spawn a board run with skill='planning/consolidate'."""
    scope = f"reflect-full-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/comms/consolidate",
        json={"board": "feature", "scope": scope, "mode": "full"},
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert body.get("run_id") == "x"
    assert body.get("status") == "started"
    assert "superseded_count" in body
    # Stub was called with skill="planning/consolidate"
    assert len(patch_board_run.calls) == 1
    call_kwargs = patch_board_run.calls[0]["kwargs"]
    assert call_kwargs.get("skill") == "planning/consolidate"


def test_consolidate_mode_reflect_spawns_board_run(client, patch_board_run):
    """mode='reflect' is an alias for 'full' and must also spawn."""
    scope = f"reflect-alias-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/comms/consolidate",
        json={"board": "feature", "scope": scope, "mode": "reflect"},
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert body.get("run_id") == "x"
    assert len(patch_board_run.calls) == 1
    call_kwargs = patch_board_run.calls[0]["kwargs"]
    assert call_kwargs.get("skill") == "planning/consolidate"


def test_consolidate_mode_full_409_when_board_busy(client, monkeypatch):
    """mode='full' must return 409 when start_board_run signals board_busy."""
    import pathly_orchestrator.supervisor.board_run as br_mod

    def _busy(*args, **kwargs):
        return {"ok": False, "error": "board_busy", "holder": "some-run-id"}

    monkeypatch.setattr(br_mod, "start_board_run", _busy)
    scope = f"reflect-busy-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/comms/consolidate",
        json={"board": "feature", "scope": scope, "mode": "full"},
    )
    assert r.status_code == 409, r.data
    body = json.loads(r.data)
    assert body["ok"] is False
