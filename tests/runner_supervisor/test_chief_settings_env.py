"""chief-agent 20, B1: the chief's claude starts without background-task and scheduled-task prompts.

Measured on claude 2.1.304: ``CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`` stops the
``<task-notification>`` prompts and ``CLAUDE_CODE_DISABLE_CRON=1`` stops the scheduler that fires a
task of ``.claude/scheduled_tasks.json`` as a bare prompt (which the hook then records as
``human``). A permission rule does neither, so the settings the session writes carry both as an
``env`` block. A codex chief has no settings file and is unchanged.
"""

from __future__ import annotations

import json

from chief_open_support import (
    Host,
    _no_watcher_outlives_its_test,
    chief_root,
    open_with,
    project,
)

from pathly_orchestrator.runner.chief_argv import chief_argv, claude_settings

SWITCHES = {
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
    "CLAUDE_CODE_DISABLE_CRON": "1",
}


def test_the_claude_settings_hold_an_env_block_with_both_switches_set_to_1():
    settings = claude_settings("echo hook")

    assert settings["env"] == SWITCHES


def test_the_env_block_leaves_the_permissions_and_the_hook_as_they_were():
    settings = claude_settings("echo hook")

    assert set(settings) == {"permissions", "hooks", "env"}
    assert settings["permissions"]["allow"] == ["Bash(pathly *)"]
    assert "Bash(curl *)" in settings["permissions"]["deny"]
    assert settings["hooks"] == {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo hook"}]}]
    }


def test_the_settings_file_a_claude_chief_is_started_with_holds_the_env_block(
    project, chief_root
):
    host = Host()

    run_id = open_with(project, host)["run_id"]

    path = chief_root / run_id / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    assert settings["env"] == SWITCHES
    argv = host.sent[0][1]["argv"]
    assert argv[argv.index("--settings") + 1] == str(path)


def test_a_codex_chief_has_no_settings_file_and_no_env_in_its_argv(project, chief_root):
    host = Host()

    run_id = open_with(project, host, engine="codex", preset="status")["run_id"]

    assert sorted(p.name for p in (chief_root / run_id).iterdir()) == ["hook_secret"]
    argv = host.sent[0][1]["argv"]
    assert argv == chief_argv("codex", "", "s", "m", None)
    assert not [a for a in argv if "CLAUDE_CODE" in a]
