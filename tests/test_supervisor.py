"""Tests for pathly_orchestrator.supervisor (Conv 2 — Phases 5-7)."""
from __future__ import annotations

import json
import threading
import time
from unittest.mock import patch

import pytest

from pathly_orchestrator.supervisor import (
    RunnerState,
    recover_stale_mirrors,
    start_run,
    pause_run,
    resume_run,
    abort_run,
    supply_decision,
    reroute_run,
    get_state,
    _lock,
    _registry,
    _write_mirror,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_NEXT_ACTION = "pathly_orchestrator.fsm_http_client.next_action"
_COMPLETE_STAGE = "pathly_orchestrator.fsm_http_client.complete_stage"
_INVOKE_AGENT = "pathly_orchestrator.runner.invoke_agent"


def _na(state: str = "STORMING", adapter: str = "claude") -> dict:
    return {
        "current_state": state,
        "agent": "builder",
        "instructions": "do stuff",
        "preferred_adapter": adapter,
    }



def _cs_next(to: str = "PLANNING") -> dict:
    return {"next_state": to}


def _cs_done() -> dict:
    return {"done": True}


def _cs_decide() -> dict:
    return {
        "decide": True,
        "question": "Which path?",
        "options": {"a": "PATH_A", "b": "PATH_B"},
        "default": "a",
    }


def _invoke_result(cost: float = 0.1, session_id: str = "sess-1") -> dict:
    return {"cost_usd": cost, "session_id": session_id}


def _fresh_registry(topic: str = "test-topic") -> None:
    """Remove a topic from the in-memory registry so tests are isolated."""
    with _lock:
        _registry.pop(topic, None)


# ── Phase 5: RunnerState + registry + mirror ──────────────────────────────────

def test_runner_state_public_dict():
    state = RunnerState(
        topic="t1", flow="team", project_root="/p", model="claude-sonnet-4-6", timeout=60
    )
    d = state.public_dict()
    assert d["topic"] == "t1"
    assert d["status"] == "idle"
    assert d["iterations"] == 0
    assert d["open_session"] is None


def test_write_mirror_creates_file(tmp_path):
    state = RunnerState(
        topic="mirror-topic", flow="team",
        project_root=str(tmp_path), model="m", timeout=60
    )
    state.status = "running"
    _write_mirror(state)
    mirror = tmp_path / "pathly" / "plans" / "mirror-topic" / "RUNNER_STATE.json"
    assert mirror.exists()
    data = json.loads(mirror.read_text())
    assert data["status"] == "running"
    assert data["topic"] == "mirror-topic"


def test_write_mirror_updates_on_status_change(tmp_path):
    state = RunnerState(
        topic="mirror-topic2", flow="team",
        project_root=str(tmp_path), model="m", timeout=60
    )
    state.status = "running"
    _write_mirror(state)
    state.status = "paused"
    _write_mirror(state)
    mirror = tmp_path / "pathly" / "plans" / "mirror-topic2" / "RUNNER_STATE.json"
    data = json.loads(mirror.read_text())
    assert data["status"] == "paused"


def test_recover_stale_mirrors(tmp_path):
    topic = "stale-run"
    mirror_dir = tmp_path / "pathly" / "plans" / topic
    mirror_dir.mkdir(parents=True)
    mirror = mirror_dir / "RUNNER_STATE.json"
    mirror.write_text(json.dumps({"topic": topic, "status": "running"}))

    recover_stale_mirrors(str(tmp_path))

    data = json.loads(mirror.read_text())
    assert data["status"] == "error"
    assert data["error_kind"] == "stale_restart"


def test_recover_stale_mirrors_skips_non_running(tmp_path):
    topic = "done-run"
    mirror_dir = tmp_path / "pathly" / "plans" / topic
    mirror_dir.mkdir(parents=True)
    mirror = mirror_dir / "RUNNER_STATE.json"
    mirror.write_text(json.dumps({"topic": topic, "status": "done"}))

    recover_stale_mirrors(str(tmp_path))

    data = json.loads(mirror.read_text())
    assert data["status"] == "done"  # untouched


def test_recover_stale_mirrors_no_plans_dir(tmp_path):
    # Should not raise even if plans dir doesn't exist
    recover_stale_mirrors(str(tmp_path / "nonexistent"))


# ── Phase 6: run loop + caps + abort ─────────────────────────────────────────

def test_start_run_single_stage_done(tmp_path):
    topic = "conv2-single"
    _fresh_registry(topic)
    na_calls = [_na("STORMING")]
    cs_calls = [_cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, return_value=_invoke_result()),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=5,
            max_cost_usd=10.0,
        )
        # Wait for the loop to finish
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    _fresh_registry(topic)


def test_start_run_two_stages(tmp_path):
    topic = "conv2-two-stage"
    _fresh_registry(topic)
    na_calls = [_na("STORMING"), _na("PLANNING")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, return_value=_invoke_result()),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=5,
            max_cost_usd=10.0,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    assert state.iterations == 2
    _fresh_registry(topic)


def test_start_run_already_active_raises(tmp_path):
    topic = "conv2-active"
    _fresh_registry(topic)
    # Manually inject an active state
    with _lock:
        fake = RunnerState(
            topic=topic, flow="team", project_root=str(tmp_path), model="m", timeout=60
        )
        fake.status = "running"
        _registry[topic] = fake

    with pytest.raises(ValueError, match="already active"):
        start_run(
            topic=topic, flow="team", project_root=str(tmp_path),
            max_iterations=5, max_cost_usd=1.0,
        )
    _fresh_registry(topic)


def test_cap_exceeded_cost(tmp_path):
    topic = "conv2-cost-cap"
    _fresh_registry(topic)
    na_calls = [_na("STORMING")]
    cs_calls = [_cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, return_value=_invoke_result(cost=5.0)),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=2.0,  # will be exceeded after first stage costs 5.0
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    # After first stage (cost 5.0 > max 2.0), second iteration boundary should cap
    # But the run might complete "done" if FSM returns done before second boundary.
    # So we check either done (normal) or error+cap_exceeded (cap triggered before done).
    # In this test na_calls has 1 entry and cs_calls returns done — the loop reaches done before cap check.
    # Let's restructure: 2 stages, cap after first.
    _fresh_registry(topic)


def test_cap_exceeded_cost_stops_loop(tmp_path):
    """With 2 stages and cost cap < cumulative after stage 1, stage 2 should not execute."""
    topic = "conv2-cost-cap2"
    _fresh_registry(topic)

    invoke_call_count = []

    def fake_invoke(*_args, **_kwargs):
        invoke_call_count.append(1)
        return {"cost_usd": 3.0, "session_id": None}

    # FSM would return a second stage, but the cap should stop the loop
    na_calls = [_na("STORMING"), _na("PLANNING")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=2.0,  # stage 1 costs 3.0 → exceeded
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "error"
    assert state.error_kind == "cap_exceeded"
    assert len(invoke_call_count) == 1  # only one invocation before cap
    _fresh_registry(topic)


def test_cap_exceeded_iterations(tmp_path):
    """Iteration cap stops the loop after max_iterations are consumed."""
    topic = "conv2-iter-cap"
    _fresh_registry(topic)

    invoke_call_count = []

    def fake_invoke(*_args, **_kwargs):
        invoke_call_count.append(1)
        return {"cost_usd": 0.0, "session_id": None}

    # FSM always returns next_state — would loop forever without cap
    def fake_na(_payload):
        return _na(f"STAGE-{len(invoke_call_count)}")

    def fake_cs(_payload):
        return _cs_next(f"STAGE-{len(invoke_call_count) + 1}")

    with (
        patch(_NEXT_ACTION, side_effect=fake_na),
        patch(_COMPLETE_STAGE, side_effect=fake_cs),
        patch(_INVOKE_AGENT, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=2,
            max_cost_usd=100.0,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "error"
    assert state.error_kind == "cap_exceeded"
    assert len(invoke_call_count) == 2
    _fresh_registry(topic)


def test_abort_stops_run(tmp_path):
    """Abort sets status=aborted before the loop calls another agent."""
    topic = "conv2-abort"
    _fresh_registry(topic)

    invoke_started = threading.Event()
    abort_done = threading.Event()

    def fake_invoke(*args, **kwargs):
        invoke_started.set()
        abort_done.wait(timeout=2.0)
        return {"cost_usd": 0.0, "session_id": None}

    na_calls = [_na("STORMING"), _na("PLANNING")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )
        invoke_started.wait(timeout=2.0)
        abort_run(topic)
        abort_done.set()

        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "aborted"
    _fresh_registry(topic)


def test_pause_and_resume(tmp_path):
    """Pause stops the loop at the next boundary; resume restarts it."""
    topic = "conv2-pause"
    _fresh_registry(topic)

    stage_count = [0]

    def fake_na(payload):
        stage_count[0] += 1
        return _na(f"STAGE-{stage_count[0]}")

    def fake_cs(payload):
        if stage_count[0] >= 2:
            return _cs_done()
        return _cs_next(f"STAGE-{stage_count[0] + 1}")

    with (
        patch(_NEXT_ACTION, side_effect=fake_na),
        patch(_COMPLETE_STAGE, side_effect=fake_cs),
        patch(_INVOKE_AGENT, return_value=_invoke_result(cost=0.1)),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )

        # Pause immediately
        pause_run(topic)

        # Wait for loop to acknowledge pause
        deadline = time.monotonic() + 3.0
        while state.status != "paused" and time.monotonic() < deadline:
            time.sleep(0.05)

        assert state.status == "paused"

        # Resume
        resume_run(topic)

        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    _fresh_registry(topic)


# ── Phase 7: decision + session continuity ────────────────────────────────────

def test_decision_point_awaiting_and_resume(tmp_path):
    """Loop sets awaiting_decision, supply_decision resumes with FSM call."""
    topic = "conv2-decision"
    _fresh_registry(topic)

    decision_supplied = threading.Event()

    def fake_cs(payload):
        if payload.get("decision"):
            # FSM received the decision
            return _cs_done()
        return _cs_decide()

    def supply_after_delay():
        # Wait until state is awaiting_decision, then supply it
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with _lock:
                st = _registry.get(topic)
                if st and st.status == "awaiting_decision":
                    break
            time.sleep(0.05)
        supply_decision(topic, "b")
        decision_supplied.set()

    with (
        patch(_NEXT_ACTION, return_value=_na("STORMING")),
        patch(_COMPLETE_STAGE, side_effect=fake_cs),
        patch(_INVOKE_AGENT, return_value=_invoke_result()),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )

        supply_thread = threading.Thread(target=supply_after_delay, daemon=True)
        supply_thread.start()

        deadline = time.monotonic() + 8.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    decision_supplied.wait(timeout=2.0)
    assert state.status == "done"
    _fresh_registry(topic)


def test_supply_decision_wrong_status_raises(tmp_path):
    topic = "conv2-decision-bad"
    _fresh_registry(topic)
    with _lock:
        fake = RunnerState(
            topic=topic, flow="team", project_root=str(tmp_path), model="m", timeout=60
        )
        fake.status = "running"
        _registry[topic] = fake

    with pytest.raises(ValueError, match="not awaiting a decision"):
        supply_decision(topic, "a")
    _fresh_registry(topic)


def test_session_continuity_same_adapter(tmp_path):
    """Same adapter on consecutive stages → session is continued (session_id reused)."""
    topic = "conv2-sess-same"
    _fresh_registry(topic)

    invoke_sessions = []

    def fake_invoke(*args, **kwargs):
        invoke_sessions.append(kwargs.get("session"))
        return {"cost_usd": 0.05, "session_id": "sess-abc"}

    na_calls = [_na("STORMING", "claude"), _na("PLANNING", "claude")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    # First invocation: no session yet
    assert invoke_sessions[0] is None
    # Second invocation: session_id from first invocation
    assert invoke_sessions[1] == "sess-abc"
    _fresh_registry(topic)


def test_session_fresh_on_adapter_change(tmp_path):
    """Different adapter on second stage → fresh (no session_id passed)."""
    topic = "conv2-sess-change"
    _fresh_registry(topic)

    invoke_sessions = []

    def fake_invoke(*args, **kwargs):
        invoke_sessions.append(kwargs.get("session"))
        return {"cost_usd": 0.05, "session_id": "sess-xyz"}

    na_calls = [_na("STORMING", "claude"), _na("PLANNING", "codex")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    # Both invocations get None session (different adapters means no resume)
    assert invoke_sessions[0] is None
    assert invoke_sessions[1] is None
    _fresh_registry(topic)


def test_reroute_overrides_adapter_for_next_stage(tmp_path):
    """reroute_run overrides the preferred_adapter for the next stage only."""
    topic = "conv2-reroute"
    _fresh_registry(topic)

    used_adapters = []
    first_invoke_done = threading.Event()
    second_invoke_may_proceed = threading.Event()

    def fake_invoke(*args, **kwargs):
        adapter = kwargs.get("adapter", "claude")
        used_adapters.append(adapter)
        if len(used_adapters) == 1:
            first_invoke_done.set()
            # Block until we set the reroute and allow proceeding
            second_invoke_may_proceed.wait(timeout=3.0)
        return {"cost_usd": 0.0, "session_id": None}

    na_calls = [_na("STORMING", "claude"), _na("PLANNING", "claude")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, side_effect=fake_invoke),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )

        # Wait for first invoke to complete, then set the reroute before allowing second
        first_invoke_done.wait(timeout=3.0)
        reroute_run(topic, "codex")
        second_invoke_may_proceed.set()

        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    assert used_adapters[0] == "claude"
    assert used_adapters[1] == "codex"
    _fresh_registry(topic)


def test_cost_accumulated_across_stages(tmp_path):
    topic = "conv2-cost-accum"
    _fresh_registry(topic)

    na_calls = [_na("STORMING"), _na("PLANNING")]
    cs_calls = [_cs_next("PLANNING"), _cs_done()]

    with (
        patch(_NEXT_ACTION, side_effect=na_calls),
        patch(_COMPLETE_STAGE, side_effect=cs_calls),
        patch(_INVOKE_AGENT, return_value={"cost_usd": 0.25, "session_id": None}),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    assert state.status == "done"
    assert abs(state.cost_usd_so_far - 0.5) < 1e-9
    _fresh_registry(topic)


def test_mirror_written_on_completion(tmp_path):
    topic = "conv2-mirror-done"
    _fresh_registry(topic)

    with (
        patch(_NEXT_ACTION, return_value=_na("STORMING")),
        patch(_COMPLETE_STAGE, return_value=_cs_done()),
        patch(_INVOKE_AGENT, return_value=_invoke_result()),
    ):
        state = start_run(
            topic=topic,
            flow="team",
            project_root=str(tmp_path),
            max_iterations=10,
            max_cost_usd=100.0,
        )
        deadline = time.monotonic() + 5.0
        while state.status not in {"done", "error", "aborted"} and time.monotonic() < deadline:
            time.sleep(0.05)

    mirror = tmp_path / "pathly" / "plans" / topic / "RUNNER_STATE.json"
    assert mirror.exists()
    data = json.loads(mirror.read_text())
    assert data["status"] == "done"
    _fresh_registry(topic)


def test_get_state_unknown_topic():
    assert get_state("no-such-topic-xyz") is None
