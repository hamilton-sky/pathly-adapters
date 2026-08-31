"""Tests for supervisor/task_retry.py — per-task retry/escalation + deadlock detection.

scheduler.py's DAG frontier loop had no retry at all: ANY task failure (a worker
exception, or an outcome reporting failure) called fail_task() immediately and
permanently, cascading 'blocked' to every transitive dependent — the `attempts` column
(incremented by claim_task on every claim) was written but never read anywhere. These
tests cover task_retry.py's decision logic in isolation, then the SAME wiring against
the REAL scheduler_loop (not a mock of it) — the same "measure the actual mechanism"
standard as cost_cap.py's tests.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.supervisor.task_retry import (
    build_retry_context,
    detect_deadlocks,
    resolve_max_attempts,
    resolve_task_failure,
    retry_task,
)


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


def _make_task(
    conn, scope: str, text: str, lane: str = "default", depends_on=None, goal_id=None
) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="builder",
        type="task",
        text=text,
        depends_on=depends_on,
        goal_id=goal_id,
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', lane=? WHERE id=?",
        (lane, mid),
    )
    conn.commit()
    return mid


def _row(conn, mid: str) -> dict:
    return dict(
        conn.execute("SELECT * FROM comms_messages WHERE id=?", (mid,)).fetchone()
    )


# ── resolve_max_attempts ────────────────────────────────────────────────────────


def test_unconfigured_resolves_to_default():
    assert resolve_max_attempts() == 3


def test_configured_value_resolves():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "goal.task_max_attempts", "5")
    assert resolve_max_attempts() == 5


@pytest.mark.parametrize("bad", ["not-a-number", "0", "-2", ""])
def test_invalid_or_non_positive_falls_back_to_default(bad):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "goal.task_max_attempts", bad)
    assert resolve_max_attempts() == 3


def test_a_broken_db_falls_back_to_default(monkeypatch):
    import pathly_orchestrator.db.connection as conn_mod

    monkeypatch.setattr(
        conn_mod, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    assert resolve_max_attempts() == 3


# ── retry_task ───────────────────────────────────────────────────────────────────


def test_retry_task_reverts_to_pending_and_stamps_reason():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    mid = _make_task(conn, "tr-retry", "t")
    conn.execute(
        "UPDATE comms_messages SET task_status='in_progress', claimed_by='x' WHERE id=?",
        (mid,),
    )
    conn.commit()

    retry_task(conn, mid, "it broke")

    row = _row(conn, mid)
    assert row["task_status"] == "pending"
    assert row["claimed_by"] is None
    assert row["fail_reason"] == "it broke"


def test_retry_task_does_not_touch_dependents():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    a = _make_task(conn, "tr-retry-deps", "a")
    b = _make_task(conn, "tr-retry-deps", "b", depends_on=[a])

    retry_task(conn, a, "boom")

    assert _row(conn, b)["task_status"] == "pending"  # unaffected, not cascaded


# ── build_retry_context ────────────────────────────────────────────────────────


def test_first_attempt_has_no_retry_context():
    assert build_retry_context({"attempts": 0, "fail_reason": None}) == ""


def test_retry_after_failure_shows_the_previous_reason():
    block = build_retry_context({"attempts": 1, "fail_reason": "tests failed: foo"})
    assert "Retry attempt 2" in block
    assert "tests failed: foo" in block


def test_attempts_without_a_stashed_reason_has_no_context():
    """Defensive: attempts>0 with no reason (shouldn't happen — retry_task always
    stamps one) still renders nothing rather than an empty/broken block."""
    assert build_retry_context({"attempts": 2, "fail_reason": ""}) == ""


# ── resolve_task_failure ─────────────────────────────────────────────────────────


def test_resolve_task_failure_retries_under_the_limit():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    mid = _make_task(conn, "tr-decide-retry", "t")
    broadcasts: list = []
    statuses: list = []

    decision, blocked = resolve_task_failure(
        conn,
        mid,
        current_attempt=1,
        reason="boom",
        board="feature",
        scope="tr-decide-retry",
        goal_id=None,
        text="t",
        lane="default",
        broadcast=lambda ev, pl: broadcasts.append((ev, pl)),
        post_status=lambda t: statuses.append(t),
        max_attempts=3,
    )

    assert decision == "retried"
    assert blocked == []
    assert _row(conn, mid)["task_status"] == "pending"
    assert _row(conn, mid)["fail_reason"] == "boom"
    assert broadcasts and broadcasts[0][0] == "task_retry"
    assert statuses and "Retrying" in statuses[0]


def test_resolve_task_failure_escalates_at_the_limit():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    parent = _make_task(conn, "tr-decide-escalate", "p")
    dependent = _make_task(conn, "tr-decide-escalate", "d", depends_on=[parent])
    broadcasts: list = []

    decision, blocked = resolve_task_failure(
        conn,
        parent,
        current_attempt=3,
        reason="boom",
        board="feature",
        scope="tr-decide-escalate",
        goal_id=None,
        text="p",
        lane="default",
        broadcast=lambda ev, pl: broadcasts.append((ev, pl)),
        max_attempts=3,
    )

    assert decision == "escalated"
    assert dependent in blocked
    assert _row(conn, parent)["task_status"] == "failed"
    assert _row(conn, dependent)["task_status"] == "blocked"
    assert broadcasts and broadcasts[0][0] == "task_failed"


def test_resolve_task_failure_posts_a_board_escalation_only_when_escalating():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "tr-decide-escbrd"
    mid = _make_task(conn, scope, "t")

    def _count_escalations() -> int:
        return conn.execute(
            "SELECT COUNT(*) n FROM comms_messages WHERE scope=? AND type='escalation'",
            (scope,),
        ).fetchone()["n"]

    resolve_task_failure(
        conn,
        mid,
        current_attempt=1,
        reason="boom",
        board="feature",
        scope=scope,
        goal_id=None,
        text="t",
        lane="default",
        max_attempts=3,
    )
    assert _count_escalations() == 0  # retried — no escalation

    resolve_task_failure(
        conn,
        mid,
        current_attempt=3,
        reason="boom again",
        board="feature",
        scope=scope,
        goal_id=None,
        text="t",
        lane="default",
        max_attempts=3,
    )
    assert _count_escalations() == 1  # escalated


# ── detect_deadlocks ──────────────────────────────────────────────────────────────


def test_detect_deadlocks_marks_unsatisfiable_pending_tasks_blocked():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "tr-deadlock"
    stuck = _make_task(conn, scope, "stuck", depends_on=["nonexistent-id"])

    result = detect_deadlocks(conn, "feature", scope)

    assert result == [stuck]
    assert _row(conn, stuck)["task_status"] == "blocked"
    assert "deadlocked" in _row(conn, stuck)["fail_reason"]


def test_detect_deadlocks_is_noop_when_nothing_pending():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "tr-deadlock-clean"
    mid = _make_task(conn, scope, "t")
    conn.execute("UPDATE comms_messages SET task_status='done' WHERE id=?", (mid,))
    conn.commit()

    assert detect_deadlocks(conn, "feature", scope) == []


def test_detect_deadlocks_scoped_by_goal_id():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "tr-deadlock-goal"
    other = _make_task(
        conn, scope, "other", depends_on=["missing"], goal_id="goal-other"
    )
    mine = _make_task(conn, scope, "mine", depends_on=["missing"], goal_id="goal-mine")

    result = detect_deadlocks(conn, "feature", scope, goal_id="goal-mine")

    assert result == [mine]
    assert _row(conn, other)["task_status"] == "pending"  # untouched


# ── Integration: the real scheduler_loop, wired exactly as scheduler.py wires it ──


class _FakeState:
    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "claude-sonnet-4-6"


def test_scheduler_retries_a_failing_task_then_succeeds():
    """A task that fails twice then succeeds on its 3rd attempt (default
    max_attempts=3) must end up 'done', not 'failed' — proves retry is wired
    end-to-end through the REAL scheduler_loop, not just task_retry's unit contract.
    Also proves the retry-context block reaches the next attempt's prompt."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    conn = get_db()
    scope = "tr-sched-retry"
    mid = _make_task(conn, scope, "flaky task")
    calls = {"n": 0}

    def _flaky_spawn(state, instructions, adapter, model, task_run_id, broadcast_fn):
        calls["n"] += 1
        if calls["n"] < 3:
            return {"outcome": "failed", "error": f"attempt {calls['n']} broke"}
        assert "attempt 2 broke" in instructions
        return {"outcome": "success"}

    result = scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=_flaky_spawn,
    )

    assert calls["n"] == 3
    assert mid in result["completed"]
    assert result["failed"] == []
    row = conn.execute(
        "SELECT task_status, attempts FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    assert row["task_status"] == "done"
    assert row["attempts"] == 3


def test_scheduler_gives_each_retry_attempt_a_distinct_run_id():
    """BILLING CORRECTNESS: run_id is the identity the whole billing chain keys off
    (TERMINAL_SPAWN, the PTY result callback, _reconciliation_window's async patch,
    agent_invocations.run_id). Before this, every attempt of a retried task reused the
    SAME run_id (`sched-<task_id>`) — a late-arriving reconciliation for attempt N could
    fold its real cost onto attempt N+1's row instead of its own
    (invocation_projection matches a BILLING_UPDATE to the MOST RECENT AGENT_DONE
    sharing its run_id, so attempt N+1's row wins). Each attempt must now get its own
    run_id ("sched-<task_id>#<attempt>"), so async billing can never cross attempts."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    conn = get_db()
    scope = "tr-sched-run-id"
    mid = _make_task(conn, scope, "flaky task")
    seen_run_ids: list[str] = []

    def _flaky_spawn(state, instructions, adapter, model, task_run_id, broadcast_fn):
        seen_run_ids.append(task_run_id)
        if len(seen_run_ids) < 3:
            return {"outcome": "failed", "error": "broke"}
        return {"outcome": "success"}

    result = scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=_flaky_spawn,
    )

    assert mid in result["completed"]
    assert len(seen_run_ids) == 3
    assert (
        len(set(seen_run_ids)) == 3
    ), f"run_ids must be unique per attempt: {seen_run_ids}"
    for i, run_id in enumerate(seen_run_ids, start=1):
        assert run_id == f"sched-{mid}#{i}", run_id


def test_scheduler_escalates_after_exhausting_retries():
    """A task that ALWAYS fails must end up permanently 'failed' after exactly
    max_attempts (default 3) attempts, with its dependent cascaded to 'blocked' —
    the original no-retry behavior, just delayed until retries are exhausted."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    conn = get_db()
    scope = "tr-sched-escalate"
    parent = _make_task(conn, scope, "always broken")
    dependent = _make_task(conn, scope, "depends on broken", depends_on=[parent])
    calls = {"n": 0}

    def _always_fails(state, instructions, adapter, model, task_run_id, broadcast_fn):
        calls["n"] += 1
        return {"outcome": "failed", "error": "nope"}

    result = scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=_always_fails,
    )

    assert calls["n"] == 3  # exactly max_attempts, not unbounded
    assert parent in result["failed"]
    dep_status = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (dependent,)
    ).fetchone()["task_status"]
    assert dependent in result["blocked"] or dep_status == "blocked"

    escalations = conn.execute(
        "SELECT COUNT(*) n FROM comms_messages WHERE scope=? AND type='escalation'",
        (scope,),
    ).fetchone()["n"]
    assert escalations == 1


def test_scheduler_detects_deadlock_via_the_shared_extraction():
    """A task depending on a nonexistent id never becomes ready; the frontier loop
    must still terminate immediately (not hang) and mark it blocked+deadlocked, via
    the extracted task_retry.detect_deadlocks — proves the extraction out of
    scheduler.py's inline postscript didn't regress the original behavior."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.isolation import SerialIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    conn = get_db()
    scope = "tr-sched-deadlock"
    stuck = _make_task(conn, scope, "orphan", depends_on=["does-not-exist"])

    def _never_called(*a, **k):
        raise AssertionError("should never be scheduled — never becomes ready")

    result = scheduler_loop(
        _FakeState(),
        board="feature",
        scope=scope,
        isolation=SerialIsolation(),
        spawn_fn=_never_called,
    )

    assert stuck in result["deadlocked"]
    assert stuck in result["blocked"]
    assert (
        conn.execute(
            "SELECT task_status FROM comms_messages WHERE id=?", (stuck,)
        ).fetchone()["task_status"]
        == "blocked"
    )
