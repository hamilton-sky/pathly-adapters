"""Integration tests: the REAL FSM driven through the REAL driver loops.

These exist because the historical `next_state` contract bug shipped GREEN: every
driver test (test_supervisor.py, test_runner.py) MOCKS complete_stage to return a
fictional ``{"next_state": ...}`` envelope, while the real FSM emitted only
``current_state``. The real FSM was therefore never driven through either real loop,
so both the supervisor and the runner silently treated a clean advance as an
"Unexpected result" and stopped after exactly one transition.

The tests below use the REAL ``complete_stage`` (only the agent spawn / next_action
display are stubbed, because those launch CLIs) so the FSM↔driver advance contract is
actually exercised across multiple transitions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pathly_orchestrator.fsm_ops as fsm_ops
from pathly_orchestrator.fsm_ops import complete_stage

# A minimal, gate-free linear flow we fully control: ALPHA --A.md--> BETA --B.md--> DONE.
# Using a controlled flow (rather than the real team flow) keeps the test decoupled from
# the specific gate artifacts each real stage requires — it isolates the advance contract.
LINEAR_FLOW = {
    "version": 1,
    "flow": "test",
    "storage_path": "pathly/plans/{topic}/",
    "states": ["ALPHA", "BETA", "DONE"],
    "transitions": {"ALPHA": ["BETA"], "BETA": ["DONE"], "DONE": []},
    "agent_map": {"ALPHA": "team/a", "BETA": "team/b"},
    "feedback_routing": {},
    "transition_rules": {
        "ALPHA": {
            "on_content": [{"file": "A.md", "contains": "## go", "next": "BETA"}],
            "default": "ALPHA",
        },
        "BETA": {
            "on_content": [{"file": "B.md", "contains": "## go", "next": "DONE"}],
            "default": "BETA",
        },
    },
    "transition_actions": {},
}


def _storage_path(tmp_path: Path, topic: str = "test-topic") -> Path:
    p = tmp_path / "pathly" / "plans" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


def _patch_load_flow(monkeypatch) -> None:
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: LINEAR_FLOW)


def _patch_build_prompt(monkeypatch) -> None:
    monkeypatch.setattr(
        fsm_ops, "build_prompt", lambda *args, **kwargs: f"instructions for {args[1]}"
    )


def _seed(tmp_path) -> Path:
    storage = _storage_path(tmp_path)
    (storage / "STATE.json").write_text(
        json.dumps({"current": "ALPHA"}), encoding="utf-8"
    )
    (storage / "A.md").write_text("## go\nready", encoding="utf-8")
    (storage / "B.md").write_text("## go\nready", encoding="utf-8")
    return storage


# ── Contract: real complete_stage emits the advance signal the drivers gate on ──


def test_real_complete_stage_emits_next_state_across_transitions(tmp_path, monkeypatch):
    """The exact regression guard: drive the REAL FSM across TWO transitions and assert
    each successful advance carries a top-level ``next_state`` — the key both
    supervisor/orchestrator.py:75/525 and runner/cli.py:74/188 gate continuation on."""
    _patch_load_flow(monkeypatch)
    _patch_build_prompt(monkeypatch)
    _seed(tmp_path)
    payload = {"flow": "test", "topic": "test-topic", "project_root": str(tmp_path)}

    # First advance: ALPHA -> BETA
    r1 = complete_stage(payload)
    assert r1.get("next_state") == "BETA"
    assert r1.get("current_state") == "BETA"
    assert "done" not in r1
    # This is byte-for-byte the predicate both driver loops use to decide "advance vs
    # Unexpected". It MUST be truthy on a clean advance, or the pipeline stops after stage 1.
    assert bool(r1.get("done") or r1.get("next_state")) is True

    # Second advance: BETA -> DONE
    r2 = complete_stage(payload)
    assert r2.get("done") is True


def test_next_action_does_not_carry_next_state(tmp_path, monkeypatch):
    """next_action describes the CURRENT stage to work on — it is not a transition, so it
    must NOT carry next_state (only complete_stage's advance does). Guards against the fix
    leaking the advance signal into the wrong envelope."""
    from pathly_orchestrator.fsm_ops import next_action

    _patch_load_flow(monkeypatch)
    _patch_build_prompt(monkeypatch)
    _seed(tmp_path)

    result = next_action(
        {"flow": "test", "topic": "test-topic", "project_root": str(tmp_path)}
    )
    assert result["current_state"] == "ALPHA"
    assert "next_state" not in result


# ── Driver integration: the real runner advances through the real FSM to DONE ──


def test_run_flow_advances_through_real_fsm_to_done(tmp_path, monkeypatch, capsys):
    """End-to-end through the REAL runner driver: only next_action (display) and
    invoke_agent (the CLI spawn) are stubbed; complete_stage is REAL. Before the fix this
    printed 'Unexpected result' and returned 1 after the first transition."""
    import pathly_orchestrator.runner as runner_mod
    from pathly_orchestrator.runner import run_flow

    _patch_load_flow(monkeypatch)
    _patch_build_prompt(monkeypatch)
    _seed(tmp_path)

    # The runner's `complete_stage` is the HTTP client (forwards to the FSM server). Point it
    # at the REAL in-process fsm_ops.complete_stage so the driver exercises the real FSM logic
    # without needing a live server — the HTTP transport returns the same JSON verbatim.
    monkeypatch.setattr(runner_mod, "complete_stage", fsm_ops.complete_stage)

    # next_action only supplies the per-iteration display/instructions; the real state
    # progression is driven by the REAL complete_stage reading/writing DB state.
    monkeypatch.setattr(
        runner_mod,
        "next_action",
        lambda payload: {
            "current_state": "ALPHA",
            "agent": "team/a",
            "instructions": "do",
            "limits": {},
        },
    )
    # invoke_agent would launch a real CLI — no-op it so the test stays hermetic.
    monkeypatch.setattr(runner_mod, "invoke_agent", lambda *a, **k: None)

    rc = run_flow("test", "test-topic", str(tmp_path))
    out = capsys.readouterr().out

    assert "Unexpected result" not in out
    assert rc == 0
    assert "✓ Complete" in out


# ── Driver integration: the real SUPERVISOR loop advances through the real FSM ──


def test_supervisor_loop_advances_through_real_fsm_to_done(tmp_path, monkeypatch):
    """End-to-end through the REAL supervisor loop (Studio's headless driver): only
    next_action (display) and the PTY spawn are stubbed; complete_stage is the REAL
    fsm_ops one. Before the fix, ``_resolve_stage_supervised``'s advance gate
    (``orchestrator.py:75`` -> ``if result.get("done") or result.get("next_state")``)
    never saw ``next_state`` on a clean advance, so the supervisor fell through to the
    "Unexpected result" -> ``status=error`` branch after exactly one stage. This is the
    supervisor-side companion to the runner-loop test above — the bug lived in BOTH
    drivers and was hidden because both their unit tests mock ``complete_stage``."""
    import time
    from unittest.mock import patch

    import pathly_orchestrator.fsm_http_client as fhc
    from pathly_orchestrator.supervisor import _lock, _registry, start_run

    _patch_load_flow(monkeypatch)
    _patch_build_prompt(monkeypatch)
    _seed(tmp_path)

    topic = "test-topic"
    with _lock:
        _registry.pop(topic, None)

    na_calls = [
        {
            "current_state": "ALPHA",
            "agent": "team/a",
            "instructions": "do",
            "preferred_adapter": "claude",
        },
        {
            "current_state": "BETA",
            "agent": "team/b",
            "instructions": "do",
            "preferred_adapter": "claude",
        },
    ]

    # The supervisor's complete_stage is the HTTP client; point it at the REAL in-process
    # fsm_ops.complete_stage so the driver exercises the real FSM advance contract (same
    # technique as the runner test). _run_stage_via_terminal is stubbed so no PTY spawns.
    with (
        patch.object(fhc, "next_action", side_effect=na_calls),
        patch.object(fhc, "complete_stage", side_effect=complete_stage),
        patch(
            "pathly_orchestrator.supervisor._run_stage_via_terminal",
            return_value={"cost_usd": 0.0, "session_id": "sess-1"},
        ),
    ):
        state = start_run(
            topic=topic,
            flow="test",
            project_root=str(tmp_path),
            max_iterations=5,
            max_cost_usd=10.0,
        )
        deadline = time.monotonic() + 8.0
        while (
            state.status not in {"done", "error", "aborted"}
            and time.monotonic() < deadline
        ):
            time.sleep(0.05)

    with _lock:
        _registry.pop(topic, None)

    # Before the fix this was "error" after one transition; the advance must reach DONE.
    assert state.status == "done", f"supervisor stalled at status={state.status!r}"
    assert state.iterations == 2


# ── Smart fix-routing (pathly/features/smart-fix-routing/DESIGN.md) — drives the REAL
# team.flow.yaml + REAL complete_stage/route_feedback across a full routing chain, per
# DESIGN.md ss5's integration test plan. Only build_prompt (the non-blocked, state-advance
# path) is stubbed — same technique as _patch_build_prompt above — build_prompt_for_agent
# (the blocked-feedback path under test) is REAL throughout. ──────────────────────────────


def _load_team_flow() -> dict:
    from importlib.resources import files

    import yaml

    text = (
        files("pathly_data")
        .joinpath("core/flows/team.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _team_feature_storage(tmp_path: Path, topic: str = "fix-routing-test") -> Path:
    p = tmp_path / "pathly" / "features" / topic
    p.mkdir(parents=True, exist_ok=True)
    (p / "STATE.json").write_text(
        json.dumps({"current": "REVIEWING"}), encoding="utf-8"
    )
    return p


def test_smart_fix_routing_drives_real_team_flow(tmp_path, monkeypatch):
    """ARCH_FEEDBACK.md -> architect (stays REVIEWING); swap to REVIEW_FAILURES.md only
    -> builder (the REGRESSION assertion: byte-identical to before this feature, DESIGN.md
    risk #1 / ss5 bullet 5); remove all feedback -> hits the REVIEW.md verify gate
    (REVIEW_INCOMPLETE.md -> reviewer); write RESULT: PASS REVIEW.md -> advances
    REVIEWING -> TESTING."""
    team_flow = _load_team_flow()
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: team_flow)
    _patch_build_prompt(monkeypatch)

    topic = "fix-routing-test"
    storage = _team_feature_storage(tmp_path, topic)
    fb_dir = storage / "feedback"
    fb_dir.mkdir()
    (fb_dir / "ARCH_FEEDBACK.md").write_text(
        "- [ARCH] Layer boundary violated in the payments module.\n", encoding="utf-8"
    )
    payload = {"flow": "team", "topic": topic, "project_root": str(tmp_path)}

    # 1. ARCH_FEEDBACK.md open -> routes to architect; state stays REVIEWING; the
    # fix-mode block (build_prompt_for_agent) is REAL, not stubbed.
    r1 = complete_stage(payload)
    assert r1.get("blocked") is True
    assert r1.get("target_agent") == "architect"
    assert r1.get("current_state") == "REVIEWING"
    assert r1.get("decision") == "block"
    assert "next_state" not in r1
    assert "## Fix mode" in (r1.get("instructions") or "")
    assert "ARCHITECTURE_PROPOSAL.md" in (r1.get("instructions") or "")

    # 2. Swap to REVIEW_FAILURES.md only -> routes to builder. REGRESSION ASSERTION
    # (DESIGN.md ss5 bullet 5): a run whose only failure file is REVIEW_FAILURES.md
    # produces the exact same target/state as before this feature.
    (fb_dir / "ARCH_FEEDBACK.md").unlink()
    (fb_dir / "REVIEW_FAILURES.md").write_text(
        "- [IMPL] Off-by-one in the discount calculation.\n", encoding="utf-8"
    )
    r2 = complete_stage(payload)
    assert r2.get("blocked") is True
    assert r2.get("target_agent") == "builder"
    assert r2.get("current_state") == "REVIEWING"
    assert r2.get("decision") == "block"
    assert "Fix mode" not in (r2.get("instructions") or "")

    # 3. Remove all feedback -> no open feedback file -> falls through to the
    # REVIEWING->TESTING gate, which fails (no REVIEW.md yet) and writes
    # REVIEW_INCOMPLETE.md, routed to reviewer.
    (fb_dir / "REVIEW_FAILURES.md").unlink()
    r3 = complete_stage(payload)
    assert r3.get("blocked") is True
    assert r3.get("target_agent") == "reviewer"
    assert r3.get("file") == "REVIEW_INCOMPLETE.md"
    assert r3.get("current_state") == "REVIEWING"
    assert (fb_dir / "REVIEW_INCOMPLETE.md").exists()

    # 4. Resolve the gate: write REVIEW.md (RESULT: PASS) and clear the routed feedback
    # file -> the flow advances REVIEWING -> TESTING.
    (fb_dir / "REVIEW_INCOMPLETE.md").unlink()
    (storage / "REVIEW.md").write_text(
        "RESULT: PASS\nReviewed: conversation 1 — clean.\n", encoding="utf-8"
    )
    r4 = complete_stage(payload)
    assert r4.get("next_state") == "TESTING"
    assert r4.get("current_state") == "TESTING"
