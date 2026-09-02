"""supervisor/fan_out.py — the DAG scheduler as an FSM stage executor (fan-out Phase C).

Phase C moves the fan-out machinery INSIDE the FSM: `_loop` no longer calls
`_run_stage_via_terminal` directly, it calls `fan_out.run_stage`, which either delegates to
that same single spawn (no `parallel_states` entry — every packaged flow) or drains the
state's ready tasks through the real `scheduler_loop`.

Phase D turned parallelism on, but **gated**: `lane` isolation is granted only while the
frontier's lane partition audits safe (`lane_partition.AuditedLaneIsolation`), re-checked every
scheduling round. So the Phase-C serial assertions below did NOT have to flip — the tasks in
them declare no `files`, which audits unsafe, so those drains stay serial for a BETTER reason
than a hard pin. The Phase-D tests alongside them prove parallelism does engage once footprints
are declared and disjoint.

Style follows tests/dag_goals/test_dag_scheduler.py: the real `scheduler_loop` with a fake
`spawn_fn` that identifies its task from the task id inside `run_id` — never from a prompt
substring, because the composed prompt carries board context quoting every sibling task's
text (test_golden_path.py documents why that flakes).
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from pathly_orchestrator.supervisor import fan_out


class _FakeState:
    """Minimal stand-in for RunnerState (mirrors test_dag_scheduler.py)."""

    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "claude-sonnet-4-6"
    goal_id = ""
    _abort_flag = False

    def __init__(self, topic: str) -> None:
        self.topic = topic


def _flow(parallel_states=None) -> dict:
    flow = {"states": ["PLANNING", "BUILDING", "DONE"]}
    if parallel_states is not None:
        flow["parallel_states"] = parallel_states
    return flow


def _make_task(conn, scope: str, text: str, lane: str = "default", files=None) -> str:
    """A pending task. `files=None` mirrors every DAG production posts today (undeclared)."""
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="builder",
        type="task",
        text=text,
        lane=lane,
        files=files,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def _task_id_of(run_id: str) -> str:
    """`sched-<task_id>#<attempt>` -> `<task_id>` (task_retry mints one run_id per attempt)."""
    return (
        run_id[len("sched-") :].split("#", 1)[0]
        if run_id.startswith("sched-")
        else run_id
    )


def _make_fake_spawn(
    records: dict, sleep_s: float = 0.05, fail_for=None, cost: float = 0.0
):
    """A spawn_fn recording (start, end) per task id, keyed off run_id — not prompt text."""
    fail_for = fail_for or set()
    lock = threading.Lock()

    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn, **kwargs):
        task_id = _task_id_of(run_id)
        with lock:
            records[task_id] = {
                "start": time.monotonic(),
                "end": None,
                "kwargs": kwargs,
            }
        time.sleep(sleep_s)
        with lock:
            records[task_id]["end"] = time.monotonic()
        if task_id in fail_for:
            return {"outcome": "failed", "error": "intentional", "cost_usd": cost}
        return {"ok": True, "cost_usd": cost}

    return _spawn


def _overlap(r1: dict, r2: dict) -> bool:
    return r1["start"] < r2["end"] and r2["start"] < r1["end"]


# ── parallel_config: the opt-in predicate ────────────────────────────────────


def test_no_parallel_states_key_is_none():
    assert fan_out.parallel_config(_flow(), "BUILDING") is None
    assert fan_out.parallel_config({}, "BUILDING") is None


def test_unlisted_state_is_none():
    assert fan_out.parallel_config(_flow({"PLANNING": {}}), "BUILDING") is None


def test_listed_state_returns_its_config():
    cfg = fan_out.parallel_config(_flow({"BUILDING": {"max_workers": 4}}), "BUILDING")
    assert cfg == {"max_workers": 4}


def test_bodiless_entry_is_opt_in_with_defaults_not_absent():
    """`BUILDING:` (YAML None) must not collapse into "not a parallel state"."""
    assert fan_out.parallel_config(_flow({"BUILDING": None}), "BUILDING") == {}


# ── The non-parallel path: byte-for-byte the old single spawn ────────────────


def test_non_parallel_state_spawns_once_with_identical_arguments(monkeypatch):
    """No parallel_states entry -> exactly one _run_stage_via_terminal, args unchanged."""
    import pathly_orchestrator.supervisor as _sup

    calls: list = []

    def _fake(*args, **kwargs):
        calls.append((args, kwargs))
        return {"cost_usd": 1.5, "session_id": "sess-1"}

    monkeypatch.setattr(_sup, "_run_stage_via_terminal", _fake)
    state = _FakeState("feat")

    result = fan_out.run_stage(
        state,
        _flow(),
        "BUILDING",
        "do the thing",
        "claude",
        "claude-sonnet-4-6",
        "run-7",
        None,
        session="sess-0",
        autonomy=False,
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (state, "do the thing", "claude", "claude-sonnet-4-6", "run-7", None)
    assert kwargs == {"session": "sess-0", "autonomy": False}
    # The single spawn's result is passed through untouched.
    assert result == {"cost_usd": 1.5, "session_id": "sess-1"}


# ── The parallel path: drains the frontier, one at a time ───────────────────


def test_parallel_state_drains_every_ready_task(monkeypatch):
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "fanout-drain"
    ids = [_make_task(conn, scope, f"task-{n}", lane=f"lane-{n}") for n in range(3)]

    records: dict = {}
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal",
        _make_fake_spawn(records, sleep_s=0.02, cost=0.25),
    )

    result = fan_out.run_stage(
        _FakeState(scope),
        _flow({"BUILDING": {"max_workers": 4, "isolation": "lane"}}),
        "BUILDING",
        "unused — the fan-out composes its own per-task prompts",
        "claude",
        "claude-sonnet-4-6",
        "run-7",
        None,
    )

    assert set(records) == set(ids), "every ready task must be spawned"
    assert result["outcome"] == "success"
    assert result["cost_usd"] == pytest.approx(0.75), "per-task costs are summed"
    assert (
        result["session_id"] is None
    ), "a fan-out cannot carry one session across N agents"
    assert set(result["result"]["completed"]) == set(ids)


def test_serial_isolation_is_pinned_even_when_yaml_asks_for_lane(monkeypatch):
    """Three ready tasks in three lanes, never two at once — because none declares `files`.

    Under Phase C this held because `SerialIsolation` was pinned unconditionally. Under
    Phase D it holds because the audit gate refuses to widen concurrency for a frontier
    whose footprints are undeclared. Same observable behaviour, sounder reason: this is the
    exact shape of every DAG production posts today.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "fanout-serial"
    ids = [_make_task(conn, scope, f"task-{n}", lane=f"lane-{n}") for n in range(3)]

    records: dict = {}
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal",
        _make_fake_spawn(records, sleep_s=0.05),
    )

    fan_out.run_stage(
        _FakeState(scope),
        _flow({"BUILDING": {"isolation": "lane"}}),
        "BUILDING",
        "x",
        "claude",
        "m",
        "run-7",
        None,
    )

    assert set(records) == set(ids)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            assert not _overlap(
                records[a], records[b]
            ), "SerialIsolation must serialise even distinct lanes in Phase C"


def test_a_failing_task_makes_the_stage_report_failure(monkeypatch, tmp_path):
    """One escalated task -> outcome 'failed'; require_tasks_done blocks the transition.

    The stage does NOT hard-fail: `_loop` surfaces a self-reported failure as a
    RUNNER_WARNING and lets the gate decide, which is the documented join semantics.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    conn = get_db()
    set_setting(conn, "goal.task_max_attempts", "1")  # escalate on first failure
    scope = "fanout-failure"
    ok_id = _make_task(conn, scope, "task-ok", lane="a")
    bad_id = _make_task(conn, scope, "task-bad", lane="b")

    records: dict = {}
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal",
        _make_fake_spawn(records, sleep_s=0.01, fail_for={bad_id}),
    )

    result = fan_out.run_stage(
        _FakeState(scope),
        _flow({"BUILDING": {}}),
        "BUILDING",
        "x",
        "claude",
        "m",
        "run-7",
        None,
    )

    assert result["outcome"] == "failed"
    assert bad_id in result["result"]["failed"]
    assert ok_id in result["result"]["completed"], "a sibling lane still completes"

    # The join: require_tasks_done sees the unfinished task and blocks the transition.
    from pathly_orchestrator.db.queries.comms_tasks import (
        count_incomplete_tasks_for_scope,
    )

    assert count_incomplete_tasks_for_scope(conn, "feature", scope) >= 1

    from pathly_orchestrator.fsm.gates.tasks import check_require_tasks_done

    # The gate exactly as team-build.flow.yaml declares it (it writes on_fail feedback).
    blocked = check_require_tasks_done(
        {"type": "require_tasks_done", "on_fail": "INCOMPLETE_TASKS.md"},
        tmp_path,
        "BUILDING",
        "REVIEWING",
        goal_id=None,
        feature_scope=scope,
        board="feature",
    )
    assert blocked is not None, "the gate — not the stage — is what stops the flow"
    assert blocked["gate_failed"] == "require_tasks_done"


def test_abort_mid_drain_stops_scheduling(monkeypatch):
    """The FSM's own _abort_flag is folded into scheduler_loop's abort_check."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "fanout-abort"
    for n in range(4):
        _make_task(conn, scope, f"task-{n}", lane=f"lane-{n}")

    state = _FakeState(scope)
    spawned: list = []

    def _spawn(s, instructions, adapter, model, run_id, broadcast_fn, **kwargs):
        spawned.append(_task_id_of(run_id))
        state._abort_flag = True  # abort after the first task
        return {"ok": True}

    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal", _spawn
    )

    fan_out.run_stage(
        state, _flow({"BUILDING": {}}), "BUILDING", "x", "claude", "m", "run-7", None
    )

    assert len(spawned) == 1, f"abort must stop further spawns, got {spawned}"


def test_workers_get_the_stages_autonomy_and_no_session(monkeypatch):
    """A fan-out worker inherits the stage's autonomy posture; session is always None."""
    from pathly_orchestrator.db.connection import get_db

    scope = "fanout-kwargs"
    _make_task(get_db(), scope, "task-a", lane="a")

    records: dict = {}
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal",
        _make_fake_spawn(records, sleep_s=0.0),
    )

    fan_out.run_stage(
        _FakeState(scope),
        _flow({"BUILDING": {}}),
        "BUILDING",
        "x",
        "claude",
        "m",
        "run-7",
        None,
        session="sess-must-not-leak",
        autonomy=False,
    )

    (record,) = records.values()
    assert record["kwargs"] == {"session": None, "autonomy": False}


# ── Production is provably unchanged ─────────────────────────────────────────


def test_no_packaged_flow_declares_parallel_states():
    """Phase C changes the ENGINE, not any flow — so no run can take the fan-out branch.

    This is what makes "behaviour is byte-identical" a fact rather than a claim; the
    first flow to opt in is Phase D's, deliberately and with measurement behind it.
    """
    import yaml

    from tests._paths import SRC

    flow_dir = SRC / "pathly_data" / "core" / "flows"
    flows = sorted(flow_dir.glob("*.flow.yaml"))
    assert len(flows) == 9, "guard against this check silently finding nothing"
    for path in flows:
        flow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for state_name in flow.get("states") or []:
            assert fan_out.parallel_config(flow, state_name) is None, path.name


def test_load_flow_config_degrades_to_the_single_spawn_path():
    """An unloadable flow yields {} — i.e. no parallel state — never an exception.

    `_loop` never needed the flow dict before Phase C; a failure to read it must not be
    able to fail a run that would previously have proceeded.
    """
    assert fan_out.load_flow_config("no-such-flow", "/nonexistent") == {}
    assert fan_out.parallel_config({}, "BUILDING") is None


# ── Phase D: parallelism, gated on the lane partition auditing safe ──────────


def _drain_parallel(monkeypatch, scope, tasks, config, sleep_s=0.12):
    """Drain `tasks` [(lane, files)] through run_stage with `config`; return the records."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    ids = [
        _make_task(conn, scope, f"task-{n}", lane=lane, files=files)
        for n, (lane, files) in enumerate(tasks)
    ]
    records: dict = {}
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal",
        _make_fake_spawn(records, sleep_s=sleep_s),
    )
    fan_out.run_stage(
        _FakeState(scope),
        _flow({"BUILDING": config}),
        "BUILDING",
        "x",
        "claude",
        "m",
        "run-7",
        None,
    )
    return ids, records


def _max_concurrent(records: dict) -> int:
    """Peak overlap across the recorded (start, end) intervals."""
    events = []
    for r in records.values():
        events.append((r["start"], 1))
        events.append((r["end"], -1))
    events.sort()
    peak = running = 0
    for _, delta in events:
        running += delta
        peak = max(peak, running)
    return peak


def test_declared_disjoint_footprints_actually_run_in_parallel(monkeypatch):
    """THE Phase-D change: lanes with disjoint declared files run concurrently.

    This is the assertion Phase C could not make. If it fails, parallelism is off.
    """
    ids, records = _drain_parallel(
        monkeypatch,
        "d-parallel",
        [
            ("backend", ["src/api.py"]),
            ("frontend", ["web/app.tsx"]),
            ("docs", ["README.md"]),
        ],
        {"isolation": "lane"},
    )
    assert set(records) == set(ids)
    assert _max_concurrent(records) > 1, "declared-disjoint lanes must overlap"


def test_max_workers_caps_the_concurrency(monkeypatch):
    """A flow's declared ceiling is honoured, not just the lane count."""
    _, records = _drain_parallel(
        monkeypatch,
        "d-cap",
        [(f"lane-{n}", [f"src/mod_{n}.py"]) for n in range(4)],
        {"isolation": "lane", "max_workers": 2},
    )
    peak = _max_concurrent(records)
    # BOTH halves matter: `<= 2` alone passes trivially under serial isolation, so it would
    # not notice the cap being applied to a drain that never went parallel in the first place.
    assert peak > 1, "4 disjoint lanes must run in parallel at all"
    assert peak <= 2, f"max_workers=2 must bound the peak, saw {peak}"


def test_a_cross_lane_conflict_keeps_the_drain_serial(monkeypatch):
    """Declared footprints that OVERLAP across lanes must not run at once."""
    _, records = _drain_parallel(
        monkeypatch,
        "d-conflict",
        [("backend", ["src/api.py"]), ("frontend", ["src/api.py"])],
        {"isolation": "lane"},
    )
    assert _max_concurrent(records) == 1, "an overlapping partition must stay serial"


def test_one_undeclared_task_keeps_the_whole_drain_serial(monkeypatch):
    """An unknown footprint overlaps everything — it cannot be reasoned around."""
    _, records = _drain_parallel(
        monkeypatch,
        "d-undeclared",
        [("backend", ["src/api.py"]), ("frontend", None)],
        {"isolation": "lane"},
    )
    assert _max_concurrent(records) == 1


def test_isolation_serial_is_obeyed_even_with_perfect_footprints(monkeypatch):
    """`isolation: serial` is a literal instruction, not a hint."""
    _, records = _drain_parallel(
        monkeypatch,
        "d-serial",
        [("backend", ["src/api.py"]), ("frontend", ["web/app.tsx"])],
        {"isolation": "serial"},
    )
    assert _max_concurrent(records) == 1


def test_isolation_worktree_degrades_to_serial_rather_than_crashing(monkeypatch):
    """`WorktreeIsolation` is still a stub that raises — a run must not die on it."""
    _, records = _drain_parallel(
        monkeypatch,
        "d-worktree",
        [("backend", ["src/api.py"]), ("frontend", ["web/app.tsx"])],
        {"isolation": "worktree"},
    )
    assert _max_concurrent(records) == 1, "the stub must degrade, not raise"


def test_the_audit_is_re_run_every_round_not_once(monkeypatch):
    """The frontier GROWS as tasks complete — a one-time check would miss a late conflict.

    `first` runs alone; completing it unblocks TWO dependents that both declare the same
    file in different lanes. A drain that audited only at start would see a safe frontier
    and then run the conflicting pair concurrently.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "d-reaudit"
    first = _make_task(conn, scope, "first", lane="seed", files=["src/seed.py"])
    for n in range(2):
        mid = _make_task(
            conn, scope, f"dependent-{n}", lane=f"lane-{n}", files=["src/shared.py"]
        )
        conn.execute(
            "UPDATE comms_messages SET depends_on=? WHERE id=?",
            (json.dumps([first]), mid),
        )
    conn.commit()

    records: dict = {}
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor._run_stage_via_terminal",
        _make_fake_spawn(records, sleep_s=0.12),
    )
    fan_out.run_stage(
        _FakeState(scope),
        _flow({"BUILDING": {"isolation": "lane"}}),
        "BUILDING",
        "x",
        "claude",
        "m",
        "run-7",
        None,
    )

    assert len(records) == 3, "all three tasks must run"
    assert _max_concurrent(records) == 1, (
        "the conflicting dependents became ready only AFTER the first task finished — "
        "catching them requires re-auditing each round"
    )


def test_no_packaged_flow_opts_into_parallelism_yet():
    """Phase D ships the ENGINE. No shipped flow declares `parallel_states`, so production
    behaviour is still unchanged — opting a flow in is a separate, deliberate decision.
    """
    import yaml

    from tests._paths import SRC

    flows = sorted((SRC / "pathly_data" / "core" / "flows").glob("*.flow.yaml"))
    assert len(flows) == 9
    for path in flows:
        flow = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "parallel_states" not in flow, path.name
