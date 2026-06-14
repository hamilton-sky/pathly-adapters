#!/usr/bin/env python3
"""Verify adapter consistency across the three places that must stay in sync.

For every directory under src/pathly_data/adapters/ there must be a matching
entry in all three of:

  1. install_cli/orchestrate.py   — ALLOWED_HOSTS set
  2. install_cli/detect.py        — host detection dict key
  3. pathly_orchestrator/fsm/state.py — _KNOWN_ADAPTERS frozenset

Exits non-zero if any adapter is missing from any of the three.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ADAPTERS_DIR = ROOT / "src" / "pathly_data" / "adapters"


def adapter_dirs() -> set[str]:
    return {p.name for p in ADAPTERS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")}


def parse_set_literal(text: str, var_name: str) -> set[str]:
    """Extract string members from a set or frozenset literal assigned to var_name.

    Handles both:
        VAR = {"a", "b"}
        VAR: type = frozenset({"a", "b"})
    """
    # Find the variable assignment line
    start = text.find(var_name)
    if start == -1:
        return set()
    # Find the opening brace (may be inside frozenset(...))
    brace_start = text.find("{", start)
    if brace_start == -1:
        return set()
    # Walk forward tracking brace depth
    depth = 0
    i = brace_start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = text[brace_start + 1 : i]
    return set(re.findall(r'"([^"]+)"', body))


def parse_dict_keys(text: str, var_name: str) -> set[str]:
    """Extract top-level string keys from a Python dict assignment.

    Works on multi-line dicts with complex values (e.g. Path.home() calls).
    Finds the assignment, then collects all "key": patterns up to the closing
    brace at the same indent level.
    """
    start = text.find(f"{var_name}")
    if start == -1:
        return set()
    # Find the opening brace
    brace_start = text.find("{", start)
    if brace_start == -1:
        return set()
    # Walk forward tracking brace depth to find the matching closing brace
    depth = 0
    i = brace_start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = text[brace_start + 1 : i]
    # Extract string keys (only top-level: "key":)
    return set(re.findall(r'^\s*"([^"]+)"\s*:', body, re.MULTILINE))


def main() -> int:
    adapters = adapter_dirs()
    if not adapters:
        print("ERROR: no adapter directories found under src/pathly_data/adapters/")
        return 1

    orchestrate_text = (ROOT / "src" / "install_cli" / "orchestrate.py").read_text(encoding="utf-8")
    detect_text      = (ROOT / "src" / "install_cli" / "detect.py").read_text(encoding="utf-8")
    state_text       = (ROOT / "src" / "pathly_orchestrator" / "fsm" / "state.py").read_text(encoding="utf-8")

    allowed_hosts   = parse_set_literal(orchestrate_text, "ALLOWED_HOSTS")
    detected_hosts  = parse_dict_keys(detect_text, "_HOST_MARKERS")
    known_adapters  = parse_set_literal(state_text, "_KNOWN_ADAPTERS")

    checks = {
        "install_cli/orchestrate.py  (ALLOWED_HOSTS)":        allowed_hosts,
        "install_cli/detect.py       (host detection dict)":  detected_hosts,
        "pathly_orchestrator/fsm/state.py (_KNOWN_ADAPTERS)": known_adapters,
    }

    errors = []
    for location, registered in checks.items():
        missing = adapters - registered
        extra   = registered - adapters
        if missing:
            errors.append(f"  {location}")
            errors.append(f"    MISSING (dir exists, not registered): {sorted(missing)}")
        if extra:
            errors.append(f"  {location}")
            errors.append(f"    EXTRA   (registered, no dir):         {sorted(extra)}")

    if errors:
        print("Adapter consistency check FAILED:")
        for line in errors:
            print(line)
        print()
        print("Adapter dirs:", sorted(adapters))
        for label, registered in checks.items():
            if registered:
                print(f"Registered in {label.split('(')[0].strip()}: {sorted(registered)}")
        return 1

    print(f"Adapter consistency OK: {sorted(adapters)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
