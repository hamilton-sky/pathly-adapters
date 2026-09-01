"""Tests for supervisor/compiled_flow.py — Phase 2 of the FSM/DAG convergence.

`run_compiled_flow` walks a flow's states directly (no fsm_state DB row, no
/next_action-/complete_stage HTTP round-trip) but reuses the SAME pure helpers
(`route_feedback`, `evaluate_transition_rules`, `run_gates`, `run_transition_actions`)
and prompt-building path (`fsm_compose.build_prompt`/`build_prompt_for_agent`) the real
FSM engine uses — so these tests exercise the REAL machinery, only the CLI spawn and
prompt composition are stubbed (same technique as test_park_resume.py).

Off by default: `is_compiled_flow`/`resolve_compiled_flows` gate everything on the
`flow.compiled_executors` app-setting, empty unless a test sets it.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest

import pathly_orchestrator.fsm_compose as fsm_compose
import pathly_orchestrator.fsm_ops as fsm_ops
from pathly_orchestrator.supervisor.compiled_flow import (
    is_compiled_flow,
    resolve_compiled_flows,
    run_compiled_flow,
)
from pathly_orchestrator.supervisor.state import RunnerState

_TERMINAL = {"done", "error", "aborted", "parked"}

SIMPLE_FLOW = {
    "version": 1,
    "flow": "test-compiled",
    "storage_path": "pathly/features/{topic}/",
    "states": ["ALPHA", "BETA", "DONE"],
    "transitions": {"ALPHA": ["BETA"], "BETA": ["DONE"], "DONE": []},
    "agent_map": {"ALPHA": "team/a", "BETA": "team/b"},
    "feedback_routing": {"TEST_FAILURES": "builder", "HUMAN_QUESTIONS": "human"},
    "transition_actions": {},
}


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _set_setting(key: str, value) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), key, "" if value is None else str(value))


def _make_state(
    topic: str, tmp_path: Path, flow: str = "test-compiled", **kw
) -> RunnerState:
    return RunnerState(
        topic=topic,
        flow=flow,
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=600,
        max_iterations=kw.pop("max_iterations", 10),
        max_cost_usd=kw.pop("max_cost_usd", 5.0),
        **kw,
    )


def _stub_prompts(monkeypatch) -> None:
    monkeypatch.setattr(
        fsm_compose, "build_prompt", lambda flow, state, storage, *a, **k: f"do {state}"
    )
    monkeypatch.setattr(
        fsm_compose,
        "build_prompt_for_agent",
        lambda agent, storage, **k: f"resolve as {agent}",
    )


def _run(state: RunnerState, spawn_fn: Callable, *, flow_config=None) -> list[str]:
    """Run run_compiled_flow synchronously with a stubbed spawn; returns the list of
    run_ids spawned, in order (via the same `pathly_orchestrator.supervisor._run_stage_via_terminal`
    patch point orchestrator._loop's own tests use)."""
    from contextlib import ExitStack

    calls: list[str] = []

    def _spawn(_state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        calls.append(run_id)
        return spawn_fn(instructions, run_id)

    with ExitStack() as stack:
        stack.enter_context(
            patch("pathly_orchestrator.supervisor._run_stage_via_terminal", _spawn)
        )
        if flow_config is not None:
            stack.enter_context(
                patch.object(fsm_ops, "_load_flow", lambda *_: flow_config)
            )
        run_compiled_flow(state, None)
    return calls


def _feature_dir(tmp_path: Path, topic: str) -> Path:
    p = tmp_path / "pathly" / "features" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── resolve_compiled_flows / is_compiled_flow ─────────────────────────────────────


def test_resolve_compiled_flows_unconfigured_is_empty():
    assert resolve_compiled_flows() == frozenset()


def test_resolve_compiled_flows_parses_comma_separated():
    _set_setting("flow.compiled_executors", "quick-fix, debug")
    assert resolve_compiled_flows() == frozenset({"quick-fix", "debug"})


def test_resolve_compiled_flows_fails_open_on_broken_db(monkeypatch):
    import pathly_orchestrator.db.connection as conn_mod

    monkeypatch.setattr(
        conn_mod, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    assert resolve_compiled_flows() == frozenset()


def test_is_compiled_flow_membership():
    _set_setting("flow.compiled_executors", "quick-fix")
    assert is_compiled_flow("quick-fix") is True
    assert is_compiled_flow("debug") is False
    assert is_compiled_flow("team") is False


# ── api.start_run dispatch seam ──────────────────────────────────────────────────


def test_start_run_dispatches_to_compiled_executor_when_opted_in(tmp_path):
    import pathly_orchestrator.supervisor.compiled_flow as cf_mod
    import pathly_orchestrator.supervisor.orchestrator as orch_mod
    from pathly_orchestrator.supervisor import _lock, _registry, start_run

    _set_setting("flow.compiled_executors", "test-compiled")
    calls = {"compiled": 0, "fsm": 0}

    def _fake_compiled(state, broadcast_fn):
        calls["compiled"] += 1

    def _fake_fsm(state, broadcast_fn):
        calls["fsm"] += 1

    topic = "dispatch-compiled"
    with _lock:
        _registry.pop(topic, None)
    with (
        patch.object(cf_mod, "run_compiled_flow", _fake_compiled),
        patch.object(orch_mod, "_loop", _fake_fsm),
    ):
        state = start_run(topic=topic, flow="test-compiled", project_root=str(tmp_path))
        deadline = time.monotonic() + 5.0
        while (
            calls["compiled"] == 0 and calls["fsm"] == 0 and time.monotonic() < deadline
        ):
            time.sleep(0.02)

    with _lock:
        _registry.pop(topic, None)
    assert calls == {"compiled": 1, "fsm": 0}


def test_start_run_uses_fsm_loop_by_default(tmp_path):
    import pathly_orchestrator.supervisor.compiled_flow as cf_mod
    import pathly_orchestrator.supervisor.orchestrator as orch_mod
    from pathly_orchestrator.supervisor import _lock, _registry, start_run

    # No app-setting configured -> resolve_compiled_flows() is empty for this flow.
    calls = {"compiled": 0, "fsm": 0}

    def _fake_compiled(state, broadcast_fn):
        calls["compiled"] += 1

    def _fake_fsm(state, broadcast_fn):
        calls["fsm"] += 1

    topic = "dispatch-default"
    with _lock:
        _registry.pop(topic, None)
    with (
        patch.object(cf_mod, "run_compiled_flow", _fake_compiled),
        patch.object(orch_mod, "_loop", _fake_fsm),
    ):
        state = start_run(topic=topic, flow="test-compiled", project_root=str(tmp_path))
        deadline = time.monotonic() + 5.0
        while (
            calls["compiled"] == 0 and calls["fsm"] == 0 and time.monotonic() < deadline
        ):
            time.sleep(0.02)

    with _lock:
        _registry.pop(topic, None)
    assert calls == {"compiled": 0, "fsm": 1}


# ── run_compiled_flow — golden path ───────────────────────────────────────────────


def test_compiled_flow_drains_a_linear_flow_to_done(tmp_path, monkeypatch):
    from pathly_orchestrator import eventlog

    _stub_prompts(monkeypatch)
    topic = "compiled-golden"
    _feature_dir(tmp_path, topic)
    state = _make_state(topic, tmp_path)

    calls = _run(state, lambda instr, rid: {"cost_usd": 0.01}, flow_config=SIMPLE_FLOW)

    assert len(calls) == 2, calls  # ALPHA, BETA — DONE is never spawned
    assert state.status == "done"
    assert state.iterations == 2
    assert state.cost_usd_so_far == pytest.approx(0.02)
    storage_path = tmp_path / "pathly" / "features" / topic
    assert eventlog.read_state(str(storage_path)) is None, "no fsm_state persisted"


# ── run_compiled_flow — feedback settle loop ──────────────────────────────────────


def test_compiled_flow_resolves_a_feedback_file_then_advances(tmp_path, monkeypatch):
    _stub_prompts(monkeypatch)
    topic = "compiled-feedback"
    storage = _feature_dir(tmp_path, topic)
    calls: list[str] = []

    def _spawn(instr, rid):
        calls.append(rid)
        if len(calls) == 1:
            # ALPHA's primary spawn "fails" — write the feedback file the flow routes.
            (storage / "feedback").mkdir(exist_ok=True)
            (storage / "feedback" / "TEST_FAILURES.md").write_text("boom")
        elif len(calls) == 2:
            # The feedback-target ("builder") resolves it.
            (storage / "feedback" / "TEST_FAILURES.md").unlink()
        return {"cost_usd": 0.0}

    state = _make_state(topic, tmp_path)
    seen = _run(state, _spawn, flow_config=SIMPLE_FLOW)

    assert len(seen) == 3, seen  # ALPHA primary, 1 feedback round, then BETA primary
    assert state.status == "done"


def test_compiled_flow_fails_after_exhausting_feedback_rounds(tmp_path, monkeypatch):
    from pathly_orchestrator.supervisor.state import MAX_FEEDBACK_ROUNDS

    _stub_prompts(monkeypatch)
    topic = "compiled-feedback-exhausted"
    storage = _feature_dir(tmp_path, topic)
    (storage / "feedback").mkdir(exist_ok=True)
    (storage / "feedback" / "TEST_FAILURES.md").write_text("always broken")

    state = _make_state(topic, tmp_path)
    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0}, flow_config=SIMPLE_FLOW)

    # 1 primary ALPHA spawn + MAX_FEEDBACK_ROUNDS feedback-target spawns.
    assert len(seen) == 1 + MAX_FEEDBACK_ROUNDS, seen
    assert state.status == "error"
    assert state.error_kind == "feedback_exhausted"


def test_compiled_flow_fails_on_human_checkpoint_and_posts_escalation(
    tmp_path, monkeypatch
):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_active_escalations

    _stub_prompts(monkeypatch)
    topic = "compiled-human"
    storage = _feature_dir(tmp_path, topic)
    (storage / "feedback").mkdir(exist_ok=True)
    (storage / "feedback" / "HUMAN_QUESTIONS.md").write_text("which database?")

    state = _make_state(topic, tmp_path)
    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0}, flow_config=SIMPLE_FLOW)

    assert len(seen) == 1  # only the primary ALPHA spawn — no fake human to spawn
    assert state.status == "error"
    assert state.error_kind == "human_checkpoint"
    escalations = get_active_escalations(get_db(), boards=["feature"], scopes=[topic])
    assert any("HUMAN_QUESTIONS.md" in e["text"] for e in escalations)
    assert any("does not support pause/resume" in e["text"] for e in escalations)


# ── run_compiled_flow — safety guards ─────────────────────────────────────────────


def test_compiled_flow_refuses_a_topic_with_existing_fsm_state(tmp_path, monkeypatch):
    from pathly_orchestrator import eventlog

    _stub_prompts(monkeypatch)
    topic = "compiled-existing-state"
    storage = _feature_dir(tmp_path, topic)
    eventlog.write_state(str(storage), {"current": "ALPHA"}, flow=SIMPLE_FLOW)

    state = _make_state(topic, tmp_path)
    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0}, flow_config=SIMPLE_FLOW)

    assert seen == [], "must not spawn anything"
    assert state.status == "error"
    assert state.error_kind == "existing_fsm_state"


def test_compiled_flow_fails_loudly_on_a_decide_rule(tmp_path, monkeypatch):
    _stub_prompts(monkeypatch)
    flow = dict(SIMPLE_FLOW)
    flow["transition_rules"] = {
        "ALPHA": {
            "decide": {"question": "which way?", "options": {}, "default": ""},
        }
    }
    topic = "compiled-decide"
    _feature_dir(tmp_path, topic)

    state = _make_state(topic, tmp_path)
    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0}, flow_config=flow)

    assert len(seen) == 1  # ALPHA's primary spawn happens; the decide check is after
    assert state.status == "error"
    assert state.error_kind == "decide_unsupported"


def test_compiled_flow_respects_abort_before_first_spawn(tmp_path, monkeypatch):
    _stub_prompts(monkeypatch)
    topic = "compiled-abort"
    _feature_dir(tmp_path, topic)
    state = _make_state(topic, tmp_path)
    state._abort_flag = True

    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0}, flow_config=SIMPLE_FLOW)

    assert seen == []
    assert state.status == "aborted"


def test_compiled_flow_respects_cap_exceeded(tmp_path, monkeypatch):
    _stub_prompts(monkeypatch)
    topic = "compiled-cap"
    _feature_dir(tmp_path, topic)
    state = _make_state(topic, tmp_path, max_iterations=0)

    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0}, flow_config=SIMPLE_FLOW)

    assert seen == []
    assert state.status == "error"
    assert state.error_kind == "cap_exceeded"


# ── run_compiled_flow — against the REAL packaged quick-fix.flow.yaml ─────────────


def test_compiled_flow_against_the_real_quick_fix_flow(tmp_path, monkeypatch):
    """Prompt composition is still stubbed (composing real skill fragments is heavy and
    not the point here) but the FLOW itself is the real packaged quick-fix.flow.yaml —
    no monkeypatched _load_flow — so this proves the executor's transition/gate/feedback
    wiring against the actual shape it was verified against."""
    _stub_prompts(monkeypatch)
    topic = "compiled-real-quickfix"
    _feature_dir(tmp_path, topic)
    state = _make_state(topic, tmp_path, flow="quick-fix")

    seen = _run(state, lambda instr, rid: {"cost_usd": 0.0})  # no flow_config override

    assert len(seen) == 3, seen  # SCOPING, FIXING, VERIFYING — DONE is never spawned
    assert state.status == "done"
    assert state.iterations == 3


# ── escalation ladder off in-memory counts (no STATE.json) ────────────────────────


def test_escalation_reason_names_which_path_reached_the_human():
    """The two ways a run reaches a human read very differently to whoever finds the
    board post: a question to answer vs. N agents that could not fix it."""
    from pathly_orchestrator.supervisor.compiled_escalation import escalation_reason

    assert escalation_reason(0, "HUMAN_QUESTIONS.md") == (
        "the flow routes HUMAN_QUESTIONS.md to a human"
    )
    assert (
        escalation_reason(1, "X.md") == "1 round of automated fixes did not resolve it"
    )
    assert (
        escalation_reason(3, "X.md") == "3 rounds of automated fixes did not resolve it"
    )


def test_retry_counts_are_passed_to_route_feedback(tmp_path, monkeypatch):
    """The executor supplies its OWN per-file counts (it writes no STATE.json), so
    escalation_routing tiers actually climb. Captures what route_feedback is handed on
    each round: 0, then 1 — first sighting is attempt 1, exactly as on the FSM path."""
    import pathly_orchestrator.supervisor.compiled_flow as cf

    seen: list[dict] = []

    def fake_route(flow, storage_path, *, retry_counts=None):
        seen.append(dict(retry_counts or {}))
        if len(seen) <= 2:
            return {
                "file": "REVIEW_FAILURES.md",
                "target_agent": "builder",
                "retry_count": (retry_counts or {}).get("REVIEW_FAILURES.md", 0),
            }
        return None

    state = _make_state("esc-topic", tmp_path)
    _set_setting("flow.compiled_executors", "test-compiled")
    with (
        patch.object(fsm_ops, "_load_flow", return_value=SIMPLE_FLOW),
        patch("pathly_orchestrator.fsm.route_feedback", fake_route),
        patch.object(fsm_compose, "build_prompt", return_value="p"),
        patch.object(fsm_compose, "build_prompt_for_agent", return_value="fb"),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            return_value={"outcome": "success", "cost_usd": 0.0},
        ),
    ):
        run_compiled_flow(state, None)

    assert seen[:3] == [{}, {"REVIEW_FAILURES.md": 1}, {"REVIEW_FAILURES.md": 2}]
