"""Hook: classify feedback questions as [REQ] or [ARCH].

Receives a JSON payload on stdin with a "file" or "path" key.
Validates the path stays inside the project's plans/ directory.
If ANTHROPIC_API_KEY is not set, exits silently (classification is optional).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_ARCH_QUESTION = re.compile(
    r"\b(architect|architecture|architectural|design|approach|structure)\b",
    re.IGNORECASE,
)


def _log_skip(message: str) -> None:
    log_path = Path.home() / ".pathly" / "hook.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"classify_feedback: {message}\n")
    except OSError:
        pass


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

    plans_dir = (Path(project_root_env) / "plans").resolve()
    resolved = Path(raw_path).resolve()

    if not resolved.is_relative_to(plans_dir):
        print(
            f"pathly-hook: rejected path outside plans/: {resolved}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(0)

    if not resolved.exists():
        sys.exit(0)

    content = resolved.read_text(encoding="utf-8")
    lines = content.splitlines()
    tagged: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- [REQ]") and not stripped.startswith("- [ARCH]"):
            question_text = stripped[2:]
            if _ARCH_QUESTION.search(question_text):
                tagged.append(f"- [ARCH] {stripped[2:]}")
            else:
                tagged.append(f"- [REQ] {stripped[2:]}")
        else:
            tagged.append(line)

    resolved.write_text("\n".join(tagged) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
