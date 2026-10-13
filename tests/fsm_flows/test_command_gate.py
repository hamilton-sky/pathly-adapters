"""Tests for ``command_gate`` — the executed (ground-truth) transition gate.

Every other gate reads a file an agent wrote. This one runs a real subprocess and reads
its exit code, so these tests run real subprocesses too (``sys.executable -c …``): a gate
whose whole value is "it actually ran the command" is not worth testing against a mock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pathly_orchestrator.fsm import run_gates
from pathly_orchestrator.fsm.gates.command import _clip, _to_argv

# ── Helpers ───────────────────────────────────────────────────────────────────


def _storage(tmp_path: Path, topic: str = "cmd-feature") -> Path:
    p = tmp_path / "pathly" / "features" / topic
    p.mkdir(parents=True, exist_ok=True)
    return p


def _flow(gate: dict) -> dict:
    return {
        "version": 1,
        "flow": "test",
        "storage_path": "pathly/features/{topic}/",
        "states": ["A", "B"],
        "transitions": {"A": ["B"], "B": []},
        "agent_map": {"A": "team/build", "B": "team/review"},
        "feedback_routing": {"BUILD_FAILURES": "builder"},
        "transition_rules": {"A": {"default": "B"}},
        "transition_actions": {},
        "gates": {"A->B": [gate]},
    }


def _py(code: str) -> str:
    """A shell-free command string that runs `code` in this interpreter."""
    return json.dumps([sys.executable, "-c", code])


def _events(storage: Path, topic: str = "cmd-feature") -> list[dict]:
    from pathly_orchestrator import db as _db

    conn = _db.get_db()
    project_root = str(storage.parent.parent.parent)
    return _db.read_events(conn, project_root, topic)


def _feedback(storage: Path, name: str) -> str:
    return (storage / "feedback" / name).read_text(encoding="utf-8")


# ── The core contract: exit code decides ──────────────────────────────────────


def test_exit_zero_passes_the_gate(tmp_path):
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py("raise SystemExit(0)"),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    assert run_gates(flow, "A", "B", storage, "cmd-feature", 1) is None
    assert not (storage / "feedback" / "BUILD_FAILURES.md").exists()

    passed = [e for e in _events(storage) if e.get("type") == "GATE_PASSED"]
    assert len(passed) == 1
    assert passed[0]["gate"] == "command_gate"
    assert passed[0]["exit_code"] == 0
    assert passed[0]["transition"] == "A->B"


def test_exit_nonzero_blocks_the_gate(tmp_path):
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py("raise SystemExit(3)"),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    result = run_gates(flow, "A", "B", storage, "cmd-feature", 1)
    assert result == {
        "gate_failed": "command_gate",
        "feedback_file": "BUILD_FAILURES.md",
    }

    failed = [e for e in _events(storage) if e.get("type") == "GATE_FAILED"]
    assert len(failed) == 1
    assert failed[0]["exit_code"] == 3
    assert "exited 3" in failed[0]["reason"]


def test_a_lying_agent_cannot_pass_an_executed_gate(tmp_path):
    """The whole point: a PASS marker on disk does not satisfy command_gate.

    A verify_gate is satisfied by the agent writing 'RESULT: PASS'. This gate is not —
    it re-derives the answer from the process exit code.
    """
    storage = _storage(tmp_path)
    (storage / "VERIFY.md").write_text("RESULT: PASS\nall good!\n", encoding="utf-8")
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py("raise SystemExit(1)"),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    assert run_gates(flow, "A", "B", storage, "cmd-feature", 1) is not None


# ── Failure feedback carries the REAL output ──────────────────────────────────


def test_feedback_file_carries_command_exit_code_and_output(tmp_path):
    storage = _storage(tmp_path)
    code = (
        "import sys; "
        "print('E: undefined name widget'); "
        "print('boom on stderr', file=sys.stderr); "
        "raise SystemExit(2)"
    )
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py(code),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    run_gates(flow, "A", "B", storage, "cmd-feature", 1)
    text = _feedback(storage, "BUILD_FAILURES.md")

    assert "exited 2" in text
    assert "E: undefined name widget" in text  # stdout
    assert "boom on stderr" in text  # stderr
    assert "MEASURED result" in text


def test_gate_runs_in_the_project_root_not_the_storage_dir(tmp_path):
    """cwd must be the repo root, so `pytest`/`npm test` resolve the project's config."""
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py("import os; print(os.getcwd()); raise SystemExit(9)"),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    run_gates(flow, "A", "B", storage, "cmd-feature", 1)
    printed_cwd = _feedback(storage, "BUILD_FAILURES.md")

    assert str(tmp_path) in printed_cwd
    assert str(storage) not in printed_cwd


def test_nested_goal_run_still_resolves_the_repo_root(tmp_path):
    """A goals/<slug> run is 5 levels below the root, not 3 — the gate must still find it."""
    storage = tmp_path / "pathly" / "features" / "f" / "goals" / "g"
    storage.mkdir(parents=True, exist_ok=True)
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py("import os; print(os.getcwd()); raise SystemExit(7)"),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    run_gates(flow, "A", "B", storage, "g", 1)
    text = (storage / "feedback" / "BUILD_FAILURES.md").read_text(encoding="utf-8")
    assert str(tmp_path) in text
    assert "pathly/features/f/goals" not in text.replace("\\", "/")


# ── Fail-open on absent config, fail-closed on broken config ──────────────────


def test_unconfigured_command_skips_the_gate(tmp_path):
    """Adding this gate to a shared flow must not break a project with no verify command."""
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command_key": "definitely-not-configured",
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    assert run_gates(flow, "A", "B", storage, "cmd-feature", 1) is None
    assert not (storage / "feedback" / "BUILD_FAILURES.md").exists()

    skipped = [e for e in _events(storage) if e.get("type") == "GATE_SKIPPED"]
    assert any(e["reason"] == "no_command_configured" for e in skipped)


def test_unexecutable_command_fails_closed(tmp_path):
    """A verify command that can never run must NOT silently pass every gate forever."""
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command": "pathly-no-such-binary-xyz --run",
            "command_key": "test",
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    result = run_gates(flow, "A", "B", storage, "cmd-feature", 1)
    assert result is not None
    text = _feedback(storage, "BUILD_FAILURES.md")
    assert "could not be executed" in text
    assert "verify.test" in text  # names the setting to fix


def test_timeout_is_a_failure_not_a_crash(tmp_path):
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command": _py("import time; time.sleep(30)"),
            "timeout": 1,
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    result = run_gates(flow, "A", "B", storage, "cmd-feature", 1)
    assert result == {
        "gate_failed": "command_gate",
        "feedback_file": "BUILD_FAILURES.md",
    }
    assert "timed out" in _feedback(storage, "BUILD_FAILURES.md")


# ── Command resolution ────────────────────────────────────────────────────────


def test_command_resolves_from_the_verify_setting(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "verify.test", _py("raise SystemExit(5)"))
    storage = _storage(tmp_path)
    flow = _flow(
        {"type": "command_gate", "command_key": "test", "on_fail": "TEST_FAILURES.md"}
    )

    result = run_gates(flow, "A", "B", storage, "cmd-feature", 1)
    assert result == {
        "gate_failed": "command_gate",
        "feedback_file": "TEST_FAILURES.md",
    }
    assert "exited 5" in _feedback(storage, "TEST_FAILURES.md")


def test_yaml_literal_beats_the_setting(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "verify.build", _py("raise SystemExit(1)"))
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command_key": "build",
            "command": _py("raise SystemExit(0)"),
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    assert run_gates(flow, "A", "B", storage, "cmd-feature", 1) is None


# ── argv splitting ────────────────────────────────────────────────────────────


def test_to_argv_splits_a_plain_command():
    assert _to_argv("python -m pytest tests/ -q") == [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-q",
    ]


def test_to_argv_honors_quoting():
    assert _to_argv('npm test -- --grep "two words"') == [
        "npm",
        "test",
        "--",
        "--grep",
        "two words",
    ]


def test_to_argv_accepts_a_json_array():
    assert _to_argv('["C:\\\\py\\\\python.exe", "-m", "pytest"]') == [
        "C:\\py\\python.exe",
        "-m",
        "pytest",
    ]


@pytest.mark.parametrize("bad", ["", "   ", "[]", '["a", '])
def test_to_argv_rejects_unusable_commands(bad):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _to_argv(bad)


def test_unparseable_command_fails_closed(tmp_path):
    storage = _storage(tmp_path)
    flow = _flow(
        {
            "type": "command_gate",
            "command": '["unterminated", ',
            "command_key": "build",
            "on_fail": "BUILD_FAILURES.md",
        }
    )

    assert run_gates(flow, "A", "B", storage, "cmd-feature", 1) is not None
    assert "could not be parsed" in _feedback(storage, "BUILD_FAILURES.md")


# ── Output clipping keeps both ends ───────────────────────────────────────────


def test_clip_keeps_short_output_verbatim():
    assert _clip("  short output\n") == "short output"


def test_clip_keeps_head_and_tail_of_long_output():
    body = "HEAD" + ("x" * 20000) + "TAIL"
    clipped = _clip(body)

    assert clipped.startswith("HEAD")  # compiler errors live at the top
    assert clipped.endswith("TAIL")  # test summaries live at the bottom
    assert "characters elided" in clipped
    assert len(clipped) < len(body)
