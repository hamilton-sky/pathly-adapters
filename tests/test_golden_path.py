"""T1 — the end-to-end GOLDEN-PATH smoke test (production-readiness P0).

The canonical Pathly loop is: a goal is decomposed into a task DAG, and an executor DRAINS
that DAG to DONE. Every piece exists in isolation — test_dag_scheduler_db.py covers
claim/fail/reclaim at the DB layer; test_runner_fsm_integration.py covers the FSM/team driver —
but NOTHING drove `goal -> executor dispatch -> scheduler drain -> DONE` as one flow. That seam
is exactly the class of place the historical next_state contract bug hid (mocks on BOTH sides of
the FSM<->driver boundary shipped GREEN while the real loop stopped after one step).

These tests drive the REAL `start_goal_run -> _run_loop -> scheduler_loop` against the REAL DB and
REAL SerialIsolation. Only the CLI spawn (`spawn_fn`) is stubbed, so every task makes REAL
`pending -> in_progress -> done` transitions and real dependency/fail-cascade decisions. `block=True`
runs the drain synchronously in the test thread — no thread-join races.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Posting a message must not spawn a background embed thread mid-test."""
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _seed_goal(conn, scope: str) -> str:
    """Insert a real goal row (executor is set via executor_override at dispatch)."""
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        conn, board="feature", scope=scope, from_agent="architect",
        type="goal", text=f"Goal: {scope}",
    )


def _seed_task(conn, scope: str, goal_id: str, text: str, depends_on=None) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn, board="feature", scope=scope, from_agent="planner",
        type="task", text=text, goal_id=goal_id, depends_on=depends_on,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def _status(conn, mid: str) -> str | None:
    r = conn.execute("SELECT task_status FROM comms_messages WHERE id=?", (mid,)).fetchone()
    return r["task_status"] if r else None


def test_goal_loop_drains_dag_to_done(tmp_path):
    """GOLDEN PATH: a goal + a 3-task DAG (B depends on A; C independent) drains to DONE through
    the REAL loop executor. Assert every task reaches 'done' via real claim->complete, the
    scheduler's own tally agrees, and the dependency is respected (A runs before B)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    conn = get_db()
    scope = "golden-path-drain"
    gid = _seed_goal(conn, scope)
    a = _seed_task(conn, scope, gid, "task ALPHA")
    b = _seed_task(conn, scope, gid, "task BETA", depends_on=[a])
    c = _seed_task(conn, scope, gid, "task GAMMA")

    spawn_order: list[str] = []

    def fake_spawn(_state, instructions, _adapter, _model, _run_id, _broadcast_fn):
        # No real CLI: record which task ran (its text is embedded in the composed prompt),
        # return a success outcome so the scheduler's real complete_task fires.
        spawn_order.append(instructions)
        return {"cost_usd": 0.0, "session_id": f"sess-{len(spawn_order)}"}

    result = start_goal_run(
        gid, executor_override="loop", project_root=str(tmp_path),
        spawn_fn=fake_spawn, block=True,
    )

    assert result["ok"] is True, result
    inner = result["result"]  # _work() dict: completed/failed/blocked + executor/goal_id/run_id
    assert set(inner["completed"]) == {a, b, c}, inner
    assert inner["failed"] == []
    assert inner["blocked"] == []

    # Real DB transitions landed.
    assert _status(conn, a) == "done"
    assert _status(conn, b) == "done"
    assert _status(conn, c) == "done"

    # Dependency respected: ALPHA was dispatched before BETA (SerialIsolation, real frontier).
    assert len(spawn_order) == 3
    idx_alpha = next(i for i, ins in enumerate(spawn_order) if "task ALPHA" in ins)
    idx_beta = next(i for i, ins in enumerate(spawn_order) if "task BETA" in ins)
    assert idx_alpha < idx_beta, "BETA (depends on ALPHA) must not be dispatched before ALPHA"


def test_goal_loop_cascades_block_on_failure(tmp_path):
    """FAIL PATH through the REAL executor: a task whose spawn RAISES fails, and its dependent
    cascades to 'blocked'; an independent task still completes. Exercises fail_task via the real
    loop, not just the DB query — so a broken agent halts its branch, loudly, not silently."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    conn = get_db()
    scope = "golden-path-fail"
    gid = _seed_goal(conn, scope)
    a = _seed_task(conn, scope, gid, "task ALPHA")
    b = _seed_task(conn, scope, gid, "task BETA", depends_on=[a])
    c = _seed_task(conn, scope, gid, "task GAMMA")

    def failing_spawn(_state, instructions, _adapter, _model, _run_id, _broadcast_fn):
        if "task ALPHA" in instructions:
            raise RuntimeError("simulated agent crash")
        return {"cost_usd": 0.0, "session_id": "sess"}

    result = start_goal_run(
        gid, executor_override="loop", project_root=str(tmp_path),
        spawn_fn=failing_spawn, block=True,
    )

    assert result["ok"] is True, result
    inner = result["result"]
    assert a in inner["failed"]
    assert b in inner["blocked"]

    assert _status(conn, a) == "failed"
    assert _status(conn, b) == "blocked"   # cascade from its failed dependency
    assert _status(conn, c) == "done"      # independent branch still drains


def test_goal_loop_fails_task_on_failure_outcome(tmp_path):
    """SILENT-FAILURE GUARD #2: a spawn that returns NORMALLY but whose outcome signals failure
    (explicit error / non-zero exit / outcome='failed') must mark the task FAILED — not 'done' just
    because the process didn't raise. A clean process exit over broken work is the exact hole."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    conn = get_db()
    scope = "golden-path-fail-outcome"
    gid = _seed_goal(conn, scope)
    a = _seed_task(conn, scope, gid, "task ALPHA")
    b = _seed_task(conn, scope, gid, "task BETA", depends_on=[a])
    c = _seed_task(conn, scope, gid, "task GAMMA")

    def outcome_fail_spawn(_s, instructions, _a, _m, _r, _b):
        if "task ALPHA" in instructions:
            return {"outcome": "failed", "error": "clean exit but the work failed"}
        return {"cost_usd": 0.0}

    result = start_goal_run(
        gid, executor_override="loop", project_root=str(tmp_path),
        spawn_fn=outcome_fail_spawn, block=True,
    )

    assert result["ok"] is True, result
    assert a in result["result"]["failed"]
    assert _status(conn, a) == "failed"     # failed via the OUTCOME, not a raised exception
    assert _status(conn, b) == "blocked"    # cascade from the failed dependency
    assert _status(conn, c) == "done"       # independent branch still drains


def test_goal_loop_surfaces_deadlocked_dag(tmp_path):
    """SILENT-FAILURE GUARD: a task with an unsatisfiable dependency — a dangling ref or a cycle —
    never becomes ready, so the frontier drains leaving it pending forever. The executor must
    SURFACE that as deadlocked/blocked, not return a clean-looking result that hides stuck work."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    conn = get_db()
    scope = "golden-path-deadlock"
    gid = _seed_goal(conn, scope)
    ok = _seed_task(conn, scope, gid, "task OK")                       # no deps -> completes
    dangle = _seed_task(conn, scope, gid, "task DANGLE", depends_on=["nonexistent-id"])
    cyc = _seed_task(conn, scope, gid, "task CYCLE")                   # made self-cyclic below
    conn.execute("UPDATE comms_messages SET depends_on=? WHERE id=?", (json.dumps([cyc]), cyc))
    conn.commit()

    result = start_goal_run(
        gid, executor_override="loop", project_root=str(tmp_path),
        spawn_fn=lambda *_a: {}, block=True,
    )

    assert result["ok"] is True, result
    inner = result["result"]
    assert _status(conn, ok) == "done"            # the healthy task still drains
    # The two unsatisfiable tasks are surfaced, not silently left pending.
    assert set(inner.get("deadlocked", [])) == {dangle, cyc}, inner
    assert _status(conn, dangle) == "blocked"
    assert _status(conn, cyc) == "blocked"
