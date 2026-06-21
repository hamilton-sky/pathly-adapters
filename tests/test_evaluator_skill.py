"""Tests for the evaluator agent + skill (BLOCK E1 — comms-board).

Verifies:
- planning/evaluate composes successfully under the claude adapter.
- The composed output contains the comms-post board-posting section.
- The core agent file exists and is parseable (has expected front-matter and sections).
"""

from pathlib import Path

import pytest

from pathly_orchestrator.compose import compose_skill, validate_composition

# Marker from fragments/comms-post.md — proves the fragment was composed in.
_COMMS_POST_MARKER = "Posting to the Comms Board"

# Root of the core data package
_CORE_ROOT = Path(__file__).parent.parent / "src" / "pathly_data" / "core"


# ── Composition ──────────────────────────────────────────────────────────────


def test_evaluate_skill_composes():
    """planning/evaluate must compose without raising."""
    out = compose_skill("planning/evaluate", "claude")
    assert isinstance(out, str) and len(out) > 0


def test_evaluate_skill_contains_comms_post_section():
    """The composed output must include the comms-post board-posting content."""
    out = compose_skill("planning/evaluate", "claude")
    assert _COMMS_POST_MARKER in out, (
        f"Expected {_COMMS_POST_MARKER!r} in composed planning/evaluate output but it was absent.\n"
        f"Output snippet: {out[:300]!r}"
    )


def test_evaluate_skill_composes_for_codex():
    """planning/evaluate must also compose for the codex adapter without raising."""
    out = compose_skill("planning/evaluate", "codex")
    assert _COMMS_POST_MARKER in out


def test_evaluate_manifest_validates():
    """The real manifest must still pass validation after the planning/evaluate entry is added."""
    validate_composition()


# ── Agent contract file ───────────────────────────────────────────────────────

_AGENT_FILE = _CORE_ROOT / "agents" / "research" / "evaluator.md"


def test_evaluator_agent_file_exists():
    """The core agent contract file must exist at the expected path."""
    assert _AGENT_FILE.exists(), f"Missing agent file: {_AGENT_FILE}"


def test_evaluator_agent_has_frontmatter():
    """The agent file must open with a YAML front-matter block (--- ... ---)."""
    text = _AGENT_FILE.read_text(encoding="utf-8")
    assert text.startswith(
        "---"
    ), "evaluator.md must start with YAML front-matter (---)"
    # The closing --- must also be present
    lines = text.splitlines()
    closing = [i for i, l in enumerate(lines) if l.strip() == "---" and i > 0]
    assert closing, "evaluator.md front-matter is not closed with a second ---"


def test_evaluator_agent_has_name_in_frontmatter():
    """The front-matter must declare a 'name:' field."""
    text = _AGENT_FILE.read_text(encoding="utf-8")
    # Extract front-matter block
    parts = text.split("---", 2)
    assert len(parts) >= 3, "evaluator.md does not have a parseable front-matter block"
    fm = parts[1]
    assert "name:" in fm, "evaluator.md front-matter is missing 'name:' field"


def test_evaluator_agent_has_expected_sections():
    """The agent contract must have the key H2 sections expected by the evaluator workflow."""
    text = _AGENT_FILE.read_text(encoding="utf-8")
    for section in ("## Input", "## Step 1", "## Step 3", "## Hard constraints"):
        assert section in text, f"evaluator.md is missing section {section!r}"


def test_evaluator_agent_is_host_neutral():
    """The agent contract must not reference host-specific tool names."""
    text = _AGENT_FILE.read_text(encoding="utf-8")
    host_specific = ["<tool_call>", "use_mcp_tool", "@claude", "claude.ai"]
    for marker in host_specific:
        assert (
            marker not in text
        ), f"evaluator.md references host-specific marker {marker!r} — keep it host-neutral"
