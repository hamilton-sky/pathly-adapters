"""Hook: classify feedback questions as [REQ] or [ARCH].

Receives a JSON payload on stdin with a "file" or "path" key.
Validates the path stays inside the project's plans/ directory.
If ANTHROPIC_API_KEY is not set, exits silently (classification is optional).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("pathly-hook: invalid JSON", file=sys.stderr)
        sys.exit(1)

    raw_path = payload.get("file") or payload.get("path")
    if not raw_path:
        print("pathly-hook: invalid JSON", file=sys.stderr)
        sys.exit(1)

    project_root_env = os.environ.get("PATHLY_PROJECT_ROOT")
    if not project_root_env:
        print("pathly-hook: PATHLY_PROJECT_ROOT not set", file=sys.stderr)
        sys.exit(1)

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
            question_text = stripped[2:].lower()
            if any(kw in question_text for kw in ("architect", "design", "how", "approach", "structure")):
                tagged.append(f"- [ARCH] {stripped[2:]}")
            else:
                tagged.append(f"- [REQ] {stripped[2:]}")
        else:
            tagged.append(line)

    resolved.write_text("\n".join(tagged) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
