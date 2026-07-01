"""Catalog-pull channel for board context (board-context-pull Solution A).

Builds the 📚 Catalog channel appended to an agent's board-context block: a short,
recency-ordered index of artifacts the agent MAY pull from, plus the permission-
scoped GET URLs to list/hydrate more. Index-first by design — the agent sees the
top entries inline so it can pick the right section on the first try instead of a
blind round-trip (or not pulling at all).

Emitted only when the agent's primary board has at least one artifact, so the
context block stays byte-identical to before on artifact-free boards.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Max artifact rows shown inline in the catalog index (recency-ordered). The agent
# can list the rest via the GET URL — this bounds prompt size the way
# _CONTEXT_CHAR_BUDGET bounds the Context channel.
_CATALOG_INDEX_MAX = 12
# Per-entry summary truncation so one long summary can't dominate the index.
_CATALOG_SUMMARY_CHARS = 140


def build_catalog_channel(conn: Any, board: str, scope: str) -> tuple[list[str], int]:
    """Return ``(markdown_lines, artifact_count)`` for the 📚 Catalog channel.

    Lists up to ``_CATALOG_INDEX_MAX`` artifacts on ``(board, scope)`` newest-first
    and appends the scoped pull instructions. Returns ``([], 0)`` when the catalog
    is empty or unavailable, so the caller omits the channel entirely (keeping the
    block byte-identical to before on empty boards).
    """
    if not scope:
        return [], 0
    try:
        from pathly_orchestrator.db.queries.comms import list_artifacts_catalog

        rows = list_artifacts_catalog(
            conn,
            scope,
            exposed_boards=[board],
            order="recency",
            limit=_CATALOG_INDEX_MAX + 1,
        )
    except Exception:
        logger.debug("catalog channel: list_artifacts_catalog failed", exc_info=True)
        return [], 0

    if not rows:
        return [], 0

    shown = rows[:_CATALOG_INDEX_MAX]
    overflow = len(rows) - len(shown)

    lines: list[str] = [
        "### 📚 Catalog (you may pull more — scoped to your board)",
        "Artifacts on your board you can pull on demand. Pull narrowly — only what "
        "the task needs.",
        "",
    ]
    for r in shown:
        path = r.get("path") or r.get("title") or "?"
        atype = r.get("type") or "?"
        summary = (r.get("summary") or r.get("title") or "").strip().replace("\n", " ")
        if len(summary) > _CATALOG_SUMMARY_CHARS:
            summary = summary[: _CATALOG_SUMMARY_CHARS - 1] + "…"
        suffix = f" — {summary}" if summary else ""
        lines.append(f"  • {path}  [{atype}]{suffix}")
    if overflow > 0:
        lines.append(f"  • … ({overflow}+ more — list via the URL below)")
    lines.append("")
    lines.append(f"To list all: `GET /comms/artifacts?board={board}&scope={scope}`")
    lines.append(
        f"To read one: `GET /comms/artifacts/section?scope={scope}"
        "&artifact=<path>&anchor=<anchor>` (omit anchor for the whole file)."
    )
    lines.append(
        "The 📎 references above are already hydrated — don't refetch them. Append "
        "`&trail=<task_id>` to a pull so the board records what you read."
    )
    return lines, len(rows)
