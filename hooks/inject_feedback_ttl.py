"""Hook: inject ttl_hours frontmatter into feedback files.

Receives a JSON payload on stdin with a "file" or "path" key.
Validates the path stays inside the project's plans/ directory.
Idempotent: if ttl_hours: is already present in frontmatter, exits 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_TTL_KEY = "ttl_hours"
_TTL_LINE = "ttl_hours: 48"
_FENCE = "---"


def _has_ttl(content: str) -> bool:
    lines = content.splitlines()
    in_frontmatter = False
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == _FENCE:
            in_frontmatter = True
            continue
        if in_frontmatter:
            if line.strip() == _FENCE:
                break
            if line.startswith(_TTL_KEY + ":"):
                return True
    return False


def _inject_ttl(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].strip() == _FENCE:
        return _FENCE + "\n" + _TTL_LINE + "\n" + "\n".join(lines[1:]) + "\n"
    return _FENCE + "\n" + _TTL_LINE + "\n" + _FENCE + "\n" + content


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

    if not resolved.exists():
        sys.exit(0)

    content = resolved.read_text(encoding="utf-8")

    if _has_ttl(content):
        sys.exit(0)

    resolved.write_text(_inject_ttl(content), encoding="utf-8")


if __name__ == "__main__":
    main()
