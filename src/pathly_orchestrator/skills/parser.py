"""Parse a skill .md file into structured body cells for the notebook editor.

Round-trip contract (Phase 0 — notebook-edit-actions):
- Frontmatter is preserved **byte-for-byte** — never dropped, never reformatted.
- Headings are stored as the **bare title** (no `#` prefix) plus a `headingLevel`,
  so serialization reconstructs the original level instead of forcing `## `.
- `serialize_skill_document` is the single serializer shared by /skills/save and
  /skills/preview, so the two surfaces can never diverge.
"""

from __future__ import annotations

import re
import uuid

# Matches a leading YAML frontmatter block, including its closing delimiter and
# trailing newline. Captured verbatim so it round-trips byte-for-byte.
_FRONTMATTER_RE = re.compile(r"^(---\n.*?\n---\n)", re.DOTALL)
_HEADING_PREFIX_RE = re.compile(r"^(#{1,6})\s+")


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body).

    frontmatter_block is "" when absent, else the verbatim ``---\\n…\\n---\\n`` block.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end() :]


def _heading_level(line: str) -> int:
    m = _HEADING_PREFIX_RE.match(line)
    return len(m.group(1)) if m else 0


def _cell(heading: str, level: int, content: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "type": "body",
        "heading": heading,
        "headingLevel": level,
        "content": content,
        "locked": True,
    }


def _split_cells(body: str) -> list[dict]:
    """Split a frontmatter-free body on '## ' headings into body cells."""
    cells: list[dict] = []
    parts = re.split(r"(?m)^(## .+)$", body)

    if len(parts) == 1:
        content = parts[0].strip()
        if content:
            cells.append(_cell("", 0, content))
        return cells

    # parts alternates: [preamble, heading, content, heading, content, ...]
    preamble = parts[0].strip()
    if preamble:
        cells.append(_cell("", 0, preamble))

    for i in range(1, len(parts) - 1, 2):
        raw_heading = parts[i].strip()  # e.g. "## Role"
        level = _heading_level(raw_heading)  # 2
        heading = _HEADING_PREFIX_RE.sub("", raw_heading)  # "Role"
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        cells.append(_cell(heading, level, content))

    return cells


def parse_skill_document(skill_path: str) -> dict:
    """Parse a skill .md into ``{"frontmatter": str, "body_cells": [...]}``.

    frontmatter is the verbatim YAML block (or "" if none); body cells carry a bare
    heading + headingLevel so the original heading level is reconstructable.
    """
    with open(skill_path, encoding="utf-8") as f:
        text = f.read()
    frontmatter, body = split_frontmatter(text)
    return {"frontmatter": frontmatter, "body_cells": _split_cells(body)}


def parse_skill_body(skill_path: str) -> list[dict]:
    """Backward-compatible accessor: body cells only (frontmatter not returned)."""
    return parse_skill_document(skill_path)["body_cells"]


def serialize_skill_document(frontmatter: str, body_cells: list[dict]) -> str:
    """Reconstruct a skill .md from frontmatter + body cells.

    The single serializer shared by /skills/save and /skills/preview. For a
    canonically-formatted skill file (one blank line between sections), parse →
    serialize is byte-identical, and the frontmatter block is always preserved
    exactly.
    """
    parts: list[str] = []
    for bc in body_cells:
        if not isinstance(bc, dict):
            continue
        heading = (bc.get("heading") or "").strip()
        content = (bc.get("content") or "").strip()
        if heading:
            level = bc.get("headingLevel")
            if not isinstance(level, int) or level < 1 or level > 6:
                level = 2
            hashes = "#" * level
            parts.append(
                f"{hashes} {heading}\n\n{content}" if content else f"{hashes} {heading}"
            )
        elif content:
            parts.append(content)

    body_markdown = ("\n\n".join(parts) + "\n") if parts else ""

    if frontmatter:
        # Exactly one blank line between the closing '---' and the body.
        return frontmatter.rstrip("\n") + "\n\n" + body_markdown
    return body_markdown
