"""Tests for supervisor/cost_cap.py — aggregate cost enforcement for the loop executor.

scheduler.py's DAG frontier loop had NO cost cap at all (unlike the FSM loop in
orchestrator.py, which already refuses to spawn a new stage once cost_usd_so_far >=
max_cost_usd) — a goal's task-DAG could run to any cost. These tests cover the fix in
two layers: CostCapTracker's own contract in isolation, then the SAME wiring pattern
goal_executor.py's _run_loop uses, run against the REAL scheduler_loop (not a mock of
it) — the same "measure the actual mechanism" standard as command_gate's tests.
"""

from __future__ import annotations

import threading
import time

import pytest

from pathly_orchestrator.supervisor.cost_cap import (
    CostCapTracker,
    init_cost_tracker,
    resolve_goal_max_cost_usd,
)


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


def _set_cap(value) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "goal.max_cost_usd", "" if value is None else str(value))


# ── resolve_goal_max_cost_usd ────────────────────────────────────────────────────


def test_unconfigured_resolves_to_no_cap():
    assert resolve_goal_max_cost_usd() is None


def test_configured_value_resolves():
    _set_cap(2.5)
    assert resolve_goal_max_cost_usd() == 2.5


@pytest.mark.parametrize("bad", ["not-a-number", "0", "-5", ""])
def test_invalid_or_non_positive_values_resolve_to_no_cap(bad):
    _set_cap(bad)
    assert resolve_goal_max_cost_usd() is None


def test_a_broken_db_fails_open_to_no_cap(monkeypatch):
    import pathly_orchestrator.db.connection as conn_mod

    monkeypatch.setattr(
        conn_mod, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    assert resolve_goal_max_cost_usd() is None


# ── CostCapTracker ────────────────────────────────────────────────────────────────


def _spawn_returning(cost_usd: float):
    def _spawn(state, instructions, adapter, model, task_run_id, broadcast_fn):
        return {"cost_usd": cost_usd, "outcome": "success"}

    return _spawn


def test_tracker_with_no_cap_never_reports_exceeded():
    tracker = CostCapTracker(None)
    wrapped = tracker.wrap(_spawn_returning(1_000_000.0))
    wrapped(None, "", "claude", "m", "t1", None)

    assert tracker.exceeded() is False


def test_tracker_accumulates_across_calls_and_trips_the_cap():
    tracker = CostCapTracker(1.0)
    wrapped = tracker.wrap(_spawn_returning(0.6))

    wrapped(None, "", "claude", "m", "t1", None)
    assert tracker.exceeded() is False  # 0.6 < 1.0

    wrapped(None, "", "claude", "m", "t2", None)
    assert tracker.exceeded() is True  # 1.2 >= 1.0


def test_a_missing_or_non_dict_outcome_costs_nothing():
    tracker = CostCapTracker(1.0)

    def _spawn_none(*a, **k):
        return None

    wrapped = tracker.wrap(_spawn_none)
    result = wrapped(None, "", "claude", "m", "t1", None)

    assert result is None  # outcome passed through unchanged
    assert tracker.exceeded() is False


def test_wrap_passes_through_the_outcome_unchanged():
    tracker = CostCapTracker(100.0)
    wrapped = tracker.wrap(_spawn_returning(0.1))

    result = wrapped(None, "", "claude", "m", "t1", None)

    assert result == {"cost_usd": 0.1, "outcome": "success"}


def test_wrap_resolves_the_real_default_spawn_when_none_is_given(monkeypatch):
    """scheduler.py's OWN default is `_run_stage_via_terminal` when spawn_fn is None —
    a wrapped None must resolve the SAME default, not silently no-op."""
    import pathly_orchestrator.supervisor as _sup

    monkeypatch.setattr(
        _sup, "_run_stage_via_terminal", lambda *a, **k: {"cost_usd": 3.0}
    )
    tracker = CostCapTracker(1.0)
    wrapped = tracker.wrap(None)

    result = wrapped(None, "", "claude", "m", "t1", None)

    assert result == {"cost_usd": 3.0}
    assert tracker.exceeded() is True


def test_report_sets_error_only_when_exceeded():
    tracker = CostCapTracker(1.0)
    res = {}
    tracker.report(res)
    assert res == {}

    tracker.wrap(_spawn_returning(2.0))(None, "", "claude", "m", "t1", None)
    tracker.report(res)
    assert res["cost_cap_exceeded"] is True
    assert "goal.max_cost_usd" in res["error"]
    assert "2.0" in res["error"] or "2.00" in res["error"]


def test_wrap_is_thread_safe_under_concurrent_workers():
    """A future LaneIsolation goal could run several workers at once — the accumulator
    must not lose updates to a race, even though today's only caller is serial."""
    tracker = CostCapTracker(None)
    wrapped = tracker.wrap(_spawn_returning(0.01))
    threads = [
        threading.Thread(target=wrapped, args=(None, "", "claude", "m", f"t{i}", None))
        for i in range(50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert tracker._total == pytest.approx(0.5)


def test_init_cost_tracker_reads_the_live_setting():
    _set_cap(4.2)
    tracker = init_cost_tracker()
    assert tracker._max == 4.2


# ── Integration: the real scheduler_loop, wired exactly as _run_loop wires it ─────


def _make_task(conn, scope: str, text: str, lane: str = "default") -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn, board="feature", scope=scope, from_agent="builder", type="task", text=text
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


class _FakeState:
    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "claude-sonnet-4-6"


def test_cap_stops_scheduling_further_tasks_via_the_real_scheduler():
    """Three independent-lane tasks, each costing more than half the cap: the SAME
    wiring _run_loop uses (wrap spawn_fn + fold into abort_check) must let at most the
    first one or two run, never all three, against the REAL scheduler frontier loop."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    conn = get_db()
    scope = "cost-cap-scope"
    ids = [_make_task(conn, scope, f"task {i}", lane=f"lane-{i}") for i in range(3)]

    tracker = CostCapTracker(1.0)

    def _real_spawn(state, instructions, adapter, model, task_run_id, broadcast_fn):
        time.sleep(0.02)
        return {"cost_usd": 0.7, "outcome": "success"}

    result = scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=tracker.wrap(_real_spawn),
        abort_check=tracker.exceeded,
    )

    assert len(result["completed"]) < 3, "the cap never stopped the DAG"
    assert tracker.exceeded() is True
    # Everything that didn't complete must be back to pending (never silently lost) or
    # explicitly blocked/deadlocked — not left claimed/in_progress forever.
    for mid in ids:
        status = _task_status(conn, mid)
        assert status in {"done", "pending", "blocked"}, status


def test_no_cap_configured_lets_the_dag_run_to_completion():
    """Fail-open: with no abort_check tied to a cap, three tasks all complete —
    confirms the integration test above is actually exercising the cap, not some
    unrelated scheduler limit."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    conn = get_db()
    scope = "cost-cap-scope-uncapped"
    for i in range(3):
        _make_task(conn, scope, f"task {i}", lane=f"lane-{i}")

    tracker = CostCapTracker(None)  # no cap configured

    def _real_spawn(state, instructions, adapter, model, task_run_id, broadcast_fn):
        return {"cost_usd": 100.0, "outcome": "success"}

    result = scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=tracker.wrap(_real_spawn),
        abort_check=tracker.exceeded,
    )

    assert len(result["completed"]) == 3
