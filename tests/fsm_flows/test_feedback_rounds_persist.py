"""The escalation ladder climbs in a headless run: `complete_stage` counts each feedback round.

`route_feedback` picks a feedback file's role from `retry_count_by_key` (rounds 1-2 the
owner, round 3 the flow's specialist, round 4 a human), but nothing wrote that count, so
every round was round 1 and the supervisor gave up with `feedback_exhausted` instead. Now
`complete_stage` records each round it routes in `fsm_state` (the DB, never `STATE.json`),
a committed transition clears the counts (the stage the file blocked was passed), and a
round routed to a human clears that file's count so the ladder starts again after the
human has had it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.fsm import route_feedback

TOPIC = "ladder-feat"
FILE = "TEST_FAILURES.md"


def _py(code: str) -> str:
    return json.dumps([sys.executable, "-c", code])


def _flow(exit_code: int = 1) -> dict:
    return {
        "version": 1,
        "flow": "ladder",
        "storage_path": "pathly/features/{topic}/",
        "states": ["A", "B"],
        "transitions": {"A": ["B"], "B": []},
        "agent_map": {"A": "team/build", "B": "team/review"},
        "feedback_routing": {"TEST_FAILURES": "builder"},
        "escalation_routing": {"TEST_FAILURES": "planner"},
        "transition_rules": {"A": {"default": "B"}},
        "transition_actions": {},
        "gates": {
            "A->B": [
                {
                    "type": "command_gate",
                    "command": _py(
                        f"print('still red'); raise SystemExit({exit_code})"
                    ),
                    "on_fail": FILE,
                }
            ]
        },
    }


@pytest.fixture()
def run(tmp_path, monkeypatch):
    """A feature at A whose A->B gate fails until `flow` is swapped for a passing one."""
    flow = {"config": _flow()}
    prompts: list = []
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda name, root=None: flow["config"])
    monkeypatch.setattr(
        fsm_ops,
        "build_prompt_for_agent",
        lambda agent, storage, feedback_file=None, retry_count=0: prompts.append(
            (agent, retry_count)
        )
        or f"fix {feedback_file}",
    )
    monkeypatch.setattr(fsm_ops, "build_prompt", lambda *a, **k: "next stage")
    storage = tmp_path / "pathly" / "features" / TOPIC
    storage.mkdir(parents=True)
    eventlog.write_state(str(storage), {"current": "A"}, flow["config"])
    return {"root": tmp_path, "storage": storage, "flow": flow, "prompts": prompts}


def _complete(run: dict, resolved: bool) -> dict:
    return fsm_ops.complete_stage(
        {
            "flow": "ladder",
            "topic": TOPIC,
            "project_root": str(run["root"]),
            "resolved_files": [FILE] if resolved else None,
        }
    )


def _counts(storage: Path) -> dict:
    return (eventlog.read_state(str(storage)) or {}).get("retry_count_by_key") or {}


def test_the_same_failure_climbs_owner_owner_specialist_human(run):
    targets = [_complete(run, resolved=i > 0)["target_agent"] for i in range(4)]

    assert targets == ["builder", "builder", "planner", "human"]
    # The retry ladder's prompt sees the same count that picked the role.
    assert run["prompts"] == [("builder", 0), ("builder", 1), ("planner", 2)]


def test_the_count_lives_in_fsm_state(run):
    _complete(run, resolved=False)
    _complete(run, resolved=True)

    assert _counts(run["storage"]) == {FILE: 2}


def test_a_human_round_restarts_the_ladder(run):
    for i in range(4):
        _complete(run, resolved=i > 0)
    assert _counts(run["storage"]) == {}

    # The human resumed and the gate fails again: round 1, the builder.
    assert _complete(run, resolved=True)["target_agent"] == "builder"


def test_a_committed_transition_clears_the_counts(run):
    _complete(run, resolved=False)
    _complete(run, resolved=True)
    run["flow"]["config"] = _flow(exit_code=0)

    result = _complete(run, resolved=True)

    assert result.get("next_state") == "B"
    assert _counts(run["storage"]) == {}


def test_a_count_in_state_json_alone_is_not_read(run):
    """The DB is the authority: a mirror file with a count does not move the ladder."""
    storage = run["storage"]
    (storage / "feedback").mkdir(exist_ok=True)
    (storage / "feedback" / FILE).write_text("red\n", encoding="utf-8")
    (storage / "STATE.json").write_text(
        json.dumps({"current": "A", "retry_count_by_key": {FILE: 2}}), encoding="utf-8"
    )

    result = route_feedback(run["flow"]["config"], storage)

    assert (result["target_agent"], result["retry_count"]) == ("builder", 0)
