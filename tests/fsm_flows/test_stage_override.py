"""flow-gate-preview (P2) — the transient per-run, per-stage prompt override channel.

build_prompt(stage_override=...) replaces ONLY the composed agent_text for that state,
verbatim (after <feature>/<board>/... var substitution), while the server-only tail
(runner contract / pipeline history / board / code) still appends exactly as it does for a
composed stage. Covers DESIGN.md ss2 (the data flow) and R4 (an override must skip
_apply_stage_selection — never double-trim). Also covers fsm_ops.next_action picking the
override for the CURRENT state only (DESIGN.md ss2 pseudocode).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

FLOW_CONFIG = {
    "agent_map": {"BUILDING": "quick"},
    "composition": {},
}


def _storage(tmp_path: Path, feature: str = "test-feature") -> Path:
    p = tmp_path / "pathly" / "features" / feature
    p.mkdir(parents=True, exist_ok=True)
    return p


def test_build_prompt_stage_override_verbatim_and_tail_appended(tmp_path, monkeypatch):
    """agent_text == the (var-substituted) override; compose is skipped entirely; the
    context/history/board tail still appends, exactly like a composed stage."""
    import pathly_orchestrator.fsm_compose as fsm_compose

    mock_load_agent_text = MagicMock(return_value="SHOULD NOT APPEAR — compose was skipped")
    monkeypatch.setattr(fsm_compose, "_load_agent_text", mock_load_agent_text)

    storage_path = _storage(tmp_path)
    from pathly_orchestrator.eventlog import append_event

    append_event(
        str(storage_path),
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 1,
            "summary": "smoke test entry",
            "ts": "2026-01-01T00:00:00Z",
            "schema_version": 1,
        },
    )

    override = "Custom trimmed prompt for <feature>."
    prompt = fsm_compose.build_prompt(
        FLOW_CONFIG, "BUILDING", storage_path, stage_override=override
    )

    # agent_text is the override, verbatim except <feature> substitution — not the composed
    # (mocked) skill body.
    assert prompt.startswith("Custom trimmed prompt for test-feature.")
    mock_load_agent_text.assert_not_called()

    # Server-only tail: runner contract (context) + pipeline history — both still append.
    assert "## Current task" in prompt
    assert "supervisor owns the FSM" in prompt
    assert "## Pipeline History" in prompt
    assert "smoke test entry" in prompt


def test_build_prompt_stage_override_absent_composes_normally(tmp_path, monkeypatch):
    """Baseline: no stage_override → the bare agent still composes via _load_agent_text."""
    import pathly_orchestrator.fsm_compose as fsm_compose

    monkeypatch.setattr(fsm_compose, "_load_agent_text", lambda *_: "base agent text")

    storage_path = _storage(tmp_path)
    prompt = fsm_compose.build_prompt(FLOW_CONFIG, "BUILDING", storage_path)

    assert prompt.startswith("base agent text")


def test_build_prompt_stage_override_skips_stage_selection(tmp_path):
    """R4 — an override must NOT be re-run through _apply_stage_selection (never
    double-trim). Contrast: the SAME ability_ids appended when no override is set."""
    from pathly_orchestrator.fsm_compose import build_prompt
    from pathly_orchestrator.skills.abilities import write_ability

    write_ability(
        "build",
        "react-web",
        "# React web\n\nPrefer function components.",
        project_root=str(tmp_path),
        scope="project",
    )
    storage_path = _storage(tmp_path)

    composed = build_prompt(
        FLOW_CONFIG,
        "BUILDING",
        storage_path,
        ability_ids=["build/react-web"],
    )
    assert "Prefer function components." in composed

    overridden = build_prompt(
        FLOW_CONFIG,
        "BUILDING",
        storage_path,
        ability_ids=["build/react-web"],
        stage_override="Verbatim gate text.",
    )
    assert overridden.startswith("Verbatim gate text.")
    assert "Prefer function components." not in overridden


def _routing_flow() -> dict:
    return {
        "version": 1,
        "flow": "test",
        "storage_path": "pathly/features/{topic}/",
        "states": ["BUILDING"],
        "transitions": {"BUILDING": []},
        "agent_map": {"BUILDING": "builder"},
        "feedback_routing": {},
        "transition_rules": {},
        "transition_actions": {},
    }


def test_next_action_threads_stage_override_for_current_state(tmp_path, monkeypatch):
    """next_action picks the override keyed by the CURRENT state and passes it through as
    build_prompt's stage_override kwarg — an entry for a DIFFERENT state is ignored."""
    import pathly_orchestrator.fsm_ops as fsm_ops

    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: _routing_flow())
    captured: dict = {}

    def _fake_build_prompt(*args, **kwargs):
        captured.update(kwargs)
        return "instructions"

    monkeypatch.setattr(fsm_ops, "build_prompt", _fake_build_prompt)

    fsm_ops.next_action(
        {
            "flow": "test",
            "topic": "override-topic",
            "project_root": str(tmp_path),
            "stage_overrides": {
                "BUILDING": "custom override text",
                "SOME_OTHER_STATE": "must not apply",
            },
        }
    )

    assert captured.get("stage_override") == "custom override text"


def test_next_action_stage_override_empty_when_absent(tmp_path, monkeypatch):
    """No stage_overrides in the request → build_prompt gets stage_override="" (compose
    normally) — the zero-cost common path."""
    import pathly_orchestrator.fsm_ops as fsm_ops

    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: _routing_flow())
    captured: dict = {}

    def _fake_build_prompt(*args, **kwargs):
        captured.update(kwargs)
        return "instructions"

    monkeypatch.setattr(fsm_ops, "build_prompt", _fake_build_prompt)

    fsm_ops.next_action(
        {
            "flow": "test",
            "topic": "no-override-topic",
            "project_root": str(tmp_path),
        }
    )

    assert captured.get("stage_override") == ""
