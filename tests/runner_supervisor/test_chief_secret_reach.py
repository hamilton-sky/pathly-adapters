"""chief-autopilot 02: the chief's settings give it no read path to ``~/.pathly``.

The session folder ``~/.pathly/chief/<run_id>/`` holds ``hook_secret``, which the
``UserPromptSubmit`` hook sends with each prompt it records as typed by the person. A chief that
read it could post a forged "human" message and cite it. So the settings deny ``Read``, ``Grep``
and ``Glob`` on ``~/.pathly/**`` (claude applies a ``Read`` rule to Grep, Glob and ``< file``
redirects best-effort; the explicit rules cost nothing) and set
``permissions.blockReadsOutsideWorkingDirectories``. There is no redirect deny rule: a
``Bash(pathly *<*)`` rule would deny ordinary bodies holding ``<``.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.runner.chief_argv import claude_settings


def _permissions() -> dict:
    return claude_settings("hook")["permissions"]


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob"])
def test_the_settings_deny_the_tool_on_the_pathly_home(tool):
    assert f"{tool}(~/.pathly/**)" in _permissions()["deny"]


def test_the_settings_block_reads_outside_the_working_directories():
    assert _permissions()["blockReadsOutsideWorkingDirectories"] is True


def test_no_deny_rule_names_an_input_redirect():
    assert not [rule for rule in _permissions()["deny"] if "<" in rule]


def test_pathly_commands_stay_allowed():
    assert _permissions()["allow"] == ["Bash(pathly *)"]
