"""T1 — the end-to-end GOLDEN-PATH smoke test (production-readiness P0).

The canonical Pathly loop is: a goal is decomposed into a task DAG, and an executor DRAINS
that DAG to DONE. Every piece exists in isolation — test_dag_scheduler_db.py covers
claim/fail/reclaim at the DB layer; test_runner_fsm_integration.py covers the FSM/team driver —
but NOTHING drove `goal -> executor dispatch -> scheduler drain -> DONE` as one flow. That seam
is exactly the class of place the historical next_state contract bug hid (mocks on BOTH sides of
the FSM<->driver boundary shipped GREEN while the real loop stopped after one step).

These tests drive the REAL drain against the REAL DB and the REAL packaged flow. Only the CLI
spawn is stubbed, so every task makes REAL `pending -> in_progress -> done` transitions and real
dependency/fail-cascade decisions, synchronously in the test thread — no thread-join races.

**Where the drain lives changed in fsm-fan-out Phase E, and these tests followed it.** The chain
used to be `start_goal_run -> _run_loop -> scheduler_loop`, with `_run_loop` a second ENGINE
running as a peer of `orchestrator._loop`. That engine is retired: `executor: loop` now launches
the `goal-loop` FSM flow, whose single DRAINING state declares `parallel_states`, so the drain is
performed by `fan_out.run_stage` INSIDE an FSM stage. So these drive `run_stage` with the real
`goal-loop` YAML and a real goal-scoped RunnerState — one layer down from `start_goal_run`, which
is now a launcher and is covered as such in tests/comms_board/test_comms_goals_run.py.

Driving it goal-scoped is deliberate: it is the shape that catches the frontier bug Phase E had to
fix first (a goal run's FSM topic is its own storage slug, not the board scope its tasks live on).
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
        conn,
        board="feature",
        scope=scope,
        from_agent="architect",
        type="goal",
        text=f"Goal: {scope}",
    )


def _seed_task(conn, scope: str, goal_id: str, text: str, depends_on=None) -> str:
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        goal_id=goal_id,
        depends_on=depends_on,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def _status(conn, mid: str) -> str | None:
    r = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    return r["task_status"] if r else None


def _drain_goal(
    gid: str,
    scope: str,
    tmp_path,
    monkeypatch,
    spawn,
    *,
    event_broadcast_fn=None,
) -> dict:
    """Drain *gid*'s DAG through the REAL goal-loop flow. Returns the drain tally.

    Exactly what `executor: loop` does at runtime, minus the FSM round-trip that decides WHEN
    to run this stage: the real packaged YAML, the real isolation it resolves to, the real
    scheduler, the real DB. `_run_stage_via_terminal` is the one thing stubbed — it is the CLI
    spawn — patched on the `supervisor` package because `fan_out._drain` calls it from there.
    """
    import pathly_orchestrator.supervisor as _sup
    from pathly_orchestrator.supervisor import fan_out
    from pathly_orchestrator.supervisor.goal_decomposer import board_run_topic
    from pathly_orchestrator.supervisor.goal_executor import _LOOP_FLOW
    from pathly_orchestrator.supervisor.state import RunnerState

    def _fake(state, instructions, adapter, model, run_id, broadcast_fn, **_kw):
        return spawn(state, instructions, adapter, model, run_id, broadcast_fn)

    monkeypatch.setattr(_sup, "_run_stage_via_terminal", _fake)

    # The goal run's real shape: an FSM topic that is the goal's own nested storage slug,
    # NOT the board scope — so the frontier has to resolve the board scope from goal_id.
    state = RunnerState(
        topic=board_run_topic("feature", scope, "goals", f"{gid[:8]}-goal"),
        flow=_LOOP_FLOW,
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=600,
        goal_id=gid,
        interactive=False,
        _comms_broadcast_fn=event_broadcast_fn,
    )
    flow_config = fan_out.load_flow_config(_LOOP_FLOW, str(tmp_path))
    assert flow_config, "the packaged goal-loop flow must load"

    merged = fan_out.run_stage(
        state, flow_config, "DRAINING", "unused", "claude", "m", "run-1", None
    )
    assert merged["result"]["fan_out"] is True, "the stage must take the fan-out branch"
    return merged["result"]


def test_goal_loop_drains_dag_to_done(tmp_path, monkeypatch):
    """GOLDEN PATH: a goal + a 3-task DAG (B depends on A; C independent) drains to DONE through
    the REAL loop executor. Assert every task reaches 'done' via real claim->complete, the
    scheduler's own tally agrees, and the dependency is respected (A runs before B)."""
    from pathly_orchestrator.db.connection import get_db

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

    inner = _drain_goal(gid, scope, tmp_path, monkeypatch, fake_spawn)
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
    assert (
        idx_alpha < idx_beta
    ), "BETA (depends on ALPHA) must not be dispatched before ALPHA"


def test_goal_loop_cascades_block_on_failure(tmp_path, monkeypatch):
    """FAIL PATH through the REAL executor: a task whose spawn RAISES fails, and its dependent
    cascades to 'blocked'; an independent task still completes. Exercises fail_task via the real
    loop, not just the DB query — so a broken agent halts its branch, loudly, not silently.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "golden-path-fail"
    gid = _seed_goal(conn, scope)
    a = _seed_task(conn, scope, gid, "task ALPHA")
    b = _seed_task(conn, scope, gid, "task BETA", depends_on=[a])
    c = _seed_task(conn, scope, gid, "task GAMMA")

    def failing_spawn(_state, _instructions, _adapter, _model, run_id, _broadcast_fn):
        # Match by task_id derived from run_id ("sched-<task_id>#<attempt>"), NOT a
        # substring of the composed prompt: with retry (task_retry.py), a failing task's
        # board context (status posts, retry-ladder feedback) can leak "task ALPHA" into
        # a SIBLING task's own prompt (board_context_for pulls recent/relevant board
        # content) — see test_dag_scheduler.py's _make_fake_spawn docstring for the same
        # documented hazard.
        task_id = (
            run_id[len("sched-") :].split("#", 1)[0]
            if run_id.startswith("sched-")
            else run_id
        )
        if task_id == a:
            raise RuntimeError("simulated agent crash")
        return {"cost_usd": 0.0, "session_id": "sess"}

    inner = _drain_goal(gid, scope, tmp_path, monkeypatch, failing_spawn)
    assert a in inner["failed"]
    assert b in inner["blocked"]

    assert _status(conn, a) == "failed"
    assert _status(conn, b) == "blocked"  # cascade from its failed dependency
    assert _status(conn, c) == "done"  # independent branch still drains


def test_goal_loop_fails_task_on_failure_outcome(tmp_path, monkeypatch):
    """SILENT-FAILURE GUARD #2: a spawn that returns NORMALLY but whose outcome signals failure
    (explicit error / non-zero exit / outcome='failed') must mark the task FAILED — not 'done' just
    because the process didn't raise. A clean process exit over broken work is the exact hole.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "golden-path-fail-outcome"
    gid = _seed_goal(conn, scope)
    a = _seed_task(conn, scope, gid, "task ALPHA")
    b = _seed_task(conn, scope, gid, "task BETA", depends_on=[a])
    c = _seed_task(conn, scope, gid, "task GAMMA")

    def outcome_fail_spawn(_s, _instructions, _a, _m, run_id, _b):
        # Match by task_id derived from run_id, not a prompt substring — see the identical
        # note in test_goal_loop_cascades_block_on_failure above.
        task_id = (
            run_id[len("sched-") :].split("#", 1)[0]
            if run_id.startswith("sched-")
            else run_id
        )
        if task_id == a:
            return {"outcome": "failed", "error": "clean exit but the work failed"}
        return {"cost_usd": 0.0}

    inner = _drain_goal(gid, scope, tmp_path, monkeypatch, outcome_fail_spawn)
    assert a in inner["failed"]
    assert (
        _status(conn, a) == "failed"
    )  # failed via the OUTCOME, not a raised exception
    assert _status(conn, b) == "blocked"  # cascade from the failed dependency
    assert _status(conn, c) == "done"  # independent branch still drains


def test_goal_loop_surfaces_deadlocked_dag(tmp_path, monkeypatch):
    """SILENT-FAILURE GUARD: a task with an unsatisfiable dependency — a dangling ref or a cycle —
    never becomes ready, so the frontier drains leaving it pending forever. The executor must
    SURFACE that as deadlocked/blocked, not return a clean-looking result that hides stuck work.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "golden-path-deadlock"
    gid = _seed_goal(conn, scope)
    ok = _seed_task(conn, scope, gid, "task OK")  # no deps -> completes
    dangle = _seed_task(conn, scope, gid, "task DANGLE", depends_on=["nonexistent-id"])
    cyc = _seed_task(conn, scope, gid, "task CYCLE")  # made self-cyclic below
    conn.execute(
        "UPDATE comms_messages SET depends_on=? WHERE id=?", (json.dumps([cyc]), cyc)
    )
    conn.commit()

    inner = _drain_goal(gid, scope, tmp_path, monkeypatch, lambda *_a: {})
    assert _status(conn, ok) == "done"  # the healthy task still drains
    # The two unsatisfiable tasks are surfaced, not silently left pending.
    assert set(inner.get("deadlocked", [])) == {dangle, cyc}, inner
    assert _status(conn, dangle) == "blocked"
    assert _status(conn, cyc) == "blocked"


def test_goal_loop_spawns_headless_not_interactive(tmp_path, monkeypatch):
    """The loop executor must spawn HEADLESS one-shots (interactive=False), like every other goal
    executor (_run_team goal_executor.py, _decompose_consultation goal_decomposer.py). Its RunnerState
    was built WITHOUT interactive=, so it defaulted to True (state.py) — which makes
    _run_stage_via_terminal build an interactive REPL argv that carries NO task prompt. In a live
    Studio run this spawned claude with no work to do; the process exited code 1 (terminal_exit_nonzero)
    and wrote ZERO AGENT_DONE, so the task failed on the exit-code floor and its dependent cascaded to
    blocked. Assert the executor hands the spawn a headless state so the real one-shot argv carries the
    prompt."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "loop-headless"
    gid = _seed_goal(conn, scope)
    _seed_task(conn, scope, gid, "task SOLO")

    seen: dict = {}

    def capture_spawn(state, _instructions, _adapter, _model, _run_id, _bfn):
        seen["interactive"] = state.interactive
        return {"cost_usd": 0.0}

    _drain_goal(gid, scope, tmp_path, monkeypatch, capture_spawn)

    assert seen.get("interactive") is False, (
        "loop executor must spawn headless one-shots (interactive=False), not an interactive REPL "
        "whose argv omits the task prompt"
    )


def test_goal_loop_posts_supervisor_progress(tmp_path, monkeypatch):
    """The loop SUPERVISOR posts a guaranteed start / done status per task to the board.

    Per-task progress is guaranteed SERVER-SIDE, never left to the agent: the supervisor owns
    claim/complete for the loop, so it is the reliable source of mid-run progress; without this a
    headless loop run shows no board progress at all (only the final card-drain), which is exactly
    what a live run exposed. (The single executor gets the equivalent via the /comms/tasks handlers.)
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "loop-progress"
    gid = _seed_goal(conn, scope)
    a = _seed_task(conn, scope, gid, "task ALPHA")
    _seed_task(conn, scope, gid, "task BETA", depends_on=[a])

    _drain_goal(gid, scope, tmp_path, monkeypatch, lambda *_a: {"cost_usd": 0.0})

    rows = conn.execute(
        "SELECT text FROM comms_messages WHERE scope=? AND type='status' AND from_agent='supervisor' "
        "AND deleted_at IS NULL ORDER BY rowid",
        (scope,),
    ).fetchall()
    texts = " || ".join(r["text"] for r in rows)
    assert "Started:" in texts and "task ALPHA" in texts, texts
    assert "Done:" in texts, texts
    # one start + one done for each of the 2 tasks → at least 4 supervisor status posts
    assert (
        len(rows) >= 4
    ), f"expected >=4 supervisor progress posts, got {len(rows)}: {texts}"


def test_goal_loop_broadcast_task_done_carries_text(tmp_path, monkeypatch):
    """The loop's task_done/task_failed SSE events must carry the task TEXT, so Studio can toast a
    meaningful label instead of a bare id. The renderer's task-completion toast reads `data.text`.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "loop-bcast"
    gid = _seed_goal(conn, scope)
    _seed_task(conn, scope, gid, "task ALPHA")

    events: list = []

    def rec(_scope, payload):
        events.append(payload)

    _drain_goal(
        gid,
        scope,
        tmp_path,
        monkeypatch,
        lambda *_a: {"cost_usd": 0.0},
        event_broadcast_fn=rec,
    )
    done = [e for e in events if e.get("event") == "task_done"]
    assert done, f"no task_done event broadcast: {events}"
    assert "task ALPHA" in (done[0].get("text") or ""), done[0]
