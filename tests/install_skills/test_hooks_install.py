"""Stop-hook install: a command that runs, and a repair that keeps the user's hook order.

The installer used to write `python -m pathly_hooks.stop_telemetry`: on a machine with only
python3 (or the package in a venv/pipx env) that fails at every session end with exit 127.
It now writes the interpreter running the installer. A repair also used to drop every
Pathly entry and append a fresh one, re-ordering the user's hooks on each run.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys

import pytest

from _install_env import make_env, run_install_cli
from _paths import REPO_ROOT
from install_cli import hooks
from install_cli.hooks import _apply_hooks, expand_command

CMD = "{python} -m pathly_hooks.stop_telemetry"


def _cfg(path, *commands):
    return {"settings_dest": str(path), "Stop": list(commands) or [CMD]}


def _hook(command, **group_keys):
    return {**group_keys, "hooks": [{"type": "command", "command": command}]}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _stop_commands(settings):
    return [h["command"] for g in settings["hooks"]["Stop"] for h in g["hooks"]]


@pytest.fixture()
def settings(tmp_path):
    return tmp_path / ".claude" / "settings.json"


def _seed(path, stop, **other_events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"theme": "dark", "hooks": {"Stop": stop, **other_events}})
    )


# ── {python} expansion ─────────────────────────────────────────────────────


def test_expand_command_leaves_plain_commands_alone():
    assert expand_command("some-tool --flag") == "some-tool --flag"


def test_expand_command_uses_the_running_interpreter(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/venvs/pathly/bin/python")
    assert (
        expand_command(CMD) == "/venvs/pathly/bin/python -m pathly_hooks.stop_telemetry"
    )


@pytest.mark.skipif(os.name == "nt", reason="posix shell quoting")
def test_expand_command_quotes_an_interpreter_path_with_spaces(monkeypatch):
    monkeypatch.setattr(sys, "executable", "/opt/my tools/bin/python")
    cmd = expand_command(CMD)
    assert shlex.split(cmd) == [
        "/opt/my tools/bin/python",
        "-m",
        "pathly_hooks.stop_telemetry",
    ]


def test_expand_command_falls_back_when_there_is_no_interpreter_path(monkeypatch):
    monkeypatch.setattr(sys, "executable", "")
    assert expand_command(CMD).startswith("python3 -m ")


def test_the_installed_hook_has_no_unexpanded_placeholder(settings):
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=False)
    (cmd,) = _stop_commands(_read(settings))
    assert "{python}" not in cmd and cmd.endswith("-m pathly_hooks.stop_telemetry")
    assert shlex.split(cmd)[0] == sys.executable


# ── repair keeps order, is idempotent, preserves the user's file ───────────


def test_repair_replaces_the_pathly_hook_in_place(settings):
    _seed(
        settings,
        [
            _hook("first-tool"),
            _hook("python -m pathly_hooks.stop_telemetry"),  # the broken old command
            _hook("last-tool"),
        ],
    )
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=True)

    cmds = _stop_commands(_read(settings))
    assert cmds[0] == "first-tool" and cmds[2] == "last-tool"  # order kept
    assert cmds[1] == expand_command(CMD)  # fixed where it was, not moved to the end


def test_repair_collapses_duplicate_pathly_groups_into_the_first_slot(settings):
    _seed(
        settings,
        [
            _hook("python -m pathly_hooks.a"),
            _hook("other"),
            _hook("python -m pathly_hooks.b"),
        ],
    )
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=True)
    assert _stop_commands(_read(settings)) == [expand_command(CMD), "other"]


def test_repair_keeps_a_users_own_hook_that_shares_a_group_with_pathlys(settings):
    _seed(
        settings,
        [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python -m pathly_hooks.stop_telemetry",
                    },
                    {"type": "command", "command": "my-own-cleanup"},
                ],
            }
        ],
    )
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=True)

    groups = _read(settings)["hooks"]["Stop"]
    assert groups[0] == _hook(expand_command(CMD))
    assert groups[1] == {
        "matcher": "*",
        "hooks": [{"type": "command", "command": "my-own-cleanup"}],
    }


def test_repair_leaves_other_events_and_settings_alone(settings):
    _seed(
        settings,
        [_hook("python -m pathly_hooks.stop_telemetry")],
        PreToolUse=[_hook("guard")],
    )
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=True)
    data = _read(settings)
    assert data["theme"] == "dark"
    assert data["hooks"]["PreToolUse"] == [_hook("guard")]


def test_a_repair_that_changes_nothing_writes_nothing(settings, capsys):
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=False)
    capsys.readouterr()
    before, mtime = settings.read_bytes(), settings.stat().st_mtime_ns

    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=True)

    assert settings.read_bytes() == before and settings.stat().st_mtime_ns == mtime
    assert "Updated hooks" not in capsys.readouterr().out


def test_without_repair_a_broken_pathly_hook_is_left_for_repair_to_fix(settings):
    broken = "python -m pathly_hooks.stop_telemetry"
    _seed(settings, [_hook(broken)])
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=False)
    assert _stop_commands(_read(settings)) == [broken]
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=True)
    assert _stop_commands(_read(settings)) == [expand_command(CMD)]


def test_non_ascii_settings_are_not_escaped_on_rewrite(settings):
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"note": "café"}, ensure_ascii=False), encoding="utf-8"
    )
    _apply_hooks("claude", _cfg(settings), dry_run=False, repair=False)
    assert "café" in settings.read_text(encoding="utf-8")


def test_dry_run_reports_but_does_not_write(settings, capsys):
    _apply_hooks("claude", _cfg(settings), dry_run=True, repair=False)
    assert not settings.exists()
    assert "Would update hooks" in capsys.readouterr().out


def test_orchestrate_still_exposes_apply_hooks():
    from install_cli import orchestrate

    assert orchestrate._apply_hooks is hooks._apply_hooks


# ── end to end: the command the installer writes actually runs ─────────────


@pytest.mark.slow
@pytest.mark.skipif(os.name == "nt", reason="exercises /bin/sh")
def test_the_installed_stop_hook_runs_with_no_python_on_path(tmp_path):
    """The reported failure: `python: command not found` (exit 127) at every session end."""
    assert run_install_cli(["claude", "--apply"], tmp_path).returncode == 0
    (cmd,) = _stop_commands(_read(tmp_path / ".claude" / "settings.json"))

    env = make_env(tmp_path)
    env["PATH"] = (
        "/nonexistent"  # no `python`, no `python3` — only an absolute path can work
    )
    ran = subprocess.run(
        ["/bin/sh", "-c", cmd],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert ran.returncode == 0, ran.stderr

    old = subprocess.run(
        ["/bin/sh", "-c", "python -m pathly_hooks.stop_telemetry"],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert old.returncode == 127  # the command this replaces cannot run there


@pytest.mark.slow
def test_apply_repair_twice_does_not_touch_settings_the_second_time(tmp_path):
    assert run_install_cli(["claude", "--apply", "--repair"], tmp_path).returncode == 0
    settings = tmp_path / ".claude" / "settings.json"
    before, mtime = settings.read_bytes(), settings.stat().st_mtime_ns

    r = run_install_cli(["claude", "--apply", "--repair"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert settings.read_bytes() == before and settings.stat().st_mtime_ns == mtime
    assert "Updated hooks" not in r.stdout
