"""Tests for P2 DAG scheduler DB layer.

Covers:
  (a) claim_task race — two threads claim the same pending task; exactly one wins
  (b) fail_task cascade — A<-B<-C chain; fail A; B and C become 'blocked';
      get_ready_tasks excludes them
  (c) reclaim_stale_claims — reverts in_progress tasks back to pending
  (d) get_ready_tasks — never returns in_progress/failed/blocked tasks
"""

from __future__ import annotations

import json
import threading

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting never spawns background threads during tests."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(conn, scope: str, text: str, depends_on: list[str] | None = None) -> str:
    """Insert a pending task and return its ID."""
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="builder",
        type="task",
        text=text,
        depends_on=depends_on,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def _task_status(conn, mid: str) -> str | None:
    row = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    return row["task_status"] if row else None


# ---------------------------------------------------------------------------
# (a) claim_task race
# ---------------------------------------------------------------------------


def test_claim_task_race_exactly_one_winner():
    """Two threads racing to claim the same pending task — exactly one returns True.

    Each thread opens its own per-thread connection (as the real scheduler does).
    SQLite serializes the atomic WHERE task_status='pending' UPDATE at the storage
    layer; the loser sees rowcount==0 because the row no longer matches.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import claim_task

    conn = get_db()
    mid = _make_task(conn, scope="race1", text="contested task")

    results: list[bool] = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _try_claim():
        # Each thread must call get_db() to get its own thread-local connection.
        thread_conn = get_db()
        barrier.wait()  # both threads enter simultaneously
        result = claim_task(thread_conn, mid, run_id="worker-X")
        with lock:
            results.append(result)

    t1 = threading.Thread(target=_try_claim)
    t2 = threading.Thread(target=_try_claim)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2, "both threads must have returned"
    assert results.count(True) == 1, "exactly one thread should win the claim"
    assert results.count(False) == 1, "exactly one thread should lose"
    # verify final state from main thread's connection
    assert _task_status(conn, mid) == "in_progress"


def test_claim_task_returns_false_when_already_claimed():
    """claim_task on an already in_progress task returns False."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import claim_task

    conn = get_db()
    mid = _make_task(conn, scope="race2", text="solo task")

    assert claim_task(conn, mid, run_id="worker-A") is True
    assert claim_task(conn, mid, run_id="worker-B") is False


# ---------------------------------------------------------------------------
# (b) fail_task cascade
# ---------------------------------------------------------------------------


def test_fail_task_cascade_marks_dependents_blocked():
    """A<-B<-C chain: fail A → B and C become blocked; get_ready_tasks excludes them."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import fail_task, get_ready_tasks

    conn = get_db()
    scope = "cascade1"
    a_id = _make_task(conn, scope=scope, text="task A")
    b_id = _make_task(conn, scope=scope, text="task B", depends_on=[a_id])
    c_id = _make_task(conn, scope=scope, text="task C", depends_on=[b_id])

    blocked = fail_task(conn, a_id, reason="intentional failure")

    assert b_id in blocked, "B should be cascade-blocked"
    assert c_id in blocked, "C should be cascade-blocked"

    assert _task_status(conn, a_id) == "failed"
    assert _task_status(conn, b_id) == "blocked"
    assert _task_status(conn, c_id) == "blocked"

    ready = get_ready_tasks(conn, boards=["feature"], scopes=[scope])
    ready_ids = {r["id"] for r in ready}
    assert a_id not in ready_ids
    assert b_id not in ready_ids
    assert c_id not in ready_ids


def test_fail_task_idempotent():
    """fail_task on an already-failed task returns [] with no error."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import fail_task

    conn = get_db()
    mid = _make_task(conn, scope="cascade2", text="lone task")

    first = fail_task(conn, mid, reason="first failure")
    assert isinstance(first, list)

    second = fail_task(conn, mid, reason="duplicate")
    assert second == [], "second call on already-failed task must return []"
    assert _task_status(conn, mid) == "failed"


# ---------------------------------------------------------------------------
# (c) reclaim_stale_claims
# ---------------------------------------------------------------------------


def test_reclaim_stale_claims_reverts_in_progress():
    """reclaim_stale_claims reverts in_progress tasks to pending."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import claim_task, reclaim_stale_claims

    conn = get_db()
    scope = "reclaim1"
    mid = _make_task(conn, scope=scope, text="orphaned task")

    assert claim_task(conn, mid, run_id="dead-worker") is True
    assert _task_status(conn, mid) == "in_progress"

    reclaimed = reclaim_stale_claims(conn, board="feature", scope=scope)
    assert mid in reclaimed
    assert _task_status(conn, mid) == "pending"


def test_reclaim_stale_claims_empty_when_none_in_progress():
    """reclaim_stale_claims returns [] when no in_progress tasks exist."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import reclaim_stale_claims

    conn = get_db()
    scope = "reclaim2"
    _make_task(conn, scope=scope, text="pending task")  # stays pending

    reclaimed = reclaim_stale_claims(conn, board="feature", scope=scope)
    assert reclaimed == []


# ---------------------------------------------------------------------------
# (d) get_ready_tasks excludes non-pending statuses
# ---------------------------------------------------------------------------


def test_get_ready_tasks_excludes_in_progress():
    """get_ready_tasks never returns an in_progress task."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import claim_task, get_ready_tasks

    conn = get_db()
    scope = "exclude1"
    mid = _make_task(conn, scope=scope, text="claimed task")

    before = get_ready_tasks(conn, boards=["feature"], scopes=[scope])
    assert any(r["id"] == mid for r in before), "task should be ready before claim"

    claim_task(conn, mid, run_id="worker-Z")

    after = get_ready_tasks(conn, boards=["feature"], scopes=[scope])
    assert not any(
        r["id"] == mid for r in after
    ), "claimed task must not appear in ready"


def test_get_ready_tasks_excludes_failed():
    """get_ready_tasks never returns a failed task."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import fail_task, get_ready_tasks

    conn = get_db()
    scope = "exclude2"
    mid = _make_task(conn, scope=scope, text="doomed task")

    fail_task(conn, mid, reason="test failure")

    ready = get_ready_tasks(conn, boards=["feature"], scopes=[scope])
    assert not any(r["id"] == mid for r in ready)


def test_get_ready_tasks_excludes_blocked():
    """get_ready_tasks never returns a blocked task."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import fail_task, get_ready_tasks

    conn = get_db()
    scope = "exclude3"
    a_id = _make_task(conn, scope=scope, text="task A")
    b_id = _make_task(conn, scope=scope, text="task B", depends_on=[a_id])

    fail_task(conn, a_id, reason="upstream failed")

    assert _task_status(conn, b_id) == "blocked"
    ready = get_ready_tasks(conn, boards=["feature"], scopes=[scope])
    assert not any(r["id"] == b_id for r in ready)
