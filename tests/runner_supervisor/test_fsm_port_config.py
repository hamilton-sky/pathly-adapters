"""PATHLY_FSM_HTTP_PORT reaches every caller, so Pathly can run beside another server on 8765.

The server already bound to the env port; its clients did not follow. The supervisor's own
/next_action calls, the port it exports to workers, and the literal ``127.0.0.1:8765`` URLs the
skills write into agent prompts all stayed on 8765, so a run on another port talked to whatever
owned 8765.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pathly_orchestrator.config import DEFAULT_FSM_PORT, fsm_port, localize_fsm_urls
from pathly_orchestrator.supervisor.registry import get_run
from pathly_orchestrator.supervisor.state import RunnerState
from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal

_PROMPT = "post with curl -X POST http://127.0.0.1:8765/comms/post and stop"


@pytest.mark.parametrize("raw", ["", "abc", "0", "70000", " "])
def test_fsm_port_falls_back_to_default_on_unset_or_invalid(
    monkeypatch, raw: str
) -> None:
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", raw)
    assert fsm_port() == DEFAULT_FSM_PORT


def test_fsm_port_reads_the_env(monkeypatch) -> None:
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8766")
    assert fsm_port() == 8766


def test_localize_is_a_no_op_on_the_default_port(monkeypatch) -> None:
    monkeypatch.delenv("PATHLY_FSM_HTTP_PORT", raising=False)
    assert localize_fsm_urls(_PROMPT) is _PROMPT


def test_localize_rewrites_every_skill_url_on_another_port(monkeypatch) -> None:
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8766")
    text = _PROMPT + "\n'http://127.0.0.1:8765/runner/event'"
    out = localize_fsm_urls(text)
    assert "8765" not in out
    assert out.count("http://127.0.0.1:8766/") == 2
    assert localize_fsm_urls("") == ""


def test_runner_state_exports_the_configured_port(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8766")
    state = RunnerState(
        topic="t", flow="team", project_root=str(tmp_path), model="", timeout=1
    )
    # isolation.py copies this into each worker's PATHLY_FSM_HTTP_PORT
    assert state.fsm_port == 8766


def test_resolve_command_localizes_the_headless_prompt(monkeypatch) -> None:
    from pathly_orchestrator.adapters import resolve_command

    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8766")
    argv = resolve_command("claude", _PROMPT, "claude-sonnet-4-6")["argv"]
    assert any("http://127.0.0.1:8766/comms/post" in a for a in argv)
    assert not any("8765" in a for a in argv)


def test_terminal_spawn_carries_the_localized_prompt(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8766")
    storage = tmp_path / "pathly" / "features" / "feat-port"
    storage.mkdir(parents=True)
    state = RunnerState(
        topic="feat-port",
        flow="team",
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=60,
        run_id="parent-1",
        current_state="BUILDING",
    )
    state.storage_path = str(storage)
    seen: dict = {}

    def broadcast(_topic, payload):
        if payload.get("type") != "TERMINAL_SPAWN":
            return
        seen["payload"] = payload
        run = get_run("feat-port-1-100")
        assert run is not None
        run.mark_started()
        run.mark_pty_result({"result": {}, "exit_code": 0})

    _run_stage_via_terminal(state, _PROMPT, "claude", "m", "feat-port-1-100", broadcast)

    payload = seen["payload"]
    assert "http://127.0.0.1:8766/comms/post" in payload["prompt"]
    assert not any("8765" in a for a in payload["argv"])
