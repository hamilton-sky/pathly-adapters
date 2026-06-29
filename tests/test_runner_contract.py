"""The runner contract injected by build_prompt — headless agents must never self-drive the FSM.

Regression for the headless team-flow loop: the `team/*` skill bodies instruct the agent to call
`pathly-fsm-call complete-stage` and "route back to team". Run headless under the supervisor, the
agent improvised FSM endpoints (`/fsm/complete-stage`, `/runner/next_action` → 404) and the flow
never advanced — it just respawned the planner. build_prompt now appends an authoritative runner
contract telling the agent the supervisor owns every transition, so the skill body's interactive
FSM-driving is explicitly overridden in headless mode.
"""

from __future__ import annotations

from pathlib import Path


def _build(flow_name: str, state: str, tmp_path) -> str:
    from pathly_orchestrator.fsm_compose import build_prompt
    from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path

    flow_cfg = _load_flow(flow_name, str(tmp_path))
    storage = Path(str(_resolve_storage_path(flow_cfg, str(tmp_path), "feat")))
    storage.mkdir(parents=True, exist_ok=True)
    return build_prompt(flow_cfg, state, storage)


def test_runner_contract_present_for_team_stage(tmp_path):
    """A team stage prompt forbids the exact self-drive moves that caused the 404 loop."""
    prompt = _build("team", "BUILDING", tmp_path)
    assert "supervisor owns the FSM" in prompt
    assert "pathly-fsm-call" in prompt  # named so the agent doesn't run it
    assert "complete-stage" in prompt and "next-action" in prompt
    assert "/complete_stage" in prompt and "/next_action" in prompt
    assert "route back" in prompt.lower()


def test_runner_contract_is_flow_agnostic(tmp_path):
    """The contract is injected for every flow, not just team (e.g. consultation/planner)."""
    prompt = _build("consultation", "PLANNING", tmp_path)
    assert "supervisor owns the FSM" in prompt
    assert "route back" in prompt.lower()
