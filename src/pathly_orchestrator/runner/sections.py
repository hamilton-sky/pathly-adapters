"""Pure markdown section parser for the comms-board context-retrieval feature.

Implements the §3.1 anchor convention and §3.3 section index build.
No DB, no network I/O except file_fingerprint which reads one file.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    """A heading-delimited section of a markdown artifact."""

    anchor: str
    heading: str
    line_start: int  # 1-based inclusive
    line_end: int  # 1-based inclusive
    ordinal: int


# Matches a markdown heading of any level: # / ## / ### etc.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")

# Matches an explicit pathly:anchor comment (may appear before or on the heading line).
# Captures the id value from: <!-- pathly:anchor id="..." --> or id='...'
_ANCHOR_RE = re.compile(r"<!--\s*pathly:anchor\s+id=[\"']([^\"']+)[\"']\s*-->")

# Matches the phase-N pattern anywhere in a heading (case-insensitive).
_PHASE_RE = re.compile(r"(?i)\bphase\s+(\d+)\b")


def slugify_heading(heading: str) -> str:
    """Derive a URL slug from a markdown heading text (§3.1 algorithm).

    Priority:
    1. If an explicit pathly:anchor comment is embedded in the heading string,
       return its id verbatim.
    2. If the heading matches ``(?i)\\bphase\\s+(\\d+)\\b``, return ``phase-N``.
    3. Generic slug: lowercase, strip leading ``## ``/``### `` markers,
       drop a trailing ``— …`` clause, replace runs of non-``[a-z0-9]`` with ``-``,
       trim leading/trailing dashes.
    """
    anchor_match = _ANCHOR_RE.search(heading)
    if anchor_match:
        return anchor_match.group(1)

    phase_match = _PHASE_RE.search(heading)
    if phase_match:
        return f"phase-{phase_match.group(1)}"

    slug = heading.strip()
    slug = re.sub(r"^#{1,6}\s*", "", slug)
    slug = re.sub(r"\s*—.*$", "", slug)
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "section"


def parse_sections(text: str) -> list[Section]:
    """Split markdown into heading-delimited Section objects.

    A section runs from its heading line to the line before the next heading
    of equal-or-higher level (same or fewer #s), or EOF. Honors a
    ``<!-- pathly:anchor id=... -->`` comment that immediately precedes (or is
    embedded in) the heading line as the section's explicit anchor. Collision
    suffixes (-2, -3) are applied in document order when two slugs would match.
    Never raises — returns [] for empty/None input. Pure (no I/O).
    """
    if not text:
        return []

    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return []

    # First pass: collect (line_index, level, heading_text, explicit_anchor_or_None)
    raw: list[tuple[int, int, str, str | None]] = []
    pending_anchor: str | None = None

    for i, line in enumerate(lines):
        anchor_m = _ANCHOR_RE.search(line)
        if anchor_m:
            heading_m = _HEADING_RE.match(line)
            if heading_m:
                raw.append((i, len(heading_m.group(1)), heading_m.group(2).strip(), anchor_m.group(1)))
                pending_anchor = None
            else:
                pending_anchor = anchor_m.group(1)
            continue

        heading_m = _HEADING_RE.match(line)
        if heading_m:
            raw.append((i, len(heading_m.group(1)), heading_m.group(2).strip(), pending_anchor))
            pending_anchor = None
        else:
            pending_anchor = None

    if not raw:
        return []

    seen_slugs: dict[str, int] = {}

    def _unique_slug(base: str) -> str:
        if base not in seen_slugs:
            seen_slugs[base] = 1
            return base
        seen_slugs[base] += 1
        return f"{base}-{seen_slugs[base]}"

    sections: list[Section] = []
    for idx, (line_idx, level, heading_text, explicit_anchor) in enumerate(raw):
        if explicit_anchor:
            anchor = _unique_slug(explicit_anchor)
        else:
            base = slugify_heading(heading_text)
            anchor = _unique_slug(base)

        line_start = line_idx + 1  # 1-based

        next_same_or_higher = n
        for next_idx, (next_line_idx, next_level, _, _) in enumerate(raw):
            if next_idx <= idx:
                continue
            if next_level <= level:
                next_same_or_higher = next_line_idx
                break

        line_end = next_same_or_higher  # 1-based (last line before next heading)

        sections.append(
            Section(
                anchor=anchor,
                heading=heading_text,
                line_start=line_start,
                line_end=line_end,
                ordinal=idx,
            )
        )

    return sections


def file_fingerprint(path: str) -> tuple[float, str]:
    """Return (st_mtime, sha256-hex of FULL content) for staleness detection.

    Reads the file once. Raises OSError if the file cannot be read.
    """
    stat = os.stat(path)
    mtime = stat.st_mtime
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return mtime, h.hexdigest()


def structure_key(sections: list[Section]) -> str:
    """Return a stable, order-independent canonical string over heading slugs.

    Two files with the same headings in any order — or with body text edited or
    sections reordered — yield the SAME structure_key. Adding/removing/renaming a
    heading changes it. Pure (no I/O).
    """
    slugs = sorted(s.anchor for s in sections)
    return "|".join(slugs)
