#!/usr/bin/env python3
"""Enforce CLAUDE.md's 400-line-per-file SOLID rule as a RATCHET, not a cliff.

The rule ("Single Responsibility — one file, one domain. Hard limit: 400 lines")
has been stated in CLAUDE.md and re-flagged by three production-readiness
assessments, and the violation count still went 6 (2026-07-07) → 14 (2026-07-15)
→ 28 (2026-08-18). A rule with no gate is not a rule.

Demanding all 28 be split at once would just make the gate unlandable, so this
is a ratchet against a recorded baseline (scripts/file_size_baseline.txt):

  * a file over the limit that is NOT in the baseline        → FAIL (new violation)
  * a baseline file that grew past its recorded size         → FAIL (regression)
  * a baseline file that dropped to/below the limit          → FAIL (ratchet click:
                                                                     drop the entry)

So existing debt is frozen, it can only shrink, and — this is the part that
matters for the SOLID rule — you cannot add lines to an already-oversized file.
Adding a NEW file is always allowed, which is exactly what rule #2 asks for
("extend by adding files, not by growing existing ones").

Usage:
    python3 scripts/check_file_size.py            # verify (CI)
    python3 scripts/check_file_size.py --update   # re-record the baseline
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BASELINE = Path(__file__).parent / "file_size_baseline.txt"

LIMIT = 400

# The two trees CLAUDE.md's "Code architecture — SOLID rules" section governs.
SCAN = [
    ("src/pathly_orchestrator", (".py",)),
    ("studio/src", (".ts", ".tsx")),
]
# Test files legitimately grow with the cases they cover, and generated files are
# not hand-maintained — neither is what the one-file-one-domain rule is about.
EXCLUDE_SUFFIXES = (".test.ts", ".test.tsx", ".test.py", ".gen.ts", ".d.ts")
EXCLUDE_PARTS = {"node_modules", "dist", "out", "__pycache__", ".venv"}


def iter_source_files():
    """Yield (repo-relative posix path, line count) for every governed source file."""
    for rel_root, suffixes in SCAN:
        root = ROOT / rel_root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if EXCLUDE_PARTS & set(path.parts):
                continue
            name = path.name
            if any(name.endswith(s) for s in EXCLUDE_SUFFIXES):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            yield path.relative_to(ROOT).as_posix(), len(text.splitlines())


def oversized() -> dict[str, int]:
    return {rel: n for rel, n in iter_source_files() if n > LIMIT}


def read_baseline() -> dict[str, int]:
    if not BASELINE.exists():
        return {}
    result: dict[str, int] = {}
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rel, _, count = line.rpartition(":")
        result[rel] = int(count)
    return result


def write_baseline(current: dict[str, int]) -> None:
    lines = [
        "# Frozen 400-line-rule debt — see scripts/check_file_size.py.",
        "# One entry per file still over the limit, recorded at its CURRENT size.",
        "# These may only SHRINK. Regenerate with: python3 scripts/check_file_size.py --update",
        "",
    ]
    lines += [f"{rel}:{n}" for rel, n in sorted(current.items(), key=lambda kv: -kv[1])]
    BASELINE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if "--update" in sys.argv:
        current = oversized()
        write_baseline(current)
        print(f"Baseline updated: {len(current)} file(s) over {LIMIT} lines.")
        return 0

    current = oversized()
    baseline = read_baseline()
    new_violations, regressions, resolved = [], [], []

    for rel, n in sorted(current.items()):
        if rel not in baseline:
            new_violations.append((rel, n))
        elif n > baseline[rel]:
            regressions.append((rel, baseline[rel], n))

    for rel, recorded in sorted(baseline.items()):
        if rel not in current:
            resolved.append((rel, recorded))

    if new_violations:
        print(f"ERROR: {len(new_violations)} file(s) over the {LIMIT}-line limit "
              f"and not in the frozen baseline:", file=sys.stderr)
        for rel, n in new_violations:
            print(f"  {rel}: {n} lines (limit {LIMIT})", file=sys.stderr)
        print("\n  Split the file by domain (CLAUDE.md 'Code architecture — SOLID rules'):\n"
              "  a blueprint owns one HTTP domain, a module owns one concern.", file=sys.stderr)

    if regressions:
        print(f"\nERROR: {len(regressions)} already-oversized file(s) grew further:", file=sys.stderr)
        for rel, was, now in regressions:
            print(f"  {rel}: {was} → {now} lines (+{now - was})", file=sys.stderr)
        print("\n  These files are already over the limit — extend by adding a new file,\n"
              "  not by growing this one (CLAUDE.md rule #2, Open/Closed).", file=sys.stderr)

    if resolved:
        print(f"\nERROR: {len(resolved)} baseline file(s) are now at or under {LIMIT} lines. "
              f"Nice — the ratchet has to click:", file=sys.stderr)
        for rel, was in resolved:
            print(f"  {rel}: was {was} lines, now <= {LIMIT}", file=sys.stderr)
        print("\n  Drop them from the baseline so they can never regress:\n"
              "  python3 scripts/check_file_size.py --update", file=sys.stderr)

    if new_violations or regressions or resolved:
        return 1

    total = sum(1 for _ in iter_source_files())
    print(f"OK: {total} source files checked; "
          f"{len(baseline)} known over {LIMIT} lines, none new, none grown.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
