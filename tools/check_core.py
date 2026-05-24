#!/usr/bin/env python3
"""
Pathly core consistency checker.
Verifies:
  1. No bare plans/, explorations/, or debugs/ path references in core/
  2. Skill/agent files referenced in SKILLS_OVERVIEW.md exist on disk
  3. Every core skill/agent .md has a matching _meta entry in all 3 adapters
  4. Doc cross-references to core/ paths resolve to real files
Exit 0 = all clear. Exit 1 = failures found (printed to stdout).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "src", "pathly_data", "core")
ADAPTERS = os.path.join(ROOT, "src", "pathly_data", "adapters")
ADAPTER_NAMES = ["claude", "codex", "copilot"]

failures: list[str] = []


# ── Check 1: No bare path prefixes ──────────────────────────────────────────
BARE_PATH_PATTERN = re.compile(
    r'(?<![/\w])(?:plans|explorations|debugs)/(?!\.)',
    re.IGNORECASE
)
# Patterns that are already correctly prefixed — skip these
ALREADY_PREFIXED = re.compile(r'pathly/(plans|explorations|debugs)/')

def check_bare_paths() -> None:
    for dirpath, _, filenames in os.walk(CORE):
        for fname in filenames:
            if not fname.endswith(('.md', '.yaml', '.yml')):
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, ROOT)
            with open(fpath, encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    # Skip lines that use the correct prefix
                    if ALREADY_PREFIXED.search(line):
                        continue
                    # Skip comment lines and code fence markers
                    stripped = line.strip()
                    if stripped.startswith('#') or stripped.startswith('```'):
                        continue
                    if BARE_PATH_PATTERN.search(line):
                        failures.append(
                            f"BARE_PATH  {rel}:{lineno}  {line.rstrip()}"
                        )


# ── Check 2: Skill references in SKILLS_OVERVIEW resolve to real files ───────
SKILL_REF_PATTERN = re.compile(r'core/skills/([\w/-]+)\.md')
AGENT_REF_PATTERN = re.compile(r'core/agents/([\w/-]+)\.md')

def check_doc_references() -> None:
    overview = os.path.join(CORE, "SKILLS_OVERVIEW.md")
    if not os.path.exists(overview):
        failures.append("MISSING  SKILLS_OVERVIEW.md not found")
        return
    with open(overview, encoding='utf-8') as f:
        content = f.read()
    for m in SKILL_REF_PATTERN.finditer(content):
        target = os.path.join(ROOT, "src", "pathly_data", "core", "skills", m.group(1) + ".md")
        if not os.path.exists(target):
            failures.append(f"DEAD_REF  SKILLS_OVERVIEW.md → core/skills/{m.group(1)}.md not found")
    for m in AGENT_REF_PATTERN.finditer(content):
        target = os.path.join(ROOT, "src", "pathly_data", "core", "agents", m.group(1) + ".md")
        if not os.path.exists(target):
            failures.append(f"DEAD_REF  SKILLS_OVERVIEW.md → core/agents/{m.group(1)}.md not found")


# ── Check 3: Every core skill/agent .md has _meta in all 3 adapters ─────────
def check_adapter_parity() -> None:
    core_files: list[str] = []
    for dirpath, _, filenames in os.walk(CORE):
        for fname in filenames:
            if fname.endswith('.md') and not fname.startswith('README') and 'template' not in dirpath.lower() and 'SKILLS_OVERVIEW' not in fname:
                # Get the skill/agent name (stem)
                stem = fname[:-3]  # remove .md
                core_files.append(stem)

    for adapter in ADAPTER_NAMES:
        meta_dir = os.path.join(ADAPTERS, adapter, "_meta")
        if not os.path.exists(meta_dir):
            failures.append(f"MISSING_ADAPTER  {adapter}/_meta/ directory not found")
            continue
        meta_files = {
            os.path.splitext(f)[0]
            for f in os.listdir(meta_dir)
            if f.endswith('.yaml')
        }
        for stem in core_files:
            if stem not in meta_files:
                failures.append(
                    f"PARITY  core skill/agent '{stem}' has no _meta in adapters/{adapter}/"
                )


# ── Check 4: Cross-references in all core .md files resolve ─────────────────
CROSS_REF_PATTERN = re.compile(r'`(core/(?:skills|agents)/[\w/-]+\.md)`')

def check_cross_references() -> None:
    for dirpath, _, filenames in os.walk(CORE):
        for fname in filenames:
            if not fname.endswith('.md'):
                continue
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, ROOT)
            with open(fpath, encoding='utf-8') as f:
                for lineno, line in enumerate(f, 1):
                    for m in CROSS_REF_PATTERN.finditer(line):
                        target_rel = m.group(1)  # e.g. core/skills/flow/go.md
                        target = os.path.join(ROOT, "src", "pathly_data", target_rel)
                        if not os.path.exists(target):
                            failures.append(
                                f"DEAD_XREF  {rel}:{lineno}  {target_rel} not found"
                            )


# ── Run all checks ────────────────────────────────────────────────────────────
def main() -> None:
    check_bare_paths()
    check_doc_references()
    check_adapter_parity()
    check_cross_references()

    if failures:
        print(f"check_core: {len(failures)} issue(s) found\n")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    else:
        print(f"check_core: all checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
