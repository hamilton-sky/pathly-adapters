"""Parse a skill .md file into structured body cells for the notebook editor."""

from __future__ import annotations

import uuid
import re


def parse_skill_body(skill_path: str) -> list[dict]:
    """Read skill_path and split on '## ' headings into body cells.

    Strips YAML frontmatter (between --- delimiters) before splitting.

    Returns list of:
      {"id": str(uuid4()), "type": "body", "heading": "## Role", "content": "...", "locked": True}
    """
    with open(skill_path, encoding="utf-8") as f:
        text = f.read()

    # Strip YAML frontmatter delimited by --- at start of file
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)

    cells: list[dict] = []
    # Split on lines that start with "## " (level-2 headings)
    parts = re.split(r"(?m)^(## .+)$", text)

    if len(parts) == 1:
        # No ## headings found — return the whole body as one cell
        content = parts[0].strip()
        if content:
            cells.append({
                "id": str(uuid.uuid4()),
                "type": "body",
                "heading": "",
                "content": content,
                "locked": True,
            })
        return cells

    # parts alternates: [preamble, heading, content, heading, content, ...]
    preamble = parts[0].strip()
    if preamble:
        cells.append({
            "id": str(uuid.uuid4()),
            "type": "body",
            "heading": "",
            "content": preamble,
            "locked": True,
        })

    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        cells.append({
            "id": str(uuid.uuid4()),
            "type": "body",
            "heading": heading,
            "content": content,
            "locked": True,
        })

    return cells
