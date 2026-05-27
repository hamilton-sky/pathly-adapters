#!/usr/bin/env python3
"""Verify that pyproject.toml, studio/package.json, docs/SECURITY.md, and
the Codex plugin.json all reference the same version. Exits non-zero if they diverge."""
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


def get_studio_version() -> str | None:
    p = ROOT / "studio" / "package.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("version")


def get_security_doc_version() -> str | None:
    p = ROOT / "docs" / "SECURITY.md"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    m = re.search(r'(\d+\.\d+\.\d+)', text)
    return m.group(1) if m else None


def get_codex_plugin_version() -> str | None:
    p = ROOT / "src/pathly_data/adapters/codex/.codex-plugin/plugin.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("version")


def main() -> int:
    pyproject = get_pyproject_version()
    studio = get_studio_version()
    sec_doc = get_security_doc_version()
    codex_plugin = get_codex_plugin_version()

    mismatches = []
    if studio and studio != pyproject:
        mismatches.append(f"studio/package.json={studio!r} != pyproject.toml={pyproject!r}")
    if sec_doc and sec_doc != pyproject:
        mismatches.append(f"docs/SECURITY.md={sec_doc!r} != pyproject.toml={pyproject!r}")
    if codex_plugin and codex_plugin != pyproject:
        mismatches.append(f"codex plugin.json={codex_plugin!r} != pyproject.toml={pyproject!r}")

    if mismatches:
        print("Version sync check FAILED:")
        for m in mismatches:
            print(f"  {m}")
        return 1

    print(f"Version sync OK: {pyproject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
