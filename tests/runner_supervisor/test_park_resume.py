"""Tests for the human-checkpoint "parked" status and its resume path.

Before this fix, a headless human checkpoint (`complete_stage` returning
`blocked, target_agent="human"`) called `_fail("human_checkpoint", ...)`: the run died
with `status="error"` and there was no way back in — Pathly's own "board is a supervisory
surface a human answers" story broke exactly where a human was actually needed.

These drive the REAL FSM (`fsm_ops.complete_stage`) the same way
`test_runner_fsm_integration.py::test_supervisor_loop_advances_through_real_fsm_to_done`
does — only `next_action` (display) and the PTY spawn are stubbed — so the park/resume
contract is proven against the real `route_feedback` / `evaluate_transition_rules`
machinery, not a mock that could quietly diverge from it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import pathly_orchestrator.fsm_ops as fsm_ops
from pathly_orchestrator.fsm_ops import complete_stage

# ALPHA has an open feedback file routed to "human" from the start, so the very first
# complete_stage call blocks on it (route_feedback runs before any transition rule) —
# no need to first advance through a real agent stage to reach the checkpoint.
HUMAN_FLOW = {
    "version": 1,
    "flow": "test-human",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["ALPHA", "DONE"],
    "transitions": {"ALPHA": ["DONE"], "DONE": []},
    "agent_map": {"ALPHA": "team/a"},
    "feedback_routing": {"HUMAN_QUESTIONS": "human"},
    "transition_rules": {
        "ALPHA": {
            "on_content": [{"file": "GO.md", "contains": "## go", "next": "DONE"}],
            "default": "ALPHA",
        },
    },
    "transition_actions": {},
}

_TERMINAL = {"done", "error", "aborted", "parked"}


def _storage(tmp_path: Path, topic: str) -> Path:
    p = tmp_path / "pathly" / "plans" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


def _seed_parked(tmp_path: Path, topic: str) -> Path:
    storage = _storage(tmp_path, topic)
    (storage / "STATE.json").write_text(
        json.dumps({"current": "ALPHA"}), encoding="utf-8"
    )
    (storage / "feedback").mkdir(exist_ok=True)
    (storage / "feedback" / "HUMAN_QUESTIONS.md").write_text(
        "Which database should this feature use?", encoding="utf-8"
    )
    return storage


def _resolve_checkpoint(storage: Path) -> None:
    """What a human does: resolve the checkpoint, then supply what the flow needs to advance."""
    (storage / "feedback" / "HUMAN_QUESTIONS.md").unlink()
    (storage / "GO.md").write_text(
        "## go\nPostgres, per the human's answer.", encoding="utf-8"
    )


def _wait_terminal(state, deadline_s: float = 8.0) -> None:
    deadline = time.monotonic() + deadline_s
    while state.status not in _TERMINAL and time.monotonic() < deadline:
        time.sleep(0.05)


@pytest.fixture(autouse=True)
def _patch_flow_and_prompt(monkeypatch):
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: HUMAN_FLOW)
    monkeypatch.setattr(
        fsm_ops, "build_prompt", lambda *args, **kwargs: f"instructions for {args[1]}"
    )


def _drive(topic: str, tmp_path: Path, *, max_iterations: int = 5):
    """start_run with next_action/complete_stage/spawn wired to the real FSM."""
    import pathly_orchestrator.fsm_http_client as fhc
    from pathly_orchestrator.supervisor import start_run

    na = {
        "current_state": "ALPHA",
        "agent": "team/a",
        "instructions": "do",
        "preferred_adapter": "claude",
    }
    ctx = (
        patch.object(fhc, "next_action", side_effect=lambda *_: dict(na)),
        patch.object(fhc, "complete_stage", side_effect=complete_stage),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            return_value={"cost_usd": 0.0, "session_id": "sess-1"},
        ),
    )
    with ctx[0], ctx[1], ctx[2]:
        state = start_run(
            topic=topic,
            flow="test-human",
            project_root=str(tmp_path),
            max_iterations=max_iterations,
            max_cost_usd=10.0,
        )
        _wait_terminal(state)
    return state


# ── The checkpoint parks instead of failing ─────────────────────────────────────


def test_human_checkpoint_parks_not_errors(tmp_path):
    from pathly_orchestrator.supervisor import _lock, _registry

    topic = "park-test-1"
    _seed_parked(tmp_path, topic)
    with _lock:
        _registry.pop(topic, None)

    state = _drive(topic, tmp_path)

    assert state.status == "parked", f"expected parked, got {state.status!r}"
    assert state.error_kind == "human_checkpoint"
    with _lock:
        _registry.pop(topic, None)


def test_human_checkpoint_posts_an_answerable_escalation(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_active_escalations
    from pathly_orchestrator.supervisor import _lock, _registry

    topic = "park-test-2"
    _seed_parked(tmp_path, topic)
    with _lock:
        _registry.pop(topic, None)

    _drive(topic, tmp_path)

    escalations = get_active_escalations(get_db(), boards=["feature"], scopes=[topic])
    assert any("HUMAN_QUESTIONS.md" in e["text"] for e in escalations)
    assert any("resume-parked" in e["text"] for e in escalations)
    with _lock:
        _registry.pop(topic, None)


def test_a_non_human_feedback_target_still_fails_normally(tmp_path):
    """Parking is specific to target_agent=='human' — a builder-routed feedback file
    must still behave exactly as before (no accidental universal parking)."""
    from pathly_orchestrator.supervisor import _lock, _registry

    topic = "park-test-3"
    flow = dict(HUMAN_FLOW)
    flow["feedback_routing"] = {"HUMAN_QUESTIONS": "builder"}  # not "human"
    import pathly_orchestrator.fsm_ops as _fo

    with patch.object(_fo, "_load_flow", lambda *_: flow):
        storage = _seed_parked(tmp_path, topic)
        with _lock:
            _registry.pop(topic, None)
        # build_prompt_for_agent is REAL here (not stubbed) since target != human, so
        # let the run take whatever path it takes and just check it never parks.
        state = _drive(topic, tmp_path)

    assert state.status != "parked"
    with _lock:
        _registry.pop(topic, None)


# ── Resuming a parked run ────────────────────────────────────────────────────────


def test_resume_parked_run_reparks_while_unresolved(tmp_path):
    """Resuming re-enters the SAME FSM state; if nothing changed it hits the same wall."""
    from pathly_orchestrator.supervisor import _lock, _registry, resume_parked_run

    topic = "park-test-4"
    _seed_parked(tmp_path, topic)
    with _lock:
        _registry.pop(topic, None)

    first = _drive(topic, tmp_path)
    assert first.status == "parked"

    import pathly_orchestrator.fsm_http_client as fhc

    na = {
        "current_state": "ALPHA",
        "agent": "team/a",
        "instructions": "do",
        "preferred_adapter": "claude",
    }
    with (
        patch.object(fhc, "next_action", side_effect=lambda *_: dict(na)),
        patch.object(fhc, "complete_stage", side_effect=complete_stage),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            return_value={"cost_usd": 0.0, "session_id": "sess-2"},
        ),
    ):
        second = resume_parked_run(topic)
        _wait_terminal(second)

    assert (
        second.run_id != first.run_id
    ), "resume must start a NEW run, not revive the old"
    assert second.status == "parked"
    with _lock:
        _registry.pop(topic, None)


def test_resume_parked_run_advances_once_a_human_resolves_it(tmp_path):
    """The actual point: a human's edit to the feedback file, then resume, reaches DONE —
    with NO separate replay step, because /next_action re-reads the file's current state.
    """
    from pathly_orchestrator.supervisor import _lock, _registry, resume_parked_run

    topic = "park-test-5"
    storage = _seed_parked(tmp_path, topic)
    with _lock:
        _registry.pop(topic, None)

    parked = _drive(topic, tmp_path)
    assert parked.status == "parked"

    _resolve_checkpoint(storage)

    import pathly_orchestrator.fsm_http_client as fhc

    na = {
        "current_state": "ALPHA",
        "agent": "team/a",
        "instructions": "do",
        "preferred_adapter": "claude",
    }
    with (
        patch.object(fhc, "next_action", side_effect=lambda *_: dict(na)),
        patch.object(fhc, "complete_stage", side_effect=complete_stage),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            return_value={"cost_usd": 0.0, "session_id": "sess-3"},
        ),
    ):
        resumed = resume_parked_run(topic)
        _wait_terminal(resumed)

    assert resumed.status == "done", f"expected done, got {resumed.status!r}"
    with _lock:
        _registry.pop(topic, None)


# ── resume_parked_run validation (no FSM needed) ──────────────────────────────────


def test_resume_parked_run_rejects_unknown_topic():
    from pathly_orchestrator.supervisor import resume_parked_run

    with pytest.raises(KeyError):
        resume_parked_run("no-such-topic-abc123")


def test_resume_parked_run_rejects_a_non_parked_run(tmp_path):
    from pathly_orchestrator.supervisor import _lock, _registry, resume_parked_run
    from pathly_orchestrator.supervisor.state import RunnerState

    topic = "park-test-not-parked"
    with _lock:
        _registry[topic] = RunnerState(
            topic=topic,
            flow="test-human",
            project_root=str(tmp_path),
            model="claude-sonnet-4-6",
            timeout=600,
            status="running",
        )
    try:
        with pytest.raises(ValueError):
            resume_parked_run(topic)
    finally:
        with _lock:
            _registry.pop(topic, None)


# ── on_done sees "parked" as non-success (api.py's result-shaping) ────────────────


def test_on_done_receives_error_for_a_parked_run(tmp_path):
    """Every on_done consumer branches on res.get('error') to avoid reporting a
    non-clean stop as success (see goals.py's _on_done) — parked must set it too."""
    from pathly_orchestrator.supervisor import _lock, _registry

    topic = "park-test-6"
    _seed_parked(tmp_path, topic)
    with _lock:
        _registry.pop(topic, None)

    seen: list[dict] = []
    import pathly_orchestrator.fsm_http_client as fhc
    from pathly_orchestrator.supervisor import start_run

    na = {
        "current_state": "ALPHA",
        "agent": "team/a",
        "instructions": "do",
        "preferred_adapter": "claude",
    }
    with (
        patch.object(fhc, "next_action", side_effect=lambda *_: dict(na)),
        patch.object(fhc, "complete_stage", side_effect=complete_stage),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            return_value={"cost_usd": 0.0, "session_id": "sess-4"},
        ),
    ):
        state = start_run(
            topic=topic,
            flow="test-human",
            project_root=str(tmp_path),
            max_iterations=5,
            max_cost_usd=10.0,
            on_done=lambda run_id, res: seen.append(res),
        )
        _wait_terminal(state)
        deadline = time.monotonic() + 5.0
        while not seen and time.monotonic() < deadline:
            time.sleep(0.05)

    with _lock:
        _registry.pop(topic, None)

    assert seen, "on_done was never called"
    assert seen[0]["status"] == "parked"
    assert seen[0].get(
        "error"
    ), "a parked run must still carry `error` for on_done consumers"
