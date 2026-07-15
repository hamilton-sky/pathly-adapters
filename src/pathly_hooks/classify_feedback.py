"""Hook: classify feedback bullets by root cause into one of five tags.

Receives a JSON payload on stdin with a "file" or "path" key.
Validates the path stays inside the project's feature workspace (pathly/features/ or
legacy pathly/plans/).
If ANTHROPIC_API_KEY is not set, exits silently (classification is optional).

Tag -> feedback file -> responsible role (mirrors flow feedback_routing / smart-fix-routing
DESIGN.md ss1.2):
    [REQ]    REQUIREMENT_GAP.md              -> po        (USER_STORIES.md)
    [PLAN]   PLAN_FEEDBACK.md                -> planner   (IMPLEMENTATION_PLAN.md)
    [ARCH]   ARCH_FEEDBACK.md                -> architect (ARCHITECTURE_PROPOSAL.md)
    [DESIGN] DESIGN_FEEDBACK.md              -> designer  (DESIGN.md)
    [IMPL]   REVIEW_FAILURES.md/TEST_FAILURES.md -> builder (source code)

Precedence when a bullet matches multiple keyword families: REQ > PLAN > ARCH > DESIGN.
The default when none match is scoped by file family (risk #3 in DESIGN.md): a FAILURE
file (REVIEW_FAILURES.md, TEST_FAILURES.md — a reviewer/tester bug report) defaults to
[IMPL]; any other (question/clarification) file keeps the original [REQ] default.

This hook only TAGS bullets in place — it does not move them between files or route
them; routing is the FSM's job (route_feedback in fsm/engine_transitions.py), keyed by
the filename, not the tag.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_REQ_QUESTION = re.compile(
    r"\b(requirement|scope|acceptance|user story)\b",
    re.IGNORECASE,
)

_PLAN_QUESTION = re.compile(
    r"\b(plan|phase|task|sequence|dependency)\b",
    re.IGNORECASE,
)

_ARCH_QUESTION = re.compile(
    r"\b(architect|architecture|architectural|design|approach|structure)\b",
    re.IGNORECASE,
)

_DESIGN_QUESTION = re.compile(
    r"\b(ui|ux|layout|component|visual|style)\b",
    re.IGNORECASE,
)

# Precedence order: REQ -> PLAN -> ARCH -> DESIGN. The first family that matches wins.
_TAG_ORDER = ("REQ", "PLAN", "ARCH", "DESIGN")
_PATTERNS = {
    "REQ": _REQ_QUESTION,
    "PLAN": _PLAN_QUESTION,
    "ARCH": _ARCH_QUESTION,
    "DESIGN": _DESIGN_QUESTION,
}

# All five tags this hook recognizes — used for the idempotency (already-tagged) check.
_ALL_TAGS = (*_TAG_ORDER, "IMPL")

# Failure (bug-report) files default to [IMPL]; every other feedback file (a clarification
# / question file) keeps the pre-existing [REQ] default.
_FAILURE_FILE_STEMS = {"REVIEW_FAILURES", "TEST_FAILURES"}


def _log_skip(message: str) -> None:
    log_path = Path.home() / ".pathly" / "hook.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"classify_feedback: {message}\n")
    except OSError:
        pass


def _classify(question_text: str) -> str | None:
    """Classify one bullet by keyword-family precedence. None if no family matches."""
    for tag in _TAG_ORDER:
        if _PATTERNS[tag].search(question_text):
            return tag
    return None


def _default_tag(filename: str) -> str:
    """Default tag when no keyword family matches (risk #3, DESIGN.md)."""
    stem = filename[:-3] if filename.endswith(".md") else filename
    return "IMPL" if stem in _FAILURE_FILE_STEMS else "REQ"


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("pathly-hook: invalid JSON", file=sys.stderr)
        sys.exit(1)

    raw_path = payload.get("file") or payload.get("path")
    if not raw_path:
        sys.exit(0)  # no feedback file in this payload — nothing to do

    project_root_env = os.environ.get("PATHLY_PROJECT_ROOT")
    if not project_root_env:
        _log_skip("PATHLY_PROJECT_ROOT not set")
        sys.exit(0)

    pathly_root = (Path(project_root_env) / "pathly").resolve()
    # A feature's feedback lives at pathly/features/<name>/feedback/ (flat, current) or the
    # legacy pathly/plans/<name>/feedback/. Accept a path under EITHER; reject anything outside
    # both (traversal, or an absolute path elsewhere) — the write-path containment guard.
    allowed_roots = (pathly_root / "features", pathly_root / "plans")
    resolved = Path(raw_path).resolve()

    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        print(
            f"pathly-hook: rejected path outside features/ or plans/: {resolved}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(0)

    if not resolved.exists():
        sys.exit(0)

    content = resolved.read_text(encoding="utf-8")
    lines = content.splitlines()
    default_tag = _default_tag(resolved.name)
    already_tagged = tuple(f"- [{tag}]" for tag in _ALL_TAGS)
    tagged: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith(already_tagged):
            question_text = stripped[2:]
            tag = _classify(question_text) or default_tag
            tagged.append(f"- [{tag}] {question_text}")
        else:
            tagged.append(line)

    resolved.write_text("\n".join(tagged) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
