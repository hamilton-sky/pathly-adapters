"""chief-autopilot 02 and round two 15: the chief's settings give it no read path to the secret.

The ``UserPromptSubmit`` hook sends the session's hook secret with each prompt it records as typed
by the person; a chief that read it could post a forged "human" message and cite it. Round two
(ticket 15) took the secret out of every file: the server keeps it in memory and Studio puts it in
the chief claude's environment, ``PATHLY_CHIEF_HOOK_SECRET``, where the hook inherits it. So the
settings deny the chief the ways to print that environment: ``Bash(env*)``, ``Bash(printenv*)``
and ``Read``, ``Grep`` and ``Glob`` on ``/proc`` (``//proc/**``: a single leading slash anchors a
rule at the settings source, two at the filesystem root). They still deny ``Read``, ``Grep`` and
``Glob`` on ``~/.pathly/**`` (the database and the session folder) and set
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


@pytest.mark.parametrize("rule", ["Bash(env*)", "Bash(printenv*)", "Read(/proc/**)"])
def test_the_settings_deny_printing_the_chiefs_environment(rule):
    assert rule in _permissions()["deny"]


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob"])
def test_the_settings_deny_the_tool_on_the_real_proc(tool):
    assert f"{tool}(//proc/**)" in _permissions()["deny"]


def test_the_settings_block_reads_outside_the_working_directories():
    assert _permissions()["blockReadsOutsideWorkingDirectories"] is True


def test_no_deny_rule_names_an_input_redirect():
    assert not [rule for rule in _permissions()["deny"] if "<" in rule]


def test_pathly_commands_stay_allowed():
    assert _permissions()["allow"] == ["Bash(pathly *)"]
