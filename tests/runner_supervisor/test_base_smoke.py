"""supervisor/base_smoke.py — a red base parks a run before it spawns anything (build-proof 12).

Before the first spawn of a flow that has a ``command_gate`` on ``build`` (``team``,
``team-build``, ``goal-loop``) the supervisor runs ``verify.smoke`` (else ``verify.build``). A
non-zero exit, a timeout or a command that cannot run parks the run (``error_kind``
``base_red``) with a human escalation, so a failure the run did not cause is not blamed on it.

Real ``start_run`` / ``resume_parked_run`` threads and real settings in the per-test DB; only
``fhc`` (the FSM calls) and ``_run_stage_via_terminal`` (the CLI spawn) are patched, as in
``test_runner_fsm_integration.py``. The verify commands are real Python one-liners that append
to a log file, so how often the smoke ran is read from the file, not from a mock.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pathly_orchestrator.fsm_http_client as fhc
import pathly_orchestrator.fsm_ops as fsm_ops
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms_messages import get_active_escalations
from pathly_orchestrator.fsm_ops import complete_stage
from pathly_orchestrator.supervisor import (
    _lock,
    _registry,
    resume_parked_run,
    start_run,
)
from pathly_orchestrator.supervisor import base_smoke
from pathly_orchestrator.supervisor.state import RunnerState

TOPIC = "smoke-demo"

STAGE = {
    "current_state": "BUILDING",
    "agent": "team/build",
    "instructions": "build it",
    "preferred_adapter": "claude",
}


def _command(log: Path, code: int, say: str = "") -> str:
    """A verify command (JSON argv) that appends cwd|env to *log*, prints *say*, exits *code*."""
    script = (
        "import os, sys; "
        f"open({str(log)!r}, 'a').write("
        "os.getcwd() + '|' + os.environ.get('PATHLY_VERIFY_GATE', '') + '\\n'); "
        f"print({say!r}); "
        f"sys.exit({code})"
    )
    return json.dumps([sys.executable, "-c", script])


def _set(key: str, value: str) -> None:
    set_setting(get_db(), key, value)


def _runs(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _escalations(topic: str = TOPIC) -> list[dict]:
    return get_active_escalations(get_db(), boards=["feature"], scopes=[topic])


@pytest.fixture(autouse=True)
def _clean_registry():
    with _lock:
        _registry.pop(TOPIC, None)
    yield
    with _lock:
        _registry.pop(TOPIC, None)


class Harness:
    """Patches the FSM calls and the CLI spawn, runs a supervisor thread to its end."""

    def __init__(self, flow: str, root: Path):
        self.flow = flow
        self.root = root
        self.events: list[dict] = []
        self.done = threading.Event()
        self.done_result: dict = {}
        self.spawn = MagicMock(return_value={"cost_usd": 0.0, "session_id": "s-1"})
        self.next_action = MagicMock(return_value=dict(STAGE))
        self.complete = MagicMock(return_value={"done": True})

    def _broadcast(self, topic, payload) -> None:
        self.events.append(payload)

    def _on_done(self, run_id, result) -> None:
        self.done_result = result
        self.done.set()

    def _go(self, launch):
        self.done.clear()
        with (
            patch.object(fhc, "next_action", self.next_action),
            patch.object(fhc, "complete_stage", self.complete),
            patch("pathly_orchestrator.supervisor._run_stage_via_terminal", self.spawn),
        ):
            state = launch()
            assert self.done.wait(15), f"run never finished (status={state.status!r})"
        return state

    def start(self, **kwargs) -> RunnerState:
        return self._go(
            lambda: start_run(
                TOPIC,
                self.flow,
                str(self.root),
                max_iterations=5,
                max_cost_usd=10.0,
                broadcast_fn=self._broadcast,
                on_done=self._on_done,
                **kwargs,
            )
        )

    def resume(self) -> RunnerState:
        return self._go(
            lambda: resume_parked_run(
                TOPIC, broadcast_fn=self._broadcast, on_done=self._on_done
            )
        )


# ── A red base parks the run before anything spawns ─────────────────────────────


@pytest.mark.parametrize("flow", ["team", "team-build", "goal-loop"])
def test_a_red_build_parks_the_run_and_spawns_nothing(tmp_path, flow):
    log = tmp_path / "smoke.log"
    _set("verify.build", _command(log, 1, "BASE IS RED"))
    harness = Harness(flow, tmp_path)

    state = harness.start()

    assert state.status == "parked"
    assert state.error_kind == "base_red"
    assert harness.spawn.call_count == 0
    assert harness.next_action.call_count == 0
    assert harness.done_result["status"] == "parked"
    assert harness.done_result["error"] == "base_red"


def test_the_red_base_is_announced_to_a_human_on_the_board(tmp_path):
    log = tmp_path / "smoke.log"
    command = _command(log, 1, "BASE IS RED")
    _set("verify.build", command)
    harness = Harness("team-build", tmp_path)

    harness.start()

    human = [e for e in _escalations() if e["to_agent"] == "human"]
    assert len(human) == 1
    text = human[0]["text"]
    assert command in text
    assert "exited 1" in text
    assert "BASE IS RED" in text
    assert "before this run spawned anything" in text
    assert "resume-parked" in text and json.dumps({"topic": TOPIC}) in text
    assert human[0]["author_source"] == "system"
    assert human[0]["type"] == "escalation"


def test_the_run_broadcasts_a_parked_event_of_kind_base_red(tmp_path):
    _set("verify.build", _command(tmp_path / "smoke.log", 1))
    harness = Harness("team-build", tmp_path)

    harness.start()

    parked = [e for e in harness.events if e.get("type") == "RUNNER_PARKED"]
    assert [e["kind"] for e in parked] == ["base_red"]
    assert parked[0]["topic"] == TOPIC
    assert any(
        e.get("type") == "RUNNER_STATUS" and e.get("status") == "parked"
        for e in harness.events
    )


def test_the_smoke_runs_in_the_project_root_with_the_verify_gate_flag(tmp_path):
    log = tmp_path / "smoke.log"
    _set("verify.build", _command(log, 1))
    harness = Harness("team-build", tmp_path)

    harness.start()

    assert _runs(log) == [f"{tmp_path}|1"]


def test_a_timeout_parks_the_run_and_says_so(tmp_path):
    _set(
        "verify.build",
        json.dumps([sys.executable, "-c", "import time; time.sleep(30)"]),
    )
    _set("verify.timeout_seconds", "1")
    harness = Harness("team-build", tmp_path)

    started = time.monotonic()
    state = harness.start()

    assert time.monotonic() - started < 20
    assert state.status == "parked" and state.error_kind == "base_red"
    assert harness.spawn.call_count == 0
    assert "timed out after 1s" in _escalations()[0]["text"]


def test_a_command_that_cannot_run_parks_the_run(tmp_path):
    _set("verify.build", json.dumps(["/no/such/tool-for-smoke", "--check"]))
    harness = Harness("team-build", tmp_path)

    state = harness.start()

    assert state.status == "parked" and state.error_kind == "base_red"
    assert harness.spawn.call_count == 0
    assert "could not run" in _escalations()[0]["text"]


# ── A green or unconfigured base lets the run proceed ───────────────────────────


def test_a_green_smoke_wins_over_a_red_build(tmp_path):
    smoke_log, build_log = tmp_path / "smoke.log", tmp_path / "build.log"
    _set("verify.smoke", _command(smoke_log, 0))
    _set("verify.build", _command(build_log, 1))
    harness = Harness("team-build", tmp_path)

    state = harness.start()

    assert state.status == "done"
    assert harness.spawn.call_count == 1
    assert len(_runs(smoke_log)) == 1
    assert _runs(build_log) == []
    assert _escalations() == []


def test_a_green_build_lets_the_run_proceed(tmp_path):
    log = tmp_path / "smoke.log"
    _set("verify.build", _command(log, 0))
    harness = Harness("team-build", tmp_path)

    state = harness.start()

    assert state.status == "done"
    assert harness.spawn.call_count == 1
    assert len(_runs(log)) == 1


def test_a_red_smoke_parks_even_when_the_build_is_green(tmp_path):
    smoke_log, build_log = tmp_path / "smoke.log", tmp_path / "build.log"
    _set("verify.smoke", _command(smoke_log, 3, "SMOKE IS RED"))
    _set("verify.build", _command(build_log, 0))
    harness = Harness("team-build", tmp_path)

    state = harness.start()

    assert state.status == "parked" and state.error_kind == "base_red"
    assert harness.spawn.call_count == 0
    assert _runs(build_log) == []
    assert "exited 3" in _escalations()[0]["text"]


def test_with_neither_setting_the_run_proceeds(tmp_path):
    harness = Harness("team-build", tmp_path)

    state = harness.start()

    assert state.status == "done"
    assert harness.spawn.call_count == 1
    assert _escalations() == []


def test_a_flow_without_a_build_gate_is_not_smoked(tmp_path):
    log = tmp_path / "smoke.log"
    _set("verify.build", _command(log, 1))
    harness = Harness("consultation", tmp_path)

    state = harness.start()

    assert state.status == "done"
    assert _runs(log) == []


def test_smoke_base_false_skips_the_check(tmp_path):
    log = tmp_path / "smoke.log"
    _set("verify.build", _command(log, 1))
    harness = Harness("team-build", tmp_path)

    state = harness.start(smoke_base=False)

    assert state.status == "done"
    assert harness.spawn.call_count == 1
    assert _runs(log) == []


# ── check_base on its own ────────────────────────────────────────────────────────


def _state(root: Path, flow: str = "team-build") -> RunnerState:
    return RunnerState(
        topic=TOPIC,
        flow=flow,
        project_root=str(root),
        model="claude-sonnet-4-6",
        timeout=600,
        run_id="run-1",
        status="running",
    )


def test_check_base_returns_true_for_a_green_base(tmp_path):
    _set("verify.build", _command(tmp_path / "smoke.log", 0))
    state = _state(tmp_path)

    assert base_smoke.check_base(state, None) is True
    assert state.status == "running" and state.error_kind is None


def test_check_base_returns_false_and_parks_for_a_red_base(tmp_path):
    _set("verify.build", _command(tmp_path / "smoke.log", 1))
    state = _state(tmp_path)
    events: list[dict] = []

    ok = base_smoke.check_base(state, lambda topic, payload: events.append(payload))

    assert ok is False
    assert state.status == "parked" and state.error_kind == "base_red"
    assert [e["kind"] for e in events if e.get("type") == "RUNNER_PARKED"] == [
        "base_red"
    ]


def test_check_base_survives_a_broadcast_that_raises(tmp_path):
    _set("verify.build", _command(tmp_path / "smoke.log", 1))
    state = _state(tmp_path)

    def boom(topic, payload):
        raise RuntimeError("sse is down")

    assert base_smoke.check_base(state, boom) is False
    assert state.status == "parked"


def test_check_base_fails_open_when_it_cannot_decide(tmp_path):
    _set("verify.build", _command(tmp_path / "smoke.log", 1))
    state = _state(tmp_path)

    with patch(
        "pathly_orchestrator.supervisor.base_smoke.run_command",
        side_effect=RuntimeError("unexpected"),
    ):
        assert base_smoke.check_base(state, None) is True
    assert state.status == "running"


def test_check_base_clips_a_huge_output(tmp_path):
    _set("verify.build", _command(tmp_path / "smoke.log", 1, "x" * 50000))
    state = _state(tmp_path)

    assert base_smoke.check_base(state, None) is False

    text = _escalations()[0]["text"]
    assert "characters elided" in text
    assert len(text) < 12000


# ── Resume: re-smoke only after base_red ─────────────────────────────────────────


def test_resume_after_base_red_smokes_again(tmp_path):
    log = tmp_path / "smoke.log"
    _set("verify.build", _command(log, 1))
    harness = Harness("team-build", tmp_path)

    first = harness.start()
    assert first.status == "parked" and first.error_kind == "base_red"
    assert len(_runs(log)) == 1

    # Still red: the resume smokes again and parks again, under a NEW run id.
    second = harness.resume()
    assert second.run_id != first.run_id
    assert second.status == "parked" and second.error_kind == "base_red"
    assert len(_runs(log)) == 2
    assert harness.spawn.call_count == 0

    # The human fixes the base: the next resume smokes once more, then spawns.
    _set("verify.build", _command(log, 0))
    third = harness.resume()
    assert third.status == "done"
    assert len(_runs(log)) == 3
    assert harness.spawn.call_count == 1


HUMAN_FLOW = {
    "version": 1,
    "flow": "test-human-build",
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
    "gates": {
        "ALPHA->DONE": [
            {"type": "command_gate", "command_key": "build", "on_fail": "BUILD.md"}
        ]
    },
    "transition_actions": {},
}


def test_resume_after_a_human_checkpoint_does_not_smoke(tmp_path, monkeypatch):
    """In-progress red work must not re-park a run that stopped on a human checkpoint."""
    monkeypatch.setattr(fsm_ops, "_load_flow", lambda *_: HUMAN_FLOW)
    monkeypatch.setattr(
        fsm_ops, "build_prompt", lambda *args, **kwargs: f"instructions for {args[1]}"
    )
    storage = tmp_path / "pathly" / "plans" / TOPIC
    (storage / "feedback").mkdir(parents=True)
    (storage / "STATE.json").write_text(json.dumps({"current": "ALPHA"}), "utf-8")
    (storage / "feedback" / "HUMAN_QUESTIONS.md").write_text("Which db?", "utf-8")

    log = tmp_path / "smoke.log"
    harness = Harness("test-human-build", tmp_path)
    harness.next_action.return_value = {
        "current_state": "ALPHA",
        "agent": "team/a",
        "instructions": "do",
        "preferred_adapter": "claude",
    }
    harness.complete.side_effect = complete_stage

    # No verify command yet: the smoke skips, the run reaches the checkpoint and parks.
    first = harness.start()
    assert first.status == "parked" and first.error_kind == "human_checkpoint"

    # The builder's work in progress is red now. The resume must not smoke it.
    _set("verify.build", _command(log, 1))
    second = harness.resume()

    assert second.run_id != first.run_id
    assert second.status == "parked"
    assert second.error_kind == "human_checkpoint"
    assert _runs(log) == []
