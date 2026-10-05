"""Tests for supervisor/scheduler.py — DAG frontier loop (Phase 2a).

Covers:
  1. Linear A->B->C (single lane): completion order A, B, C; all done.
  2. Diamond A -> B,C -> D: A finishes before B,C start; B and C intervals OVERLAP
     (true parallelism); D starts only after both B and C are done.
  3. Same-lane serialization: two ready tasks same lane -> intervals do NOT overlap.
  4. Failure: fake spawn raises for B -> B failed, B's dependent blocked, sibling
     lane (C) still completes.

DB isolation: conftest._isolate_db redirects all connections to a per-test tmp
SQLite file so the real ~/.pathly/pathly.db is never touched.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Stub embeddings so post_message never spawns background threads.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeState:
    """Minimal stand-in for RunnerState."""

    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "claude-sonnet-4-6"


def _make_task(
    conn,
    scope: str,
    text: str,
    lane: str = "default",
    depends_on: list[str] | None = None,
) -> str:
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
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', lane=? WHERE id=?",
        (lane, mid),
    )
    conn.commit()
    return mid


def _task_status(conn, mid: str) -> str | None:
    row = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    return row["task_status"] if row else None


def _make_fake_spawn(
    records: dict,
    sleep_s: float = 0.05,
    fail_for: set[str] | None = None,
):
    """Return a fake spawn_fn that records (start_ts, end_ts) per task_id.

    Parameters
    ----------
    records:
        Dict mutated in-place: {task_id: {"start": float, "end": float}}.
    sleep_s:
        How long to sleep to simulate work (enables overlap detection).
    fail_for:
        Set of task IDs to raise for. Matched against the task_id derived from
        run_id ("sched-<task_id>#<attempt>") — NOT the prompt text. The composed prompt
        now carries scope-aware board context that quotes every sibling task's text, so
        a substring match on instructions would (flakily) trip whichever task ran first.
    """
    fail_for = fail_for or set()
    lock = threading.Lock()

    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        # run_id is "sched-<task_id>#<attempt>" (task_retry.py: unique per attempt) —
        # strip the prefix and the attempt suffix to get the bare task_id.
        task_id = (
            run_id[len("sched-") :].split("#", 1)[0]
            if run_id.startswith("sched-")
            else run_id
        )
        start = time.monotonic()
        with lock:
            records[task_id] = {
                "start": start,
                "end": None,
                "instructions": instructions,
            }
        time.sleep(sleep_s)
        end = time.monotonic()
        with lock:
            records[task_id]["end"] = end
        # Fail by task_id, not by matching prompt text. The composed prompt now
        # carries board context that quotes every sibling task's text, so a substring
        # match on instructions trips whichever task ran first (flaky cascade). The
        # task_id derived from run_id is the one stable identifier the fake controls.
        if task_id in fail_for:
            raise RuntimeError(f"Intentional failure for task: {task_id}")
        return {"ok": True}

    return _spawn


def _run_scheduler(scope: str, isolation=None, **kwargs) -> dict:
    """Run scheduler_loop with a fresh LaneIsolation unless overridden."""
    from pathly_orchestrator.supervisor.isolation import LaneIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    if isolation is None:
        isolation = LaneIsolation()
    state = _FakeState()
    return scheduler_loop(
        state, board="feature", scope=scope, isolation=isolation, **kwargs
    )


def _intervals_overlap(r1: dict, r2: dict) -> bool:
    """Return True if two (start, end) records overlap in time."""
    return r1["start"] < r2["end"] and r2["start"] < r1["end"]


# ---------------------------------------------------------------------------
# Test 1: Linear A -> B -> C (single lane)
# ---------------------------------------------------------------------------


def test_linear_chain_completes_in_order():
    """A->B->C in one lane: all complete; order is A then B then C."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "sched-linear"

    a_id = _make_task(conn, scope, "task-A", lane="main")
    b_id = _make_task(conn, scope, "task-B", lane="main", depends_on=[a_id])
    c_id = _make_task(conn, scope, "task-C", lane="main", depends_on=[b_id])

    records: dict = {}
    result = _run_scheduler(scope, spawn_fn=_make_fake_spawn(records, sleep_s=0.02))

    assert set(result["completed"]) == {
        a_id,
        b_id,
        c_id,
    }, "all three tasks must complete"
    assert result["failed"] == []
    assert result["blocked"] == []

    # Completion order: A finishes before B starts, B finishes before C starts.
    assert (
        records[a_id]["end"] <= records[b_id]["start"] + 1e-6
    ), "A must finish before B starts"
    assert (
        records[b_id]["end"] <= records[c_id]["start"] + 1e-6
    ), "B must finish before C starts"

    assert _task_status(conn, a_id) == "done"
    assert _task_status(conn, b_id) == "done"
    assert _task_status(conn, c_id) == "done"


# ---------------------------------------------------------------------------
# Test 2: Diamond A(data) -> B(backend),C(frontend) -> D(tests)
# ---------------------------------------------------------------------------


def test_diamond_dag_parallelism():
    """Diamond: A done before B,C start; B and C overlap; D starts only after both done."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "sched-diamond"

    a_id = _make_task(conn, scope, "task-A", lane="data")
    b_id = _make_task(conn, scope, "task-B", lane="backend", depends_on=[a_id])
    c_id = _make_task(conn, scope, "task-C", lane="frontend", depends_on=[a_id])
    d_id = _make_task(conn, scope, "task-D", lane="tests", depends_on=[b_id, c_id])

    records: dict = {}
    # Use a longer sleep so B and C have time to truly overlap.
    result = _run_scheduler(scope, spawn_fn=_make_fake_spawn(records, sleep_s=0.1))

    assert set(result["completed"]) == {a_id, b_id, c_id, d_id}
    assert result["failed"] == []
    assert result["blocked"] == []

    # A must finish before B and C start.
    assert (
        records[a_id]["end"] <= records[b_id]["start"] + 1e-6
    ), "A must finish before B starts"
    assert (
        records[a_id]["end"] <= records[c_id]["start"] + 1e-6
    ), "A must finish before C starts"

    # B and C must overlap (true parallelism — different lanes).
    assert _intervals_overlap(
        records[b_id], records[c_id]
    ), f"B and C must run concurrently; B={records[b_id]}, C={records[c_id]}"

    # D must start only after both B and C finish.
    b_end = records[b_id]["end"]
    c_end = records[c_id]["end"]
    last_of_bc = max(b_end, c_end)
    assert (
        records[d_id]["start"] >= last_of_bc - 1e-6
    ), f"D must start after B and C both finish; D.start={records[d_id]['start']}, last_of_bc={last_of_bc}"

    for tid in (a_id, b_id, c_id, d_id):
        assert _task_status(conn, tid) == "done"


# ---------------------------------------------------------------------------
# Test 3: Same-lane serialization
# ---------------------------------------------------------------------------


def test_same_lane_tasks_run_serially():
    """Two ready tasks in the same lane must NOT overlap (<=1 worker per lane)."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "sched-samelane"

    # Both tasks are immediately ready (no deps) but share a lane.
    x_id = _make_task(conn, scope, "task-X", lane="backend")
    y_id = _make_task(conn, scope, "task-Y", lane="backend")

    records: dict = {}
    result = _run_scheduler(scope, spawn_fn=_make_fake_spawn(records, sleep_s=0.05))

    assert set(result["completed"]) == {x_id, y_id}
    assert result["failed"] == []

    # Intervals must NOT overlap — one finished before the other started.
    rx, ry = records[x_id], records[y_id]
    assert not _intervals_overlap(
        rx, ry
    ), f"Same-lane tasks must serialize; X={rx}, Y={ry}"


# ---------------------------------------------------------------------------
# Test 4: Failure cascade — failed task blocks dependents; sibling completes
# ---------------------------------------------------------------------------


def test_failure_cascades_and_sibling_completes():
    """B fails -> D (depends on B,C) is blocked; C (sibling lane) still completes.

    Graph:
        A (data, no deps)
        B (backend, depends on A)  <- will fail
        C (frontend, depends on A)
        D (tests, depends on B and C)
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "sched-fail"

    a_id = _make_task(conn, scope, "task-A", lane="data")
    b_id = _make_task(conn, scope, "task-B", lane="backend", depends_on=[a_id])
    c_id = _make_task(conn, scope, "task-C", lane="frontend", depends_on=[a_id])
    d_id = _make_task(conn, scope, "task-D", lane="tests", depends_on=[b_id, c_id])

    records: dict = {}
    # Fail task B by its id — robust to prompt composition + board context, which
    # quotes sibling task text and would otherwise cause cross-task false matches.
    spawn = _make_fake_spawn(records, sleep_s=0.05, fail_for={b_id})
    result = _run_scheduler(scope, spawn_fn=spawn)

    # A and C must complete.
    assert a_id in result["completed"], "A should complete"
    assert c_id in result["completed"], "C (sibling lane) should still complete"

    # B must be failed.
    assert b_id in result["failed"], "B should be marked failed"

    # D should be blocked (either reported by scheduler or found in DB).
    # D may appear in result["blocked"] or its DB status is "blocked".
    assert _task_status(conn, b_id) == "failed"
    # D depends on both B (failed) and C (done) — it should be blocked.
    d_status = _task_status(conn, d_id)
    assert d_status in ("blocked", "pending"), f"D should be blocked, got {d_status}"
    # If still pending it means the scheduler returned before cascading — check result.
    if d_status == "blocked":
        pass  # DB shows it correctly
    # Either the scheduler returned d_id in blocked list or the DB has it blocked.
    scheduler_blocked = set(result["blocked"])
    db_blocked = d_status == "blocked"
    assert (
        d_id in scheduler_blocked or db_blocked
    ), f"D must be blocked; scheduler blocked={scheduler_blocked}, db_status={d_status}"
