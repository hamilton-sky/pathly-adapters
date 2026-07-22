#!/usr/bin/env python3
"""CI gate: no un-sanctioned runtime reads of state/board disk mirrors.

state-one-authority rule: the SQLite DB is the single runtime authority; the
per-feature disk files STATE.json / EVENTS.jsonl / ARTIFACTS.jsonl / BOARD.json
are DB->disk EXPORTs (or dropped). Runtime code reads the DB — never a mirror —
except at reviewed, DB-first fallback sites.

Mechanism (regex heuristic, line-window classification):
  - Scan src/**/*.py and studio/src/**/*.{ts,tsx} for a mirror filename used as a
    string literal (quote/backtick context, so docstrings/comments don't match;
    RUNNER_STATE.json is a different file and is excluded by the lookbehind).
  - For each hit, classify by the FIRST read-ish or write-ish token found on the
    same line or the next WINDOW_LINES lines: write wins -> ignored (exporters
    must write); read wins -> the line must carry an inline marker; neither ->
    neutral (path resolvers, event keys) -> ignored.
  - Marker: "pathly:allow-mirror-read: <reason>" on the flagged line or the line
    directly above, AND the file must be listed in scripts/mirror_reads_allowlist.txt.
    A marker in a non-listed file fails (no silent self-exemption). A listed file
    with no live marker anywhere warns (stale allow-list) but does not fail.

Known limitation (accepted by design): an indirected read — a path built on one
line and read via a variable more than WINDOW_LINES lines later, or in another
module — escapes the heuristic. The four names are near-universally inline
literals in this codebase, and every exemption stays a reviewed allow-list line.

Exit codes: 0 clean, 1 violations found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ALLOWLIST_FILE = ROOT / "scripts" / "mirror_reads_allowlist.txt"

MARKER = "pathly:allow-mirror-read:"
WINDOW_LINES = 8

# Mirror filename as a string literal: an opening quote/backtick earlier on the
# line with no closing one before the name. Lookbehind excludes RUNNER_STATE.json.
_NAMES = r"(?:STATE\.json|EVENTS\.jsonl|ARTIFACTS\.jsonl|BOARD\.json)"
MIRROR_LITERAL_RE = re.compile(r"[\"'`][^\"'`\n]*?(?<![A-Za-z0-9_])" + _NAMES)

# Read-direction tokens. `.glob(` counts: globbing for a mirror IS discovering
# mirrors to read. `json.load` also matches json.loads — same direction.
READ_TOKEN_RE = re.compile(
    r"(?:\bread_text\s*\(|\bread_bytes\s*\(|\bjson\.load|\breadlines\s*\(|"
    r"\.read\s*\(|\.glob\s*\(|\breadFile(?:Sync)?\s*\(|\bfs\.read\s*\()"
)
# open(...) is a read unless the mode string says write/append.
OPEN_RE = re.compile(r"\bopen\s*\(")
OPEN_WRITE_RE = re.compile(r"\bopen\s*\([^)]*[\"'](?:w|a|wb|ab|w\+|a\+)[\"']")

WRITE_TOKEN_RE = re.compile(
    r"(?:\bjson\.dump\b|\.write_text\s*\(|\.write\s*\(|\bos\.replace\s*\(|"
    r"\.replace\s*\(|\bwriteFile|\bfs\.write\s*\(|\.unlink\s*\(|\bmkdir\b)"
)

SCAN_SPECS: list[tuple[Path, tuple[str, ...]]] = [
    (ROOT / "src", ("*.py",)),
    (ROOT / "studio" / "src", ("*.ts", "*.tsx")),
]

_COMMENT_PREFIXES = ("#", "//", "*", "/*", '"""', "'''")


def _is_comment_line(line: str) -> bool:
    return line.lstrip().startswith(_COMMENT_PREFIXES)


def _classify_window(lines: list[str], start: int) -> str:
    """'read' | 'write' | 'neutral' for the window starting at line index start."""
    for i in range(start, min(start + WINDOW_LINES + 1, len(lines))):
        line = lines[i]
        if OPEN_WRITE_RE.search(line) or WRITE_TOKEN_RE.search(line):
            return "write"
        if READ_TOKEN_RE.search(line) or OPEN_RE.search(line):
            return "read"
    return "neutral"


def _has_marker(lines: list[str], idx: int) -> bool:
    if MARKER in lines[idx]:
        return True
    return idx > 0 and MARKER in lines[idx - 1]


def load_allowlist() -> set[str]:
    entries: set[str] = set()
    if not ALLOWLIST_FILE.exists():
        return entries
    for raw in ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(line.split()[0].replace("\\", "/"))
    return entries


def iter_source_files():
    for base, patterns in SCAN_SPECS:
        if not base.is_dir():
            continue
        for pattern in patterns:
            for path in sorted(base.rglob(pattern)):
                if "node_modules" in path.parts or "__pycache__" in path.parts:
                    continue
                yield path


def main() -> int:
    allowlist = load_allowlist()
    violations: list[str] = []  # unmarked reads
    unlisted_markers: list[str] = []  # marker in a file not on the allow-list
    files_with_markers: set[str] = set()

    for path in iter_source_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        if any(MARKER in line for line in lines):
            files_with_markers.add(rel)
            if rel not in allowlist:
                unlisted_markers.append(rel)

        for idx, line in enumerate(lines):
            if _is_comment_line(line) or MARKER in line:
                continue
            if not MIRROR_LITERAL_RE.search(line):
                continue
            if _classify_window(lines, idx) != "read":
                continue
            if _has_marker(lines, idx):
                continue
            violations.append(f"{rel}:{idx + 1}: {line.strip()}")

    stale = sorted(allowlist - files_with_markers)

    ok = True
    if violations:
        ok = False
        print("MIRROR-READ VIOLATIONS (state-one-authority):")
        print("Runtime code must read the DB, not a disk mirror. Either migrate the")
        print(f"read, or (for a reviewed DB-first fallback) add '{MARKER} <reason>'")
        print(
            "on/above the line AND list the file in scripts/mirror_reads_allowlist.txt.\n"
        )
        for v in violations:
            print(f"  {v}")
    if unlisted_markers:
        ok = False
        print("\nMARKERS IN FILES NOT ON THE ALLOW-LIST (no silent self-exemption):")
        for f in sorted(set(unlisted_markers)):
            print(f"  {f}")
    for f in stale:
        print(f"WARNING: allow-list entry has no live marker (stale?): {f}")

    if ok:
        n = len(files_with_markers)
        print(f"check_no_mirror_reads: OK ({n} allow-listed file(s) with markers)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
