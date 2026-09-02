"""One drain, two callers — `supervisor/drain.py` (fan-out convergence).

`fan_out._drain` (an FSM stage with `parallel_states`) and `goal_executor._run_loop`
(`executor: loop`) both drive `scheduler_loop`, and each used to carry its own copy of the
same scaffolding: make a cost tracker, wrap `spawn_fn` with it, OR `tracker.exceeded()` into
an abort predicate, call the loop. Duplicated scaffolding is how two paths drift — a fix to
one silently misses the other.

These tests pin what the shared helper guarantees for BOTH callers: the cost cap applies
whether or not the caller remembered it, the spawn is wrapped exactly once (a second wrap
would double-count every task's cost), and a caller's own abort predicate still works.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.supervisor.drain import drain_frontier
from pathly_orchestrator.supervisor.isolation import SerialIsolation


class _FakeState:
    project_root = "/repo"
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "m"

    def __init__(self, topic: str) -> None:
        self.topic = topic


def _task(conn, scope, text, lane=None, files=None):
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        lane=lane,
        files=files,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


def _spawn_costing(amount: float, calls: list):
    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        calls.append(run_id)
        return {"ok": True, "cost_usd": amount}

    return _spawn


def test_the_tracker_accumulates_real_spend_and_is_returned():
    """The caller reads `.total` off the returned tracker — no second accumulator."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "drain-cost"
    for n in range(3):
        _task(conn, scope, f"t{n}")

    calls: list = []
    _, tracker = drain_frontier(
        _FakeState(scope),
        "feature",
        scope,
        isolation=SerialIsolation(),
        spawn_fn=_spawn_costing(0.5, calls),
    )
    assert len(calls) == 3
    assert tracker.total == pytest.approx(1.5)


def test_the_spawn_is_wrapped_exactly_once():
    """A caller that ALSO wrapped would double every task's cost.

    `drain_frontier` owns the wrapping, so callers pass the bare spawn. This asserts the
    total is the plain sum — 3 x 0.5, not 3 x 1.0.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "drain-once"
    for n in range(3):
        _task(conn, scope, f"t{n}")

    _, tracker = drain_frontier(
        _FakeState(scope),
        "feature",
        scope,
        isolation=SerialIsolation(),
        spawn_fn=_spawn_costing(0.5, []),
    )
    assert tracker.total == pytest.approx(1.5), "cost counted twice => double-wrapped"


def test_the_cost_cap_applies_without_the_caller_asking():
    """The cap is folded in here, so neither caller can forget it.

    `abort_check` below reports only "no reason of my own to stop" — the drain must still
    halt once the configured cap is blown.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    conn = get_db()
    set_setting(conn, "goal.max_cost_usd", "1.0")
    scope = "drain-cap"
    for n in range(6):
        _task(conn, scope, f"t{n}")

    calls: list = []
    _, tracker = drain_frontier(
        _FakeState(scope),
        "feature",
        scope,
        isolation=SerialIsolation(),
        spawn_fn=_spawn_costing(0.6, calls),
        abort_check=lambda: False,
    )
    assert tracker.exceeded()
    assert len(calls) < 6, "the cap must stop further scheduling"


def test_a_callers_own_abort_predicate_still_stops_the_drain():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "drain-abort"
    for n in range(4):
        _task(conn, scope, f"t{n}")

    calls: list = []
    stop = {"now": False}

    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        calls.append(run_id)
        stop["now"] = True
        return {"ok": True}

    drain_frontier(
        _FakeState(scope),
        "feature",
        scope,
        isolation=SerialIsolation(),
        spawn_fn=_spawn,
        abort_check=lambda: stop["now"],
    )
    assert len(calls) == 1


def test_a_raising_abort_predicate_does_not_strand_the_drain():
    """A caller's broken predicate must not wedge a run — the cap still gets its say."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "drain-badabort"
    _task(conn, scope, "t0")

    def _boom() -> bool:
        raise RuntimeError("predicate is broken")

    raw, _ = drain_frontier(
        _FakeState(scope),
        "feature",
        scope,
        isolation=SerialIsolation(),
        spawn_fn=_spawn_costing(0.0, []),
        abort_check=_boom,
    )
    assert len(raw.get("completed") or []) == 1


# ── The loop executor now shares the FSM path's audit-gated isolation ────────


def test_loop_executor_uses_the_audited_isolation_not_a_bare_serial_pin():
    """`executor: loop` gets the SAME Phase-D gate an FSM fan-out stage gets.

    Asserted on the type rather than on timing: the timing behaviour is already covered by
    test_fan_out.py, and what matters here is that the loop is no longer hardcoded to a
    plain SerialIsolation that could never become parallel.
    """
    import inspect

    from pathly_orchestrator.supervisor import goal_executor

    src = inspect.getsource(goal_executor._run_loop)
    assert "AuditedLaneIsolation(" in src
    assert "SerialIsolation()" not in src, "the hardcoded serial pin should be gone"


def _called_names(module) -> set[str]:
    """Every function NAME actually called in `module` — parsed, not grepped.

    A text search would match the module docstring, which draws `scheduler_loop(...)` in an
    ASCII diagram; the AST only sees real calls.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_both_callers_go_through_the_shared_drain():
    """The convergence itself: neither caller CALLS scheduler_loop any more."""
    from pathly_orchestrator.supervisor import fan_out, goal_executor

    for mod in (fan_out, goal_executor):
        called = _called_names(mod)
        assert "drain_frontier" in called, f"{mod.__name__} must use the shared drain"
        assert (
            "scheduler_loop" not in called
        ), f"{mod.__name__} still calls scheduler_loop directly"


def test_the_shared_drain_is_the_only_scheduler_loop_caller_in_the_supervisor():
    """One call site, checked across the whole supervisor package rather than two files."""
    import ast
    import pathlib

    from tests._paths import SRC

    sup = SRC / "pathly_orchestrator" / "supervisor"
    callers = []
    for path in sorted(sup.glob("*.py")):
        tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "scheduler_loop"
            ):
                callers.append(path.name)
    assert callers == ["drain.py"], f"scheduler_loop is called from {callers}"


# ── The extracted goal-home resolver ─────────────────────────────────────────


def test_resolve_goal_home_degrades_to_the_board_scope():
    """Best-effort by design: a goal run must not die because storage could not resolve."""
    from pathly_orchestrator.supervisor.slug import resolve_goal_home

    assert resolve_goal_home("", "feature", "my-scope", "g1") == ("my-scope", None)
    assert resolve_goal_home("/root", "feature", "my-scope", "") == ("my-scope", None)


def test_resolve_goal_home_returns_a_slug_and_dir_for_a_real_goal(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.supervisor.slug import resolve_goal_home

    conn = get_db()
    goal_id = post_message(
        conn,
        board="feature",
        scope="feat",
        from_agent="planner",
        type="goal",
        text="Ship the widget",
    )
    slug, goal_dir = resolve_goal_home(str(tmp_path), "feature", "feat", goal_id)
    assert slug and slug != "feat", "a real goal resolves to its own slug"
    assert goal_dir is not None and "goals" in goal_dir
