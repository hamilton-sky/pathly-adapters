"""End-to-end tests for hook scripts via subprocess.

All file I/O uses tmp_path. No network calls. No real API key required.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CLASSIFY_HOOK = REPO_ROOT / "hooks" / "classify_feedback.py"
INJECT_HOOK = REPO_ROOT / "hooks" / "inject_feedback_ttl.py"

HOOKS = [CLASSIFY_HOOK, INJECT_HOOK]


def _run_hook(
    hook: Path,
    payload: object,
    *,
    env: dict | None = None,
    raw_stdin: str | None = None,
) -> subprocess.CompletedProcess:
    stdin_text = raw_stdin if raw_stdin is not None else json.dumps(payload)
    base_env = {k: v for k, v in os.environ.items()}
    base_env.pop("ANTHROPIC_API_KEY", None)
    if env is not None:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(hook)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=base_env,
    )


# ---------------------------------------------------------------------------
# test_hook_rejects_path_outside_plans
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_rejects_path_outside_plans(hook, tmp_path):
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()

    evil_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
    payload = {"file": evil_path}
    result = _run_hook(
        hook,
        payload,
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode != 0
    assert "pathly-hook: rejected path outside plans/:" in result.stderr


# ---------------------------------------------------------------------------
# test_hook_accepts_valid_path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_accepts_valid_path(hook, tmp_path):
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    feedback_file = plans_dir / "feedback.md"
    feedback_file.write_text("# feedback\n", encoding="utf-8")

    payload = {"file": str(feedback_file)}
    result = _run_hook(
        hook,
        payload,
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# test_hook_malformed_json
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_malformed_json(hook, tmp_path):
    result = _run_hook(
        hook,
        None,
        raw_stdin="not json",
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# test_hook_already_tagged_file  (inject_feedback_ttl only)
# ---------------------------------------------------------------------------

def test_hook_already_tagged_file(tmp_path):
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    feedback_file = plans_dir / "feedback.md"
    original_content = "---\nttl_hours: 48\n---\n# feedback\n"
    feedback_file.write_text(original_content, encoding="utf-8")

    payload = {"file": str(feedback_file)}
    result = _run_hook(
        INJECT_HOOK,
        payload,
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0
    assert feedback_file.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# test_hook_missing_api_key  (classify_feedback only)
# ---------------------------------------------------------------------------

def test_hook_missing_api_key(tmp_path):
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    feedback_file = plans_dir / "IMPL_QUESTIONS.md"
    feedback_file.write_text("- Is this a requirement?\n", encoding="utf-8")

    env = {
        "PATHLY_PROJECT_ROOT": str(tmp_path),
    }
    result = _run_hook(
        CLASSIFY_HOOK,
        {"file": str(feedback_file)},
        env=env,
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# test_hook_missing_project_root
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_missing_project_root(hook, tmp_path):
    payload = {"file": str(tmp_path / "plans" / "feedback.md")}

    base_env = {k: v for k, v in os.environ.items()}
    base_env.pop("PATHLY_PROJECT_ROOT", None)
    base_env.pop("ANTHROPIC_API_KEY", None)

    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert result.returncode != 0
    assert "pathly-hook: PATHLY_PROJECT_ROOT not set" in result.stderr
