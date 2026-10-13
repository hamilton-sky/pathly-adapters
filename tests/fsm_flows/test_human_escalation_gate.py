"""Human escalation gate — an open gate addressed to a human blocks the transition.

Escalations used to fire correctly and gate nothing: on the board in
docs/BOARD_LIFECYCLE_FINDINGS.md four escalations sat status='pending' with
acknowledged_by=[] while the FSM ran past all of them to DONE.

Two deliberate limits are pinned here as hard as the gate itself:
  * only `to_agent='human'` gates — agent-addressed escalations are feedback ROUTING, and
    gating on them would wedge runs the pipeline is designed to self-heal.
  * force_past_gate advances but RECORDS the override on the board, so a bypassed gate stays
    auditable rather than becoming invisible.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.fsm_ops import complete_stage

FLOW = {
    "flow": "test",
    "version": 1,
    "storage_path": "pathly/plans/{topic}/",
    "states": ["BUILDING", "REVIEWING", "DONE"],
    "transitions": {"BUILDING": ["REVIEWING"], "REVIEWING": ["DONE"], "DONE": []},
    "agent_map": {
        "BUILDING": "team/build",
        "REVIEWING": "team/review",
        "DONE": "team/retro",
    },
    "feedback_routing": {"HUMAN_QUESTIONS": "human"},
    "transition_rules": {"BUILDING": {"default": "REVIEWING"}},
    "transition_actions": {},
    "gates": {},
}


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    """A feature parked at BUILDING, with complete_stage wired to the toy flow above."""
    feature = f"gate-{tmp_path.name[-8:]}"
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda _n, _r=None: FLOW)
    monkeypatch.setattr(
        fsm_ops,
        "build_prompt",
        lambda fc, state, sp, goal_id="": f"instructions {state}",
    )
    storage = tmp_path / "pathly" / "plans" / feature
    storage.mkdir(parents=True)

    def reset():
        eventlog.write_state(str(storage), {"current": "BUILDING", "feature": feature})

    reset()

    def advance(**extra):
        return complete_stage(
            {
                "flow": "test",
                "topic": feature,
                "project_root": str(tmp_path),
                "scope": feature,
                **extra,
            }
        )

    return {"feature": feature, "advance": advance, "reset": reset, "conn": get_db()}


def _escalate(conn, feature, text, to_agent):
    return post_message(
        conn,
        "feature",
        feature,
        "architect",
        type="escalation",
        text=text,
        to_agent=to_agent,
    )


def test_open_human_escalation_blocks_the_transition(harness):
    _escalate(
        harness["conn"],
        harness["feature"],
        "Human checkpoint required — daemon self-spawns without explicit consent",
        "human",
    )
    r = harness["advance"]()
    assert r["decision"] == "escalate"
    assert r["blocked"] is True
    assert r["human_gate"]["blocked_transition"] == "BUILDING->REVIEWING"
    assert len(r["human_gate"]["escalations"]) == 1
    assert "does not close a human gate" in r["instructions"]


def test_a_blocked_transition_does_not_advance_the_state(harness):
    """The gate must block, not merely warn — the whole defect was advancing anyway."""
    _escalate(harness["conn"], harness["feature"], "needs a human", "human")
    harness["advance"]()
    # A second call must still be at the pre-gate state: a gate that logs and advances anyway
    # is exactly the behaviour this replaces.
    r2 = harness["advance"]()
    assert r2["current_state"] == "BUILDING"
    assert "human_gate" in r2


def test_agent_addressed_escalation_does_not_gate(harness):
    """Agent-addressed escalations are ordinary feedback routing — gating them would wedge
    runs the pipeline resolves itself."""
    _escalate(
        harness["conn"],
        harness["feature"],
        "architect, re-check the layer rule",
        "architect",
    )
    r = harness["advance"]()
    assert "human_gate" not in r
    assert r.get("current_state") == "REVIEWING"


def test_server_written_escalation_does_not_gate(harness):
    """A park notice is the server announcing a checkpoint the feedback file already
    enforces; gating on it too would re-park every resumed run (test_park_resume)."""
    from pathly_orchestrator.runner.provenance import system_stamp

    post_message(
        harness["conn"],
        "feature",
        harness["feature"],
        "system",
        type="escalation",
        text="Human checkpoint: resolve HUMAN_QUESTIONS.md, then resume",
        to_agent="human",
        **system_stamp(),
    )
    r = harness["advance"]()
    assert "human_gate" not in r
    assert r.get("current_state") == "REVIEWING"


def test_broadcast_escalation_does_not_gate(harness):
    """ "*" is the DEFAULT `to` on every post — treating it as human-addressed would turn
    every broadcast escalation into a checkpoint."""
    _escalate(harness["conn"], harness["feature"], "heads up, everyone", "*")
    r = harness["advance"]()
    assert "human_gate" not in r
    assert r.get("current_state") == "REVIEWING"


def test_acknowledged_escalation_stops_gating(harness):
    """The normal way a human clears a gate."""
    from pathly_orchestrator.db.queries.comms import acknowledge_message

    mid = _escalate(harness["conn"], harness["feature"], "answer me", "human")
    assert "human_gate" in harness["advance"]()

    acknowledge_message(harness["conn"], mid, "human")
    harness["reset"]()
    r = harness["advance"]()
    assert "human_gate" not in r
    assert r.get("current_state") == "REVIEWING"


def test_force_past_gate_advances_and_records_the_override(harness):
    """Forcing is allowed — silently forgetting that you forced is not."""
    from pathly_orchestrator.db.queries.comms import get_messages

    _escalate(
        harness["conn"], harness["feature"], "Option B is not recommended", "human"
    )
    assert "human_gate" in harness["advance"]()

    harness["reset"]()
    r = harness["advance"](force_past_gate=True, actor="human")
    assert "human_gate" not in r
    assert r.get("current_state") == "REVIEWING"

    posts = get_messages(
        harness["conn"], "feature", harness["feature"], type="decision"
    )
    overrides = [m for m in posts if "GATE OVERRIDE" in (m.get("text") or "")]
    assert len(overrides) == 1, "a forced gate must leave a trace on the board"
    assert "Option B is not recommended" in overrides[0]["text"]
    # One force is enough: the forced-past escalation no longer re-blocks every later step.
    from pathly_orchestrator.fsm_human_gate import open_human_gates

    assert open_human_gates("feature", harness["feature"]) == []


def test_a_truthy_string_does_not_force(harness):
    """Only a JSON true forces; "false" is a truthy string."""
    _escalate(harness["conn"], harness["feature"], "needs a human", "human")
    r = harness["advance"](force_past_gate="false")
    assert "human_gate" in r


def test_force_past_gate_is_refused_for_an_agent_run():
    """An agent that can force past a human gate is the failure the gate exists to stop."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token
    from pathly_orchestrator.http_server import app

    token = mint_run_token(
        get_db(), "run-force", "builder", "f", "/tmp/p", "feature", "f"
    )
    with app.test_client() as client:
        r = client.post(
            "/complete_stage",
            headers={"X-Pathly-Run-Token": token},
            json={
                "flow": "test",
                "topic": "f",
                "project_root": "/tmp/p",
                "force_past_gate": True,
            },
        )
    assert r.status_code == 403


def test_goal_runs_check_the_parent_board_scope(harness):
    """A goal run's topic is its own slug while its agents post on the parent feature board;
    checking only the topic scope made the gate a silent no-op for every goal run."""
    from pathly_orchestrator.fsm_human_gate import gate_scopes

    goal = post_message(
        harness["conn"], "feature", harness["feature"], "planner", type="goal", text="g"
    )
    topic = f"features/{harness['feature']}/goals/g-slug"
    scopes = gate_scopes(topic, topic, "/tmp/p", goal)
    assert topic in scopes and harness["feature"] in scopes


def test_gate_read_failure_fails_open(monkeypatch):
    """A DB hiccup must not wedge every transition in the product."""
    import pathly_orchestrator.db.connection as conn_mod
    from pathly_orchestrator.fsm_human_gate import open_human_gates

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(conn_mod, "get_db", boom)
    assert open_human_gates("feature", "anything") == []


def test_record_override_with_no_gates_is_a_noop():
    from pathly_orchestrator.fsm_human_gate import record_gate_override

    record_gate_override("feature", "nowhere", [], "human")  # must not raise
