"""Hook: inject ttl_hours frontmatter into feedback files.

Receives a JSON payload on stdin with a "file" or "path" key.
Validates the path stays inside the project's feature workspace (pathly/features/ or
legacy pathly/plans/).
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


def _log_skip(message: str) -> None:
    log_path = Path.home() / ".pathly" / "hook.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"inject_feedback_ttl: {message}\n")
    except OSError:
        pass


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

    if not resolved.exists():
        sys.exit(0)

    content = resolved.read_text(encoding="utf-8")

    if _has_ttl(content):
        sys.exit(0)

    resolved.write_text(_inject_ttl(content), encoding="utf-8")


if __name__ == "__main__":
    main()
