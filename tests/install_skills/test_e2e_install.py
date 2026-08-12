"""End-to-end tests for the install_cli install/uninstall flow via subprocess.

All file I/O uses tmp_path. The real HOME/USERPROFILE env vars are redirected
so that expanduser() resolves into the temp directory. No network calls.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from _paths import REPO_ROOT


def _make_env(tmp_path: Path) -> dict[str, str]:
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


def _run_install_cli(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    env = _make_env(tmp_path)
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


# ---------------------------------------------------------------------------
# test_dry_run_exits_0
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_dry_run_exits_0(tmp_path):
    result = _run_install_cli(["claude", "--dry-run"], tmp_path)
    assert (
        result.returncode == 0
    ), f"Expected exit 0 for dry-run.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    # The CLI prints "[claude] Would write to <dest>:" during dry-run
    assert "[claude]" in result.stdout
    assert "Would write" in result.stdout


# ---------------------------------------------------------------------------
# test_apply_creates_expected_files
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_apply_creates_expected_files(tmp_path):
    # --all-skills so the Tier-2 pathly-fix skill installs (fsm-call assertion below).
    result = _run_install_cli(["claude", "--apply", "--all-skills"], tmp_path)
    assert (
        result.returncode == 0
    ), f"Expected exit 0 for apply.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    # The manifest must exist in the agents destination (~/.claude/agents/)
    agents_dest = tmp_path / ".claude" / "agents"
    manifest = agents_dest / ".pathly-manifest.json"
    assert manifest.exists(), (
        f"Expected manifest at {manifest} after apply.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    # At least one file must have been written (agents may be nested in subdirs)
    all_files = [
        f
        for f in agents_dest.rglob("*")
        if f.is_file() and f.name != ".pathly-manifest.json"
    ]
    assert all_files, (
        f"Expected at least one file under {agents_dest} after apply.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    orchestrator = (agents_dest / "orchestrator.md").read_text(encoding="utf-8")
    fix_skill = (tmp_path / ".claude" / "skills" / "pathly-fix" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "pathly_orchestrator.http_server" in orchestrator
    assert "fsm-call" in fix_skill


# ---------------------------------------------------------------------------
# skill tiers — default install set vs --export vs --all-skills
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_apply_installs_only_tier1_by_default(tmp_path):
    result = _run_install_cli(["claude", "--apply"], tmp_path)
    assert result.returncode == 0, result.stderr
    skills = tmp_path / ".claude" / "skills"
    # Tier-1: the two board on-ramps + dispatcher/help are always exposed.
    for s in ("pathly-create-feature", "pathly-post", "pathly", "pathly-help"):
        assert (skills / s / "SKILL.md").exists(), f"{s} should install by default"
    # Tier-2 pipeline skills are export-only — absent from a default apply.
    for s in ("pathly-build", "pathly-goalize", "pathly-review"):
        assert not (skills / s).exists(), f"{s} should be export-only, not default"


@pytest.mark.slow
def test_export_installs_named_skill_plus_defaults(tmp_path):
    result = _run_install_cli(["claude", "--export", "build"], tmp_path)
    assert result.returncode == 0, result.stderr
    skills = tmp_path / ".claude" / "skills"
    assert (skills / "pathly-build" / "SKILL.md").exists()  # requested
    assert (skills / "pathly-post" / "SKILL.md").exists()  # default set still installed
    assert not (skills / "pathly-review").exists()  # not requested


@pytest.mark.slow
def test_all_skills_installs_everything(tmp_path):
    result = _run_install_cli(["claude", "--apply", "--all-skills"], tmp_path)
    assert result.returncode == 0, result.stderr
    skills = tmp_path / ".claude" / "skills"
    for s in ("pathly-build", "pathly-review", "pathly-goalize", "pathly-post"):
        assert (
            skills / s / "SKILL.md"
        ).exists(), f"{s} should install with --all-skills"


# ---------------------------------------------------------------------------
# test_apply_then_uninstall_cleans_up
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_apply_then_uninstall_cleans_up(tmp_path):
    apply_result = _run_install_cli(["claude", "--apply"], tmp_path)
    assert (
        apply_result.returncode == 0
    ), f"Apply failed.\nstdout:\n{apply_result.stdout}\nstderr:\n{apply_result.stderr}"

    agents_dest = tmp_path / ".claude" / "agents"
    assert (
        agents_dest / ".pathly-manifest.json"
    ).exists(), "Manifest should exist after apply"

    uninstall_result = _run_install_cli(["claude", "--uninstall"], tmp_path)
    assert (
        uninstall_result.returncode == 0
    ), f"Uninstall failed.\nstdout:\n{uninstall_result.stdout}\nstderr:\n{uninstall_result.stderr}"

    # After uninstall the manifest should be gone
    assert not (
        agents_dest / ".pathly-manifest.json"
    ).exists(), "Manifest should be removed after uninstall"

    # All tracked files should be gone (agents may be nested in subdirs)
    remaining = [f for f in agents_dest.rglob("*") if f.is_file()]
    assert (
        not remaining
    ), f"Expected no files after uninstall, found: {[str(f.relative_to(agents_dest)) for f in remaining]}"


# ---------------------------------------------------------------------------
# test_dry_run_does_not_write_files
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_dry_run_does_not_write_files(tmp_path):
    # Pre-create the .claude sentinel dir (needed for detect_hosts); record its
    # initial contents before the dry-run so we can compare after.
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    before = set(tmp_path.rglob("*"))

    result = _run_install_cli(["claude", "--dry-run"], tmp_path)
    assert (
        result.returncode == 0
    ), f"Dry-run exited non-zero.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    after = set(tmp_path.rglob("*"))
    new_paths = after - before
    assert (
        not new_paths
    ), f"Dry-run wrote unexpected files: {[str(p) for p in sorted(new_paths)]}"


# ---------------------------------------------------------------------------
# test_invalid_host_exits_nonzero
# ---------------------------------------------------------------------------


def test_invalid_host_exits_nonzero(tmp_path):
    result = _run_install_cli(["nonexistent_host_xyz", "--apply"], tmp_path)
    assert (
        result.returncode != 0
    ), f"Expected non-zero exit for invalid host.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "nonexistent_host_xyz" in result.stderr or "unsupported" in result.stderr


# ---------------------------------------------------------------------------
# test_antigravity_dry_run_exits_0
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_antigravity_dry_run_exits_0(tmp_path):
    (tmp_path / ".gemini" / "antigravity-cli").mkdir(parents=True)
    result = _run_install_cli(["antigravity", "--dry-run"], tmp_path)
    assert (
        result.returncode == 0
    ), f"Expected exit 0 for antigravity dry-run.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "[antigravity]" in result.stdout
    assert "Would write" in result.stdout
