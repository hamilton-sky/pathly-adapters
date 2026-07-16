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

from _paths import REPO_ROOT
CLASSIFY_HOOK = REPO_ROOT / "src" / "pathly_hooks" / "classify_feedback.py"
INJECT_HOOK = REPO_ROOT / "src" / "pathly_hooks" / "inject_feedback_ttl.py"

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
# test_hook_rejects_path_outside_workspace
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_rejects_path_outside_workspace(hook, tmp_path):
    plans_dir = tmp_path / "pathly" / "plans"
    plans_dir.mkdir(parents=True)

    evil_path = str(tmp_path / ".." / ".." / "etc" / "passwd")
    payload = {"file": evil_path}
    result = _run_hook(
        hook,
        payload,
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode != 0
    assert "pathly-hook: rejected path outside features/ or plans/:" in result.stderr


# ---------------------------------------------------------------------------
# test_hook_accepts_valid_path (legacy plans/ + flat features/)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_accepts_valid_path(hook, tmp_path):
    plans_dir = tmp_path / "pathly" / "plans"
    plans_dir.mkdir(parents=True)
    feedback_file = plans_dir / "feedback.md"
    feedback_file.write_text("# feedback\n", encoding="utf-8")

    payload = {"file": str(feedback_file)}
    result = _run_hook(
        hook,
        payload,
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0


@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_accepts_flat_features_feedback(hook, tmp_path):
    """Post-flatten, feedback lives at pathly/features/<name>/feedback/ — the hooks must
    accept it, not reject it as 'outside plans/'."""
    fb_dir = tmp_path / "pathly" / "features" / "my-feature" / "feedback"
    fb_dir.mkdir(parents=True)
    feedback_file = fb_dir / "REVIEW_FAILURES.md"
    feedback_file.write_text("# feedback\n", encoding="utf-8")

    result = _run_hook(
        hook,
        {"file": str(feedback_file)},
        env={"PATHLY_PROJECT_ROOT": str(tmp_path)},
    )
    assert result.returncode == 0, result.stderr


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
    plans_dir = tmp_path / "pathly" / "plans"
    plans_dir.mkdir(parents=True)
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
    plans_dir = tmp_path / "pathly" / "plans"
    plans_dir.mkdir(parents=True)
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
# test_classify_feedback_uses_word_boundary_arch_keywords
# ---------------------------------------------------------------------------


def test_classify_feedback_uses_word_boundary_arch_keywords(tmp_path):
    plans_dir = tmp_path / "pathly" / "plans"
    plans_dir.mkdir(parents=True)
    feedback_file = plans_dir / "IMPL_QUESTIONS.md"
    feedback_file.write_text(
        "- How long should the TTL be?\n"
        "- Which design should we use?\n"
        "- Is this a showstopper?\n",
        encoding="utf-8",
    )

    result = _run_hook(
        CLASSIFY_HOOK,
        {"file": str(feedback_file)},
        env={
            "PATHLY_PROJECT_ROOT": str(tmp_path),
            "ANTHROPIC_API_KEY": "test-key",
        },
    )

    assert result.returncode == 0
    assert feedback_file.read_text(encoding="utf-8") == (
        "- [REQ] How long should the TTL be?\n"
        "- [ARCH] Which design should we use?\n"
        "- [REQ] Is this a showstopper?\n"
    )


# ---------------------------------------------------------------------------
# test_classify_feedback_five_way_split (smart-fix-routing)
# ---------------------------------------------------------------------------


def test_classify_feedback_five_way_split(tmp_path):
    """Each keyword family maps to its tag; an untagged bullet in a FAILURE file
    defaults to [IMPL] (risk #3 scoping — today's default was [REQ])."""
    fb_dir = tmp_path / "pathly" / "features" / "my-feature" / "feedback"
    fb_dir.mkdir(parents=True)
    feedback_file = fb_dir / "REVIEW_FAILURES.md"
    feedback_file.write_text(
        "- Missing acceptance criteria for the login flow requirement.\n"
        "- The phase sequencing in the plan needs to change.\n"
        "- The module violates the intended architecture structure.\n"
        "- The button layout and component style are wrong.\n"
        "- Off-by-one error in the loop counter.\n",
        encoding="utf-8",
    )

    result = _run_hook(
        CLASSIFY_HOOK,
        {"file": str(feedback_file)},
        env={
            "PATHLY_PROJECT_ROOT": str(tmp_path),
            "ANTHROPIC_API_KEY": "test-key",
        },
    )

    assert result.returncode == 0, result.stderr
    assert feedback_file.read_text(encoding="utf-8") == (
        "- [REQ] Missing acceptance criteria for the login flow requirement.\n"
        "- [PLAN] The phase sequencing in the plan needs to change.\n"
        "- [ARCH] The module violates the intended architecture structure.\n"
        "- [DESIGN] The button layout and component style are wrong.\n"
        "- [IMPL] Off-by-one error in the loop counter.\n"
    )


# ---------------------------------------------------------------------------
# test_classify_feedback_default_scoped_by_file_family
# ---------------------------------------------------------------------------


def test_classify_feedback_default_scoped_by_file_family(tmp_path):
    """Risk #3: FAILURE files (REVIEW_FAILURES/TEST_FAILURES) default an untagged
    bullet to [IMPL]; a QUESTION file (e.g. ARCH_FEEDBACK.md) keeps the [REQ] default."""
    fb_dir = tmp_path / "pathly" / "features" / "my-feature" / "feedback"
    fb_dir.mkdir(parents=True)

    for filename, expected_tag in (
        ("REVIEW_FAILURES.md", "IMPL"),
        ("TEST_FAILURES.md", "IMPL"),
        ("ARCH_FEEDBACK.md", "REQ"),
    ):
        feedback_file = fb_dir / filename
        feedback_file.write_text("- Something went wrong.\n", encoding="utf-8")

        result = _run_hook(
            CLASSIFY_HOOK,
            {"file": str(feedback_file)},
            env={
                "PATHLY_PROJECT_ROOT": str(tmp_path),
                "ANTHROPIC_API_KEY": "test-key",
            },
        )

        assert result.returncode == 0, result.stderr
        assert (
            feedback_file.read_text(encoding="utf-8")
            == f"- [{expected_tag}] Something went wrong.\n"
        ), f"{filename} default tag"


# ---------------------------------------------------------------------------
# test_classify_feedback_already_tagged_lines_untouched
# ---------------------------------------------------------------------------


def test_classify_feedback_already_tagged_lines_untouched(tmp_path):
    """A bullet already tagged with any of the 5 tags is left byte-identical
    (idempotent) — only a genuinely new bullet gets classified."""
    fb_dir = tmp_path / "pathly" / "features" / "my-feature" / "feedback"
    fb_dir.mkdir(parents=True)
    feedback_file = fb_dir / "REVIEW_FAILURES.md"
    feedback_file.write_text(
        "- [REQ] Already tagged requirement note.\n"
        "- [PLAN] Already tagged plan note.\n"
        "- [ARCH] Already tagged architecture note.\n"
        "- [DESIGN] Already tagged design note.\n"
        "- [IMPL] Already tagged impl note.\n"
        "- A brand-new untagged bullet.\n",
        encoding="utf-8",
    )

    result = _run_hook(
        CLASSIFY_HOOK,
        {"file": str(feedback_file)},
        env={
            "PATHLY_PROJECT_ROOT": str(tmp_path),
            "ANTHROPIC_API_KEY": "test-key",
        },
    )

    assert result.returncode == 0, result.stderr
    assert feedback_file.read_text(encoding="utf-8") == (
        "- [REQ] Already tagged requirement note.\n"
        "- [PLAN] Already tagged plan note.\n"
        "- [ARCH] Already tagged architecture note.\n"
        "- [DESIGN] Already tagged design note.\n"
        "- [IMPL] Already tagged impl note.\n"
        "- [IMPL] A brand-new untagged bullet.\n"
    )


# ---------------------------------------------------------------------------
# test_hook_missing_project_root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hook", HOOKS, ids=["classify", "inject_ttl"])
def test_hook_missing_project_root(hook, tmp_path):
    payload = {"file": str(tmp_path / "pathly" / "plans" / "feedback.md")}

    base_env = {k: v for k, v in os.environ.items()}
    base_env.pop("PATHLY_PROJECT_ROOT", None)
    base_env.pop("ANTHROPIC_API_KEY", None)
    base_env["HOME"] = str(tmp_path)
    base_env["USERPROFILE"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=base_env,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert "PATHLY_PROJECT_ROOT not set" in (
        tmp_path / ".pathly" / "hook.log"
    ).read_text(encoding="utf-8")
