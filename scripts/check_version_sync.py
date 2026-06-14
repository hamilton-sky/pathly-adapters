#!/usr/bin/env python3
"""Verify that all version sources reference the same version.

Checked sources (all must match pyproject.toml):
  - package.json          (root monorepo package)
  - studio/package.json   (Electron app)
  - src/pathly_data/adapters/codex/.codex-plugin/plugin.json

Exits non-zero if any source diverges.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def get_pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise ValueError("version not found in pyproject.toml")
    return m.group(1)


def get_json_version(rel_path: str) -> str | None:
    p = ROOT / rel_path
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("version")


def main() -> int:
    pyproject = get_pyproject_version()

    sources = {
        "package.json":                                              get_json_version("package.json"),
        "studio/package.json":                                       get_json_version("studio/package.json"),
        "adapters/codex/.codex-plugin/plugin.json":                  get_json_version(
            "src/pathly_data/adapters/codex/.codex-plugin/plugin.json"
        ),
    }

    mismatches = []
    for label, ver in sources.items():
        if ver is None:
            continue
        if ver != pyproject:
            mismatches.append(f"  {label}: {ver!r}  !=  pyproject.toml: {pyproject!r}")

    if mismatches:
        print("Version sync FAILED:")
        for line in mismatches:
            print(line)
        print()
        print(f"Fix: update the above files to match pyproject.toml ({pyproject})")
        return 1

    print(f"Version sync OK: {pyproject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
