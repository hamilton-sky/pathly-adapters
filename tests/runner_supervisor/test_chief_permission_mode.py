"""chief-autopilot 01: a claude chief starts in ``dontAsk`` permission mode, never auto mode.

Spike 19 part B, question 1: claude 2.1.310 started the chief in auto mode despite
``--restricted`` (auto mode is claude's starting mode for interactive sessions from v2.1.283),
and auto mode ran ``python3`` without asking. ``--permission-mode dontAsk`` denies every call that
would otherwise prompt, so the chief runs only ``pathly`` commands, claude's read-only commands and
Read, Glob and Grep inside its project. A codex chief's argv is unchanged.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.runner.chief_argv import chief_argv

FORBIDDEN = {"auto", "bypassPermissions", "--dangerously-skip-permissions"}


def _claude(model: str = "") -> list[str]:
    return chief_argv("claude", model, "/s/settings.json", "/s/mcp.json", "sess-1")


@pytest.mark.parametrize("model", ["", "opus"])
def test_the_claude_argv_carries_permission_mode_dontask_exactly_once(model):
    argv = _claude(model)

    assert argv.count("--permission-mode") == 1
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv.count("dontAsk") == 1


def test_the_permission_mode_comes_before_settings():
    argv = _claude()

    assert argv.index("--permission-mode") < argv.index("--settings")


def test_the_argv_names_the_module_constant():
    from pathly_orchestrator.runner.chief_argv import CLAUDE_PERMISSION_MODE

    assert CLAUDE_PERMISSION_MODE == "dontAsk"
    assert CLAUDE_PERMISSION_MODE in _claude()


@pytest.mark.parametrize("model", ["", "gpt-5"])
def test_the_codex_argv_carries_no_permission_mode(model):
    argv = chief_argv("codex", model, "s", "m", None)

    assert "--permission-mode" not in argv
    assert "dontAsk" not in argv


@pytest.mark.parametrize(
    "argv",
    [
        chief_argv("claude", "", "s", "m", "x"),
        chief_argv("claude", "opus", "s", "m", "x"),
        chief_argv("codex", "", "s", "m", None),
        chief_argv("codex", "gpt-5", "s", "m", None),
    ],
    ids=["claude", "claude-model", "codex", "codex-model"],
)
def test_no_chief_argv_carries_auto_or_a_bypass(argv):
    assert not FORBIDDEN & set(argv)
