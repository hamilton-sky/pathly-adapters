"""Adapters side of the feedback protocol contract.

Verifies that every feedback filename referenced in skill/agent Markdown files
is declared in protocol_contract.yaml, and that every contract name appears
in at least one Markdown file.

When pathly-engine and pathly-adapters live in separate repos, each repo
tests its own half of the contract against its own copy of protocol_contract.yaml.
If the two YAML files drift apart, the tests in the OTHER repo will catch it.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parent.parent
_CONTRACT_PATH = _REPO_ROOT / "protocol_contract.yaml"

CONTRACT = yaml.safe_load(_CONTRACT_PATH.read_text(encoding="utf-8"))
CONTRACT_FILES: set[str] = set(CONTRACT["feedback_files"])

# Derive allowed suffixes from the contract (e.g. _FEEDBACK.md, _QUESTIONS.md, _FAILURES.md).
# This means the filter automatically widens when new feedback file types are added.
_LAST_SEGMENT = re.compile(r'(_[A-Z]+\.md)$')
_CONTRACT_SUFFIXES: frozenset[str] = frozenset(
    m.group(1)
    for name in CONTRACT_FILES
    for m in [_LAST_SEGMENT.search(name)]
    if m
)

_UPPER_MD = re.compile(r'\b([A-Z][A-Z0-9_]+\.md)\b')


def _feedback_names_in_docs() -> set[str]:
    """Return all feedback-style UPPER_CASE.md names found in skill/agent Markdown files."""
    skill_dir = _REPO_ROOT / "pathly_data" / "core" / "skills"
    agent_dir = _REPO_ROOT / "pathly_data" / "core" / "agents"
    adapters_dir = _REPO_ROOT / "pathly_data" / "adapters"

    found: set[str] = set()
    for search_dir in (skill_dir, agent_dir, adapters_dir):
        for md_file in search_dir.glob("**/*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            found |= set(_UPPER_MD.findall(text))

    # Keep only names whose suffix matches a known contract pattern
    # (avoids false positives from README.md, PROGRESS.md, etc.)
    return {name for name in found if any(name.endswith(sfx) for sfx in _CONTRACT_SUFFIXES)}


class TestFeedbackProtocolAdapters:
    def test_contract_names_appear_in_docs(self):
        """Every name in protocol_contract.yaml must be mentioned in at least one skill/agent file."""
        in_docs = _feedback_names_in_docs()
        missing = CONTRACT_FILES - in_docs
        assert not missing, (
            "These contract names are NOT mentioned in any skill/agent Markdown file.\n"
            "Update the docs or remove from protocol_contract.yaml:\n"
            + "\n".join(f"  - {n}" for n in sorted(missing))
        )

    def test_no_undeclared_feedback_names_in_docs(self):
        """Every feedback filename in docs must be declared in protocol_contract.yaml."""
        in_docs = _feedback_names_in_docs()
        undeclared = in_docs - CONTRACT_FILES
        assert not undeclared, (
            "These feedback filenames appear in Markdown docs but are NOT in protocol_contract.yaml.\n"
            "Add to contract or fix the typo:\n"
            + "\n".join(f"  + {n}" for n in sorted(undeclared))
        )

    def test_contract_file_is_valid_yaml(self):
        """protocol_contract.yaml must parse and contain a feedback_files list."""
        assert isinstance(CONTRACT_FILES, set) and len(CONTRACT_FILES) > 0, (
            "protocol_contract.yaml parsed but 'feedback_files' is empty or missing"
        )
