"""The `parallel_states` flow-YAML key — fsm-fan-out Phase B (schema only, inert).

A state opts into fan-out (one FSM state drains its ready tasks, then joins) by naming
itself in `parallel_states`. Absent means today's exact behaviour, so no existing flow
changes — the last test here pins that for all nine packaged flows.

Nothing READS the key yet; Phase C is what branches on it. Validating it first is the point
of the phasing: a typo'd state name or a `max_workers: 0` is caught by
`pathly-validate-flow` rather than silently doing nothing at run time.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from pathly_orchestrator.fsm.state import validate_flow_dict

from tests._paths import SRC

_FLOW_DIR = SRC / "pathly_data" / "core" / "flows"


def _flow(parallel_states=None) -> dict:
    """A minimal flow that validates clean, optionally carrying a parallel_states block."""
    flow = {
        "storage_path": "pathly/features/{feature}",
        "states": ["PLANNING", "BUILDING", "DONE"],
        "transitions": {"PLANNING": ["BUILDING"], "BUILDING": ["DONE"]},
        "agent_map": {"PLANNING": "planner", "BUILDING": "builder"},
        "feedback_routing": {},
        "transition_actions": {},
    }
    if parallel_states is not None:
        flow["parallel_states"] = parallel_states
    return flow


def _errors(parallel_states) -> list[str]:
    return validate_flow_dict(_flow(parallel_states))[0]


def _warnings(parallel_states) -> list[str]:
    return validate_flow_dict(_flow(parallel_states))[1]


# ── The happy paths ──────────────────────────────────────────────────────────


def test_absent_key_is_unchanged():
    """A flow with no parallel_states validates exactly as before."""
    assert validate_flow_dict(_flow()) == validate_flow_dict(_flow())
    assert _flow().get("parallel_states") is None
    assert validate_flow_dict(_flow())[0] == []


@pytest.mark.parametrize(
    "config",
    [
        {"max_workers": 4, "isolation": "lane"},
        {"max_workers": 1},
        {"isolation": "serial"},
        {},
        None,  # `BUILDING:` with no body — "all defaults"
    ],
    ids=["full", "workers-only", "isolation-only", "empty-dict", "empty-body"],
)
def test_valid_blocks_pass(config):
    assert _errors({"BUILDING": config}) == []


# ── The three errors ─────────────────────────────────────────────────────────


def test_unknown_state_name_is_an_error():
    errs = _errors({"COMPILING": {"max_workers": 2}})
    assert any("COMPILING" in e and "not a declared state" in e for e in errs)


@pytest.mark.parametrize(
    "bad",
    [0, -1, "4", 2.5, None, True],
    ids=["zero", "negative", "str", "float", "none", "bool"],
)
def test_bad_max_workers_is_an_error(bad):
    """`max_workers: true` is a typo, not a cap of 1 — bool is a subclass of int."""
    errs = _errors({"BUILDING": {"max_workers": bad}})
    assert any("max_workers" in e for e in errs), f"{bad!r} should be rejected"


def test_unknown_isolation_is_an_error():
    errs = _errors({"BUILDING": {"isolation": "quantum"}})
    assert any("isolation" in e and "quantum" in e for e in errs)


def test_non_dict_block_is_an_error():
    assert any("parallel_states" in e for e in _errors(["BUILDING"]))
    assert any("BUILDING" in e for e in _errors({"BUILDING": "lane"}))


# ── The one warning ──────────────────────────────────────────────────────────


def test_worktree_validates_but_warns_that_it_is_a_stub():
    """`worktree` is legal vocabulary; WorktreeIsolation still raises NotImplementedError."""
    assert _errors({"BUILDING": {"isolation": "worktree"}}) == []
    assert any(
        "worktree" in w and "stub" in w
        for w in _warnings({"BUILDING": {"isolation": "worktree"}})
    )


def test_isolation_vocab_matches_the_isolation_module():
    """The vocabulary is not a free-standing list — each name has an implementation."""
    from pathly_orchestrator.supervisor import isolation as _iso
    from pathly_orchestrator.fsm.state import _ISOLATION_VOCAB

    for name in _ISOLATION_VOCAB:
        assert hasattr(_iso, f"{name.capitalize()}Isolation"), name


# ── Production flows are untouched ───────────────────────────────────────────


@pytest.mark.parametrize(
    "flow_path", sorted(_FLOW_DIR.glob("*.flow.yaml")), ids=lambda p: p.name
)
def test_packaged_flows_still_validate_clean(flow_path: pathlib.Path):
    """Every shipped flow validates with no errors."""
    flow = yaml.safe_load(flow_path.read_text(encoding="utf-8"))
    errors, _ = validate_flow_dict(flow)
    assert errors == [], f"{flow_path.name}: {errors}"


def test_goal_loop_is_the_only_flow_that_opts_into_fan_out():
    """Opting a flow in is a PRODUCT decision, and this is the list of them.

    Phase B shipped `parallel_states` inert — no flow declared it, so production behaviour
    could not change. Phase E adds exactly one deliberate opt-in: `goal-loop`, which IS the
    `executor: loop` product (a flat drain) and so gains nothing but its own engine back.

    Every OTHER flow opting in would change behaviour beyond concurrency — for `team-build`
    it also changes the review cadence (its `on_board_count` rule makes BUILDING drain one
    task per FSM cycle) AND which skill runs the work (a fan-out state's per-task prompts come
    from `development/execute-task`, so `team/build` would not run). This assertion is what
    makes such a change impossible to slip in unnoticed.
    """
    opted_in = sorted(
        p.name
        for p in _FLOW_DIR.glob("*.flow.yaml")
        if "parallel_states" in (yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    )
    assert opted_in == ["goal-loop.flow.yaml"]


def test_every_packaged_flow_was_actually_checked():
    """Guard against the parametrization above silently collapsing to zero cases."""
    assert len(list(_FLOW_DIR.glob("*.flow.yaml"))) == 10
