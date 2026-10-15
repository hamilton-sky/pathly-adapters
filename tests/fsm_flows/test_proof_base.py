"""build-proof 15: the run-wide ``proof_base`` and the ``TASK_PROOF`` records.

``fsm/gates/_proof_record.py`` stamps ``proof_base {tree, started_at}`` into STATE on first
entry to a state with an outgoing ``floor_gate`` or ``task_checks`` (``fsm_ops.next_action``),
keeps it across every transition but the one into DONE (``fsm_ops_complete``), and records and
reads ``TASK_PROOF`` events. No gate reads any of it yet. Setup is in ``review_packet_support``.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime
from importlib.resources import files

import pytest
import yaml
from review_packet_support import (
    FEATURE,
    _args,
    _claim,
    _enter_building,
    _state,
    _storage,
    _write,
    flow,
    repo,
)

from pathly_orchestrator import eventlog, fsm_ops
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.task_proof import get_task
from pathly_orchestrator.fsm.gates import _proof_record as proof_record
from pathly_orchestrator.proof import tree
from pathly_orchestrator.supervisor.task_retry import retry_task

FLOOR = {"type": "floor_gate", "on_fail": "FLOOR_FAILURES.md"}


def _gates(**gates: list) -> dict:
    """A tiny flow: A -> B -> DONE, with the given gate lists."""
    return {"transitions": {"A": ["B"], "B": ["DONE"], "DONE": []}, "gates": gates}


@pytest.fixture
def floored(flow) -> dict:
    """``team-build`` with one ``floor_gate`` on ``BUILDING->REVIEWING``."""
    gated = copy.deepcopy(flow)
    gated["gates"]["BUILDING->REVIEWING"].append(dict(FLOOR))
    return gated


@pytest.fixture
def goal_loop() -> dict:
    """``goal-loop`` with one ``floor_gate`` on ``DRAINING->DONE``."""
    text = (
        files("pathly_data")
        .joinpath("core/flows/goal-loop.flow.yaml")
        .read_text(encoding="utf-8")
    )
    gated = yaml.safe_load(text)
    gated["gates"]["DRAINING->DONE"].append(dict(FLOOR))
    return gated


def _post_pending() -> None:
    post_message(
        get_db(),
        board="feature",
        scope="demo",
        from_agent="planner",
        type="task",
        text="Still to do.\n",
    )


def _patched(monkeypatch, flow_config: dict) -> None:
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *a, **k: flow_config)


# --- which states want a base ----------------------------------------------------------


def test_a_state_with_an_outgoing_floor_gate_wants_a_base():
    flow_config = _gates(**{"A->B": [FLOOR]})

    assert proof_record.wants_proof_base(flow_config, "A") is True


def test_a_state_with_an_outgoing_task_checks_gate_wants_a_base():
    flow_config = _gates(
        **{"A->B": [{"type": "command_gate"}, {"type": "task_checks"}]}
    )

    assert proof_record.wants_proof_base(flow_config, "A") is True


def test_a_done_wildcard_counts_for_a_state_that_can_reach_done():
    flow_config = _gates(**{"->DONE": [FLOOR]})

    assert proof_record.wants_proof_base(flow_config, "B") is True
    # A cannot go to DONE, so the wildcard is no edge out of A.
    assert proof_record.wants_proof_base(flow_config, "A") is False


def test_a_state_with_neither_gate_type_does_not_want_a_base():
    flow_config = _gates(
        **{
            "A->B": [{"type": "command_gate"}, {"type": "scope_gate"}],
            "->DONE": [{"type": "require_tasks_done"}],
        }
    )

    assert proof_record.wants_proof_base(flow_config, "A") is False
    assert proof_record.wants_proof_base(flow_config, "B") is False
    assert proof_record.wants_proof_base(_gates(), "A") is False
    assert proof_record.wants_proof_base({}, "A") is False


def test_a_gate_on_an_edge_into_the_state_is_not_an_edge_out_of_it():
    flow_config = _gates(**{"A->B": [FLOOR]})

    assert proof_record.wants_proof_base(flow_config, "B") is False


# --- the stamp --------------------------------------------------------------------------


def test_stamp_returns_none_when_the_state_has_a_base_already(repo):
    flow_config = _gates(**{"A->B": [FLOOR]})
    prior = {"proof_base": {"tree": "abc", "started_at": "2020-01-01T00:00:00+00:00"}}

    assert proof_record.stamp_proof_base(prior, flow_config, "A", str(repo)) is None


def test_stamp_returns_none_for_a_state_that_wants_none(repo):
    assert proof_record.stamp_proof_base({}, _gates(), "A", str(repo)) is None


def test_stamp_is_a_tree_and_the_time(repo):
    flow_config = _gates(**{"A->B": [FLOOR]})

    stamp = proof_record.stamp_proof_base({}, flow_config, "A", str(repo))

    assert re.fullmatch(r"[0-9a-f]{40,64}", stamp["tree"])
    assert tree.blob(repo, stamp["tree"], "src/app.py") == "x = 1\ny = 2\n"
    assert datetime.fromisoformat(stamp["started_at"]).tzinfo is not None


# --- next_action stamps it ---------------------------------------------------------------


def test_next_action_stamps_proof_base_on_a_state_with_a_floor_gate(
    repo, flow, floored, monkeypatch
):
    _patched(monkeypatch, floored)

    _enter_building(repo, flow)

    base = _state(repo)["proof_base"]
    assert re.fullmatch(r"[0-9a-f]{40,64}", base["tree"])
    assert datetime.fromisoformat(base["started_at"])
    # It is the project as it was when the run began, like the build baseline's tree.
    assert base["tree"] == _state(repo)["build_baseline"]["tree"]


def test_a_second_next_action_keeps_the_first_base(repo, flow, floored, monkeypatch):
    _patched(monkeypatch, floored)
    _enter_building(repo, flow)
    first = _state(repo)["proof_base"]
    _write(repo, "src/app.py", "x = 3\ny = 2\n")

    fsm_ops.next_action(_args(repo))

    assert _state(repo)["proof_base"] == first


def test_no_base_is_stamped_without_a_floor_or_task_checks_gate(repo, flow):
    _enter_building(repo, flow)

    assert "proof_base" not in _state(repo)


def test_goal_loop_stamps_the_base_on_draining(repo, goal_loop, monkeypatch):
    _patched(monkeypatch, goal_loop)
    eventlog.write_state(str(_storage(repo)), {"current": "DRAINING"}, goal_loop)

    fsm_ops.next_action({**_args(repo), "flow": "goal-loop"})
    first = _state(repo)["proof_base"]
    fsm_ops.next_action({**_args(repo), "flow": "goal-loop"})

    assert _state(repo)["current"] == "DRAINING"
    assert re.fullmatch(r"[0-9a-f]{40,64}", first["tree"])
    assert first["started_at"]
    assert _state(repo)["proof_base"] == first


def test_outside_git_the_base_has_no_tree_but_a_time(
    tmp_path, flow, floored, monkeypatch
):
    plain = tmp_path / "plain"
    _write(plain, FEATURE + "/IMPLEMENTATION_PLAN.md", "# Plan\n")
    set_setting(get_db(), "code_context.backend", "off")
    _patched(monkeypatch, floored)
    eventlog.write_state(str(plain / FEATURE), {"current": "BUILDING"}, flow)

    fsm_ops.next_action({**_args(plain), "project_root": str(plain)})

    base = (eventlog.read_state(str(plain / FEATURE)) or {})["proof_base"]
    assert base["tree"] is None
    assert datetime.fromisoformat(base["started_at"])


# --- complete_stage keeps it until DONE -------------------------------------------------


def test_leaving_building_keeps_the_base(repo, flow, floored, monkeypatch):
    with monkeypatch.context() as patch:
        _patched(patch, floored)
        _enter_building(repo, flow)
    stamped = _state(repo)["proof_base"]
    _claim()
    _write(repo, "src/app.py", "x = 2\ny = 2\n")

    # The packaged flow has no floor gate yet to run; it is only the stamp that is under test.
    fsm_ops.complete_stage(_args(repo))

    state = _state(repo)
    assert state["current"] == "REVIEWING"
    assert state["proof_base"] == stamped
    assert "build_baseline" not in state


def test_a_back_edge_keeps_the_base(repo, flow):
    base = {"tree": "a" * 40, "started_at": "2020-01-01T00:00:00+00:00"}
    eventlog.write_state(
        str(_storage(repo)), {"current": "REVIEWING", "proof_base": base}, flow
    )
    _post_pending()

    # A task still ready sends REVIEWING back to BUILDING (on_board_count).
    fsm_ops.complete_stage(_args(repo))

    state = _state(repo)
    assert state["current"] == "BUILDING"
    assert state["proof_base"] == base


def test_the_transition_into_done_drops_the_base(repo, flow):
    base = {"tree": "a" * 40, "started_at": "2020-01-01T00:00:00+00:00"}
    eventlog.write_state(
        str(_storage(repo)), {"current": "RETRO", "proof_base": base}, flow
    )

    fsm_ops.complete_stage(_args(repo))

    state = _state(repo)
    assert state["current"] == "DONE"
    assert "proof_base" not in state


# --- reading the base back ---------------------------------------------------------------


def test_read_proof_base_gives_the_stamped_dict(repo, flow, floored, monkeypatch):
    _patched(monkeypatch, floored)
    _enter_building(repo, flow)

    assert proof_record.read_proof_base(_storage(repo)) == _state(repo)["proof_base"]


def test_read_proof_base_is_none_without_a_state_or_a_base(repo, flow):
    assert proof_record.read_proof_base(_storage(repo)) is None

    eventlog.write_state(str(_storage(repo)), {"current": "BUILDING"}, flow)

    assert proof_record.read_proof_base(_storage(repo)) is None


# --- TASK_PROOF records ------------------------------------------------------------------


def _proof_events(repo) -> list[dict]:
    events = eventlog.read_events(str(_storage(repo)))
    return [e for e in events if e["type"] == "TASK_PROOF"]


def _record(repo, task, checks="passed", floor="clean", **extra) -> None:
    proof_record.record_task_proof(
        _storage(repo), task, "run-1", checks, floor, **extra
    )


def test_record_task_proof_appends_the_event(repo):
    task = get_task(get_db(), _claim())

    _record(repo, task, "none", "n/a", warnings=["fewer asserts"])

    (event,) = _proof_events(repo)
    assert event["task_id"] == task["id"]
    assert event["claimed_at"] == task["claimed_at"]
    assert event["run_id"] == "run-1"
    assert event["checks"] == "none"
    assert event["floor"] == "n/a"
    assert event["warnings"] == ["fewer asserts"]


def test_record_task_proof_defaults_to_no_warnings(repo):
    _record(repo, get_task(get_db(), _claim()))

    assert _proof_events(repo)[0]["warnings"] == []


@pytest.mark.parametrize(
    "checks, floor", [("pass", "clean"), ("passed", "ok"), ("", "clean"), (None, "off")]
)
def test_record_task_proof_refuses_an_unknown_result(repo, checks, floor):
    task = get_task(get_db(), _claim())

    with pytest.raises(ValueError):
        _record(repo, task, checks, floor)

    assert _proof_events(repo) == []


def test_a_task_with_a_passing_record_is_proven(repo):
    task = get_task(get_db(), _claim())
    assert proof_record.task_proven(_storage(repo), task) is False

    _record(repo, task)

    assert proof_record.task_proven(_storage(repo), task) is True


def test_a_task_claimed_again_is_not_proven(repo):
    conn = get_db()
    task_id = _claim()
    _record(repo, get_task(conn, task_id))
    retry_task(conn, task_id, "the checks failed")
    assert claim_task(conn, task_id, "build")

    again = get_task(conn, task_id)

    assert proof_record.task_proven(_storage(repo), again) is False
    # Proving the new claim makes it proven again.
    _record(repo, again)
    assert proof_record.task_proven(_storage(repo), again) is True


def test_a_failed_floor_leaves_the_task_unproven(repo):
    task = get_task(get_db(), _claim())

    _record(repo, task, "passed", "failed")

    assert proof_record.task_proven(_storage(repo), task) is False


@pytest.mark.parametrize("checks", ["failed", "error"])
def test_failed_or_errored_checks_leave_the_task_unproven(repo, checks):
    task = get_task(get_db(), _claim())

    _record(repo, task, checks, "clean")

    assert proof_record.task_proven(_storage(repo), task) is False


@pytest.mark.parametrize("floor", ["clean", "off", "n/a"])
def test_a_task_with_no_check_block_is_proven_unless_the_floor_failed(repo, floor):
    task = get_task(get_db(), _claim())

    _record(repo, task, "none", floor)

    assert proof_record.task_proven(_storage(repo), task) is True


def test_the_newest_record_for_the_claim_decides(repo):
    task = get_task(get_db(), _claim())
    _record(repo, task, "passed", "clean")
    _record(repo, task, "failed", "clean")
    assert proof_record.task_proven(_storage(repo), task) is False

    _record(repo, task, "passed", "clean")

    assert proof_record.task_proven(_storage(repo), task) is True


def test_another_tasks_record_proves_nothing(repo):
    first = get_task(get_db(), _claim())
    second = get_task(get_db(), _claim("Another task.\n"))

    _record(repo, first)

    assert proof_record.task_proven(_storage(repo), first) is True
    assert proof_record.task_proven(_storage(repo), second) is False
