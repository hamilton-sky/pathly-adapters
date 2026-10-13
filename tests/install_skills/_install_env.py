"""Hermetic ``python -m install_cli`` runner shared by the install e2e tests.

HOME/USERPROFILE are redirected into ``tmp_path`` so ``~/.claude`` resolves inside the
temp dir and the developer's real install is never touched. No network calls.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from _paths import REPO_ROOT


def make_env(tmp_path: Path) -> dict[str, str]:
    """Return an os.environ copy with HOME/USERPROFILE redirected to tmp_path."""
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    env["APPDATA"] = str(tmp_path / "AppData" / "Roaming")
    env["LOCALAPPDATA"] = str(tmp_path / "AppData" / "Local")
    source_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = (
        source_path + os.pathsep + env["PYTHONPATH"]
        if env.get("PYTHONPATH")
        else source_path
    )
    return env


def run_install_cli(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    env = make_env(tmp_path)
    # Create ~/.claude so that detect_hosts() picks up the "claude" host
    # and so that expanduser("~") resolves to our temp directory.
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", "install_cli", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def installed_skill_dirs(tmp_path: Path) -> set[str]:
    """Names of the ``pathly*`` skill directories under the redirected ~/.claude/skills."""
    skills = tmp_path / ".claude" / "skills"
    if not skills.is_dir():
        return set()
    return {
        p.name for p in skills.iterdir() if p.is_dir() and p.name.startswith("pathly")
    }
