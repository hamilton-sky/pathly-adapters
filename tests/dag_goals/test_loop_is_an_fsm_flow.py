"""fsm-fan-out Phase E — `executor: loop` stops being a second engine.

The convergence goal was always "one engine, one authority (the DB)". Phases A-D moved the
fan-out INSIDE the FSM and turned parallelism on; what remained was the last rival engine,
``goal_executor._run_loop``, which built its own ``RunnerState`` and drove ``scheduler_loop``
top-level as a peer of ``orchestrator._loop``.

Phase E retires that engine WITHOUT retiring the product. The plan said the loop should
"become a parallel flow", meaning ``team-build``; these tests pin why it became its OWN flow
instead — ``loop`` is a flat drain and ``team-build`` is a reviewed pipeline, so collapsing
them would silently change what a user who chose ``loop`` gets.

Two prerequisites the plan did not anticipate are pinned here too, because Phase E is a
silent no-op without either of them:

* a goal-scoped run's FSM topic is NOT its board scope, so draining by the topic found an
  empty frontier;
* a DAG task's prompt never had its fragment placeholders substituted, so the task agent was
  told to write its ``AGENT_DONE`` under the literal string ``<fsm_feature>``.
"""

from __future__ import annotations

import re

import pytest
import yaml

from tests._paths import SRC

_FLOW = SRC / "pathly_data" / "core" / "flows" / "goal-loop.flow.yaml"


class _FakeState:
    """Minimal RunnerState stand-in — the attributes the drain path actually reads."""

    project_root = ""
    board_scope = ""
    db_path = ""
    fsm_port = 8765
    current_adapter = "claude"
    model = "m"
    storage_path = ""

    def __init__(self, topic: str, goal_id: str = "") -> None:
        self.topic = topic
        self.goal_id = goal_id


# ── Prerequisite 1: the frontier is the BOARD's, not the topic's ─────────────


def _goal_on(scope: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    goal_id = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text="Ship the widget",
    )
    conn.commit()
    return goal_id


def test_a_plain_feature_run_still_drains_its_own_topic():
    """The unchanged half: for a feature pipeline, topic IS the board scope."""
    from pathly_orchestrator.supervisor.fan_out import _frontier_scope

    assert _frontier_scope(_FakeState("plain-feature")) == "plain-feature"


def test_a_goal_run_drains_the_BOARD_not_its_own_storage_slug():
    """The bug Phase E would otherwise have shipped as a silent no-op.

    A goal run's FSM topic is ``features/<feature>/goals/<slug>`` — its own storage home, so
    two goals on one board don't collide. Its TASKS live on the parent board at
    ``scope=<feature>``. ``get_ready_tasks`` ANDs ``scope IN (…)`` with ``goal_id``, so
    draining by the topic returns nothing at all and the stage "completes" having run zero
    tasks.
    """
    from pathly_orchestrator.supervisor.fan_out import _frontier_scope
    from pathly_orchestrator.supervisor.goal_decomposer import board_run_topic

    scope = "fanout-goal-scope"
    goal_id = _goal_on(scope)
    topic = board_run_topic("feature", scope, "goals", "ship-the-widget")

    assert topic != scope, "precondition: the goal's topic is its own nested slug"
    assert _frontier_scope(_FakeState(topic, goal_id)) == scope


def test_the_frontier_scope_degrades_to_the_topic_rather_than_raising():
    """Best-effort by design — an unresolvable board scope must not kill a stage."""
    from pathly_orchestrator.supervisor.fan_out import _frontier_scope

    assert _frontier_scope(_FakeState("no-such-goal-run", "not-a-goal-id"))


def test_the_frontier_and_the_join_agree_for_a_goal_run():
    """`require_tasks_done` counts by goal_id when a run has one, which is what the fan-out
    scopes by — so the drain and the join cannot disagree about whose tasks these are.
    """
    import inspect

    from pathly_orchestrator.fsm.gates import tasks as _tasks

    src = inspect.getsource(_tasks._count_incomplete)
    assert "if goal_id:" in src, "the join must prefer goal_id over the scope"


# ── Prerequisite 2: a DAG task prompt is fully substituted ───────────────────


def _task_prompt() -> str:
    from pathly_orchestrator.supervisor.task_prompt import build_task_prompt

    return build_task_prompt(
        {"id": "t1", "text": "do the thing"},
        _FakeState("prompt-feature"),
        "feature",
        "prompt-feature",
        adapter="claude",
        task_id="t1",
    )


@pytest.mark.parametrize(
    "placeholder", ["<fsm_feature>", "<feature_path>", "<run_category>", "<board>"]
)
def test_a_dag_task_prompt_has_no_unsubstituted_fragment_placeholders(placeholder):
    """`completion-report` keys its AGENT_DONE off `<fsm_feature>`.

    Left literal, the event is mis-keyed: no projected invocation lands on the run, so the
    task is unbilled and absent from the Monitor — the exact failure the root CLAUDE.md
    documents for board runs, which `board_run._inject_board_prompt_vars` fixed there and
    nothing fixed on the DAG path.

    `<feature>` is deliberately NOT in this list: the runner-contract block contains the
    literal string `team <feature> …` as illustrative prose, on this path and the FSM path
    alike, and substituting inside it would corrupt the example.
    """
    assert placeholder not in _task_prompt()


def test_a_dag_task_is_stamped_as_a_loop_run_not_a_flow_run():
    """The Monitor buckets RECENT runs on this stamp.

    It used to come from `terminal_reconcile`'s synthetic AGENT_DONE, which only fires for an
    executor-owned run. Under Phase E these tasks run inside an FSM stage, where that safety
    net is off — so the prompt itself has to carry it.
    """
    prompt = _task_prompt()
    # The completion-report fragment writes `category` into its AGENT_DONE body.
    assert re.search(r"category['\"]?\s*[:=]\s*['\"]loop['\"]", prompt), prompt[:0] or (
        "the task prompt must stamp category=loop"
    )


def test_a_dag_task_prompt_still_carries_the_runner_contract():
    """Phase A's guarantee survives the extraction into task_prompt.py."""
    from pathly_orchestrator.fsm_compose import RUNNER_CONTRACT_BLOCK

    assert RUNNER_CONTRACT_BLOCK in _task_prompt()


def test_the_scheduler_no_longer_builds_the_prompt_itself():
    """One assembly, in one module — not a copy in the scheduler's worker."""
    import inspect

    from pathly_orchestrator.supervisor import scheduler

    src = inspect.getsource(scheduler)
    assert "build_task_prompt(" in src
    assert "compose_skill(" not in src, "prompt assembly should have left the scheduler"


# ── The retirement itself ────────────────────────────────────────────────────


def test_the_loop_executor_names_the_goal_loop_flow():
    from pathly_orchestrator.supervisor.goal_executor import _LOOP_FLOW, _TEAM_FLOW

    assert _LOOP_FLOW == "goal-loop"
    assert _LOOP_FLOW != _TEAM_FLOW, "loop must not collapse into the reviewed pipeline"


def test_the_goal_loop_flow_validates_and_declares_its_fan_out():
    from pathly_orchestrator.fsm.state import validate_flow_dict

    flow = yaml.safe_load(_FLOW.read_text(encoding="utf-8"))
    errors, _ = validate_flow_dict(flow)
    assert errors == [], errors
    assert flow["parallel_states"]["DRAINING"]["isolation"] == "lane"


def test_the_flow_name_matches_what_the_read_model_calls_a_loop_parent():
    """The name is load-bearing, not cosmetic.

    `run_history_read._classify_kind` returns 'loop' for a bare-uuid run whose adapter is
    the literal 'goal-loop' — and `start_run` writes `state.flow` into that adapter column.
    So naming the flow anything else would re-bucket every loop run as a flow (or, if added
    to FLOW_NAMES, as a flow explicitly), and its per-task `sched-*` rows would stop folding
    into one run in GET /runs.
    """
    import uuid

    from pathly_orchestrator.db.queries.run_history_read import (
        FLOW_NAMES,
        _classify_kind,
        _is_parent,
    )
    from pathly_orchestrator.supervisor.goal_executor import _LOOP_FLOW

    parent = str(uuid.uuid4())
    assert _LOOP_FLOW not in FLOW_NAMES, "a loop parent is not a flow parent"
    assert _classify_kind(parent, _LOOP_FLOW) == "loop"
    assert _is_parent(parent, _LOOP_FLOW) is True


def test_a_goal_loop_run_nests_its_storage_under_goals():
    """`_flow_kind` must map the new flow to the goals home, not to a 'goal-loop' dir.

    Any flow it does not recognise gets its OWN name as the storage kind — self-describing
    for a user-created flow, wrong for this one, which is a goal run.
    """
    from pathly_orchestrator.supervisor.goal_executor import _flow_kind, _LOOP_FLOW

    assert _flow_kind(_LOOP_FLOW) == "goals"


def test_goal_executor_no_longer_imports_a_drain_at_all():
    """Nothing left of the second engine — not the loop, not the tracker, not the isolation.

    Parsed, not grepped: this module's own docstrings NAME every one of these while explaining
    that they are gone, so a text search would report the explanation as the offence (it did,
    while this test was being written — the same trap test_drain_shared.py documents).
    """
    import ast
    import inspect

    from pathly_orchestrator.supervisor import goal_executor

    tree = ast.parse(inspect.getsource(goal_executor))
    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            referenced.update(a.asname or a.name for a in node.names)

    for gone in (
        "scheduler_loop",
        "drain_frontier",
        "AuditedLaneIsolation",
        "init_cost_tracker",
        "verify_clean_drain",
    ):
        assert gone not in referenced, f"{gone} should have left the goal executor"


# ── Stopping an FSM-driven goal run ──────────────────────────────────────────


def test_a_goal_run_is_found_by_its_goal_id_not_by_the_board_scope():
    """Phase E makes `loop` an FSM run, so `/comms/goals/stop` must reach it.

    The route used to look the run up with `get_state(scope)`. A goal's FSM run is registered
    under its board-nested topic, so that lookup returned None and the route reported
    "not_running" — leaving the run going. This also fixes the same gap for `executor: team`.
    """
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.state import RunnerState

    topic = "features/stopme/goals/g-abc"
    state = RunnerState(
        topic=topic,
        flow="goal-loop",
        project_root="",
        model="m",
        timeout=600,
        goal_id="goal-abc",
    )
    state.status = "running"
    with registry._lock:
        registry._registry[topic] = state
    try:
        found_topic, found = registry.find_active_run_for_goal("goal-abc", "stopme")
        assert found is state
        assert (
            found_topic == topic
        ), "abort_run must be called with the REGISTERED topic"
    finally:
        with registry._lock:
            registry._registry.pop(topic, None)


def test_a_finished_goal_run_is_not_reported_as_stoppable():
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.state import RunnerState

    topic = "features/donefeat/goals/g-done"
    state = RunnerState(
        topic=topic,
        flow="goal-loop",
        project_root="",
        model="m",
        timeout=600,
        goal_id="goal-done",
    )
    state.status = "done"
    with registry._lock:
        registry._registry[topic] = state
    try:
        _, found = registry.find_active_run_for_goal("goal-done", "donefeat")
        assert found is None
    finally:
        with registry._lock:
            registry._registry.pop(topic, None)


def test_the_scope_keyed_lookup_still_works_for_a_run_with_no_goal():
    """The fallback keeps the pre-Phase-E behaviour for a plain, non-goal run."""
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.state import RunnerState

    state = RunnerState(
        topic="plainfeat", flow="team", project_root="", model="m", timeout=600
    )
    state.status = "running"
    with registry._lock:
        registry._registry["plainfeat"] = state
    try:
        topic, found = registry.find_active_run_for_goal("", "plainfeat")
        assert found is state and topic == "plainfeat"
    finally:
        with registry._lock:
            registry._registry.pop("plainfeat", None)


def test_the_comms_broadcaster_reaches_the_run_so_the_board_still_sees_per_task_events():
    """A fan-out state's task_claimed/task_done COMMS_UPDATEs must survive the retirement.

    `executor: loop` used to hand `/comms/goals/run`'s broadcaster straight to
    `scheduler_loop`; with the FSM owning the drain there is no such call, so the broadcaster
    now rides on the RunnerState. Without this thread the board would silently stop showing
    per-task progress inside a loop run — the very thing
    tests/fsm_flows/test_golden_path.py::test_goal_loop_posts_supervisor_progress exists for.
    """
    import types

    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    conn = get_db()
    goal_id = post_message(
        conn,
        board="feature",
        scope="bcast-thread",
        from_agent="planner",
        type="goal",
        text="Ship it",
    )
    conn.execute("UPDATE comms_messages SET executor='loop' WHERE id=?", (goal_id,))
    conn.commit()

    sent: list = []
    captured: dict = {}

    def fake_start(**kw):
        captured.update(kw)
        return types.SimpleNamespace(run_id="r1")

    start_goal_run(
        goal_id,
        project_root="/x",
        start_fn=fake_start,
        event_broadcast_fn=lambda scope, payload: sent.append((scope, payload)),
        block=True,
    )
    assert captured.get("event_broadcast_fn") is not None, (
        "the comms broadcaster must reach start_run, or a loop run's per-task board "
        "events are silently dropped"
    )


def test_the_fan_out_reads_the_broadcaster_off_the_run():
    """The other half of the thread: start_run stores it, the drain uses it."""
    import inspect

    from pathly_orchestrator.supervisor import fan_out
    from pathly_orchestrator.supervisor.api import start_run
    from pathly_orchestrator.supervisor.state import RunnerState

    assert "event_broadcast_fn" in inspect.signature(start_run).parameters
    assert "_comms_broadcast_fn" in RunnerState.__dataclass_fields__
    assert "_comms_broadcast_fn" in inspect.getsource(fan_out._drain)
