"""chief-autopilot round two 18: the headless spawn host never hands on the chief's hook secret.

The chief's ``UserPromptSubmit`` hook reads ``PATHLY_CHIEF_HOOK_SECRET`` from the chief claude's
environment; Studio's main process claims it once from the server and puts it only there.
``pathly-pty-host`` refuses interactive spawns, so it never runs a chief and never claims one:
every child it starts gets an environment with no ``PATHLY_CHIEF_HOOK_SECRET``, even when the
host's own environment has one (the host inherited it, or a person exported it). The values here
are made up.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from pathly_orchestrator.pty_host.host import SpawnHost

FAKE_SECRET = "made-up-chief-secret-0123456789abcdef"


@pytest.fixture
def host_has_the_secret(monkeypatch):
    monkeypatch.setenv("PATHLY_CHIEF_HOOK_SECRET", FAKE_SECRET)


@pytest.mark.parametrize("run_token", [None, "", "tok-made-up"])
def test_the_child_env_has_no_chief_hook_secret(host_has_the_secret, tmp_path, run_token):
    env = SpawnHost._child_env(str(tmp_path), run_token)

    assert "PATHLY_CHIEF_HOOK_SECRET" not in env
    assert FAKE_SECRET not in env.values()


def test_the_child_env_keeps_the_rest(host_has_the_secret, monkeypatch, tmp_path):
    monkeypatch.setenv("SOME_OTHER_VAR", "kept")

    env = SpawnHost._child_env(str(tmp_path), "tok-made-up")

    assert env["SOME_OTHER_VAR"] == "kept"
    assert env["PATHLY_RUN_TOKEN"] == "tok-made-up"
    assert env["PATHLY_PROJECT_ROOT"] == str(tmp_path)
    assert env["PATHLY_GATE_BILLED"] == "1"


def test_the_hosts_own_environment_keeps_its_value(host_has_the_secret, tmp_path):
    SpawnHost._child_env(str(tmp_path))

    assert os.environ["PATHLY_CHIEF_HOOK_SECRET"] == FAKE_SECRET


def test_a_real_child_started_with_that_env_cannot_read_it(host_has_the_secret, tmp_path):
    env = SpawnHost._child_env(str(tmp_path))
    code = "import os; print(repr(os.environ.get('PATHLY_CHIEF_HOOK_SECRET')))"

    out = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    ).stdout

    assert out.strip() == "None"
