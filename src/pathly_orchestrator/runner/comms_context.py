"""Retrieve comms board context for injection into agent prompts.

`retrieve_board_context` queries the three comms boards (feature, project,
global) using semantic similarity when embeddings are available, or recency
when they are not, and formats the result as a `## Communication Board`
markdown block ready for appending to `agent_hint.instructions`.

Returns an empty string when there is nothing to show — callers must not
append the block in that case so the prompt remains identical to before.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _format_age(ts_str: str) -> str:
    """Convert an ISO timestamp string to a human-readable age label."""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_seconds = int((now - ts).total_seconds())
        if delta_seconds < 60:
            return "just now"
        if delta_seconds < 3600:
            return f"{delta_seconds // 60}m ago"
        if delta_seconds < 86400:
            return f"{delta_seconds // 3600}h ago"
        return f"{delta_seconds // 86400}d ago"
    except Exception:
        return ""


def _format_decision(msg: dict) -> str:
    # SPEC convention: `board` holds the tier (feature/project/global).
    tier = msg.get("board", "feature")
    text = msg.get("text", "")
    return f"- [{tier}] {text}"


def _format_context_line(msg: dict) -> str:
    from_agent = msg.get("from_agent", "?")
    to_agent = msg.get("to_agent", "*")
    stage = msg.get("stage") or ""
    ts_str = msg.get("ts", "")
    age = _format_age(ts_str) if ts_str else ""

    parts = [f"{from_agent} → {to_agent}"]
    if stage:
        parts.append(stage)
    if age:
        parts.append(age)

    header = ", ".join(parts)
    text = msg.get("text", "")
    return f"- [{header}] {text}"


def _format_question(msg: dict) -> str:
    from_agent = msg.get("from_agent", "?")
    to_agent = msg.get("to_agent", "*")
    msg_id = msg.get("id", "")
    text = msg.get("text", "")
    short_id = msg_id[:7] if msg_id else ""

    header = f"{from_agent} → {to_agent}"
    if short_id:
        header += f", {short_id}"

    line = f"- [{header}] {text}"

    options_raw = msg.get("options")
    if options_raw:
        try:
            opts: list = json.loads(options_raw) if isinstance(options_raw, str) else options_raw
            if opts:
                opt_parts = [f"{o.get('id', i)}) {o.get('label', '')}" for i, o in enumerate(opts)]
                line += "\n  Options: " + "  ".join(opt_parts)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return line


def retrieve_board_context(
    topic: str,
    project_root: str,
    task_description: str,
    board_scope: dict[str, bool] | None = None,
) -> str:
    """Return a `## Communication Board` markdown block, or '' when empty.

    Parameters
    ----------
    topic:
        The feature name (used as the feature-board scope key).
    project_root:
        The project root path (used as the project-board scope key).
    task_description:
        The upcoming agent's task — embedded for semantic search.
    board_scope:
        Dict with keys 'feature', 'project', 'global' mapping to bool.
        Defaults to all-enabled when None or absent.
    """
    if board_scope is None:
        board_scope = {"feature": True, "project": True, "global": True}

    # SPEC convention (aligned across storage + retrieval):
    #   board = tier ("feature"/"project"/"global"), scope = identifier.
    # Feature board: board="feature", scope=topic. Project board: board="project",
    # scope=project_root. Global board: board="global", scope="global".
    # Tuples below are (board_tier, scope_identifier, k).
    _norm_root = project_root.replace("\\", "/").rstrip("/")
    enabled_boards: list[tuple[str, str, int]] = []
    if board_scope.get("feature", True):
        enabled_boards.append(("feature", topic, 3))
    if board_scope.get("project", True):
        enabled_boards.append(("project", _norm_root, 2))
    if board_scope.get("global", True):
        enabled_boards.append(("global", "global", 1))

    if not enabled_boards:
        return ""

    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import (
            get_pending_decisions,
            search_by_embedding,
        )
        from pathly_orchestrator.runner.embeddings import embed

        conn = get_db()
    except Exception:
        logger.debug("comms_context: could not open DB — returning empty block")
        return ""

    # --- Semantic (or recency) search for each enabled board ----------------
    task_embedding: list[float] | None = None
    if task_description and task_description.strip():
        try:
            task_embedding = embed(task_description)
        except Exception:
            task_embedding = None

    retrieved: list[dict] = []
    seen_ids: set[str] = set()

    for board_type, scope_val, k in enabled_boards:
        try:
            if task_embedding is not None:
                rows = search_by_embedding(
                    conn,
                    embedding=task_embedding,
                    boards=[board_type],
                    scopes=[scope_val],
                    k=k,
                )
            else:
                # Fallback: recency — reuse search_by_embedding without a real
                # embedding by passing an empty list; the function's recency path
                # activates when _VEC_AVAILABLE is False.  If vec IS available,
                # we fetch by recency directly via get_messages.
                from pathly_orchestrator.db.queries.comms import get_messages
                rows = get_messages(conn, board=board_type, scope=scope_val, limit=k)
        except Exception:
            rows = []

        for row in rows:
            row_id = row.get("id", "")
            if row_id and row_id not in seen_ids:
                seen_ids.add(row_id)
                retrieved.append(row)

    # --- Always include pending decisions and escalations -------------------
    # SPEC convention: board = tier, scope = identifier.
    all_boards = [b for b, _, _ in enabled_boards]
    all_scopes = [s for _, s, _ in enabled_boards]

    mandatory: list[dict] = []
    try:
        mandatory = get_pending_decisions(conn, boards=all_boards, scopes=all_scopes)
    except Exception:
        mandatory = []

    mandatory_ids = {m.get("id", "") for m in mandatory}

    # --- Partition into sections --------------------------------------------
    decisions: list[dict] = list(mandatory)
    context_msgs: list[dict] = []
    questions: list[dict] = []

    for msg in retrieved:
        msg_id = msg.get("id", "")
        if msg_id in mandatory_ids:
            continue
        msg_type = msg.get("type", "")
        if msg_type == "decision":
            if msg_id not in {d.get("id", "") for d in decisions}:
                decisions.append(msg)
        elif msg_type in ("question",) and msg.get("status") == "pending":
            questions.append(msg)
        else:
            context_msgs.append(msg)

    # Nothing to show
    if not decisions and not context_msgs and not questions:
        return ""

    # --- Build markdown block -----------------------------------------------
    lines: list[str] = [
        "## Communication Board",
        "",
        "> These are messages from your team. Decisions override your defaults.",
        "> Read all entries. Acknowledge questions that are addressed to you.",
    ]

    if decisions:
        lines.append("")
        lines.append("### 📌 Decisions (always apply)")
        for msg in decisions:
            lines.append(_format_decision(msg))

    if context_msgs:
        lines.append("")
        lines.append("### 💬 Recent context")
        for msg in context_msgs:
            lines.append(_format_context_line(msg))

    if questions:
        lines.append("")
        lines.append("### ❓ Open questions (answer if relevant to your work)")
        for msg in questions:
            lines.append(_format_question(msg))

    return "\n".join(lines) + "\n"
