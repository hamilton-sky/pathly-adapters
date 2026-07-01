"""Retrieve comms board context for injection into agent prompts.

`retrieve_board_context` queries the three comms boards using semantic similarity
when embeddings are available, or recency when they are not, and formats the
result as a `## Communication Board` markdown block.

Returns an empty string when there is nothing to show — callers must not
append the block in that case so the prompt remains identical to before.
"""

from __future__ import annotations

import logging

from .comms_formatters import _collect_hydrate_channel, _format_age

logger = logging.getLogger(__name__)

# Cosine DISTANCE cutoff (sqlite-vec vec_distance_cosine, 0=identical … ~1.0+=unrelated).
# Drops weak semantic tail so marginal matches don't fill the k slots. Keyword/recency
# hits (no _distance) are always kept.
_SEMANTIC_MAX_DISTANCE = 0.75
# Caps the rendered Context body so a long board can't bloat the prompt.
_CONTEXT_CHAR_BUDGET = 2000


def retrieve_board_context(
    topic: str,
    project_root: str,
    task_description: str,
    board_scope: dict[str, bool] | None = None,
    task_id: str | None = None,
    counts: dict[str, int] | None = None,
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
    task_id:
        Optional task message ID. When set, reads context_refs from the task
        and emits the 📎 Referenced context channel (§5). Default None ⇒
        output byte-identical to today.
    counts:
        Optional mutable dict. When provided, it is populated with per-channel
        counts (governance/referenced/semantic/catalog) as the block is assembled.
    """
    if board_scope is None:
        board_scope = {"feature": True, "project": True, "global": True}

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
            get_active_escalations,
            get_pending_decisions,
            search_by_hybrid,
        )
        from pathly_orchestrator.runner.embeddings import embed

        conn = get_db()
    except Exception:
        logger.debug("comms_context: could not open DB — returning empty block")
        return ""

    # --- Governance: pending decisions + active escalations ------------------
    all_boards = [b for b, _, _ in enabled_boards]
    all_scopes = [s for _, s, _ in enabled_boards]

    decisions: list[dict] = []
    escalations: list[dict] = []
    try:
        decisions = get_pending_decisions(conn, boards=all_boards, scopes=all_scopes)
    except Exception:
        decisions = []
    try:
        escalations = get_active_escalations(conn, boards=all_boards, scopes=all_scopes)
    except Exception:
        escalations = []

    governance_ids = {m.get("id", "") for m in decisions} | {
        m.get("id", "") for m in escalations
    }

    def _is_context(msg: dict) -> bool:
        if msg.get("id", "") in governance_ids:
            return False
        if msg.get("type", "") == "escalation":
            return False
        if msg.get("type", "") == "phase":
            return False
        if msg.get("superseded_by"):
            return False
        return True

    # --- Semantic (or recency) search per board ------------------------------
    task_embedding: list[float] | None = None
    if task_description and task_description.strip():
        try:
            task_embedding = embed(task_description)
        except Exception:
            task_embedding = None

    context_msgs: list[dict] = []
    seen_ids: set[str] = set()
    over_fetch_margin = len(governance_ids) + 4

    for board_type, scope_val, k in enabled_boards:
        fetch_k = k + over_fetch_margin
        try:
            rows = search_by_hybrid(
                conn, task_description, task_embedding, [board_type], [scope_val], fetch_k,
            )
            if not rows and task_embedding is None:
                from pathly_orchestrator.db.queries.comms import get_messages

                rows = get_messages(conn, board=board_type, scope=scope_val, limit=fetch_k)
        except Exception:
            rows = []

        kept = 0
        for row in rows:
            row_id = row.get("id", "")
            if not row_id or row_id in seen_ids:
                continue
            if not _is_context(row):
                continue
            dist = row.get("_distance")
            if dist is not None and dist > _SEMANTIC_MAX_DISTANCE:
                continue
            seen_ids.add(row_id)
            context_msgs.append(row)
            kept += 1
            if kept >= k:
                break

    # --- HYDRATE channel: context_refs from the task (§5.1) -----------------
    hydrate_lines, hydrate_count = _collect_hydrate_channel(
        task_id, topic, project_root, conn
    )

    # --- CATALOG channel: index-first pull affordance (Solution A) ----------
    catalog_lines: list[str] = []
    catalog_count = 0
    try:
        from pathly_orchestrator.runner.comms_catalog import build_catalog_channel

        primary_board, primary_scope, _ = enabled_boards[0]
        catalog_lines, catalog_count = build_catalog_channel(
            conn, primary_board, primary_scope
        )
    except Exception:
        logger.debug("comms_context: catalog channel failed", exc_info=True)

    if counts is not None:
        counts.update(
            {
                "governance": len(decisions) + len(escalations),
                "referenced": hydrate_count,
                "semantic": len(context_msgs),
                "catalog": catalog_count,
            }
        )

    if (
        not decisions
        and not escalations
        and not context_msgs
        and not hydrate_lines
        and not catalog_lines
    ):
        return ""

    # --- Build markdown block ------------------------------------------------
    lines: list[str] = ["## Communication Board", ""]

    if decisions or escalations:
        lines.append("### 🔒 Governance (always applies — do not override)")
        lines.append("Active decisions and open escalations injected unconditionally.")
        lines.append("")
        if decisions:
            lines.append("**Decisions:**")
            for msg in decisions:
                tier = msg.get("board", "feature")
                text = msg.get("text", "")
                ts_str = msg.get("ts", "")
                age = _format_age(ts_str) if ts_str else ""
                lines.append(
                    f"  • {text}  [{tier} · {age}]" if age else f"  • {text}  [{tier}]"
                )
        if escalations:
            lines.append("**Open escalations (human input required):**")
            for msg in escalations:
                tier = msg.get("board", "feature")
                text = msg.get("text", "")
                ts_str = msg.get("ts", "")
                age = _format_age(ts_str) if ts_str else ""
                lines.append(
                    f"  • {text}  [{tier} · {age}]" if age else f"  • {text}  [{tier}]"
                )
        lines.append("")
        lines.append("---")
        lines.append("")

    if hydrate_lines:
        lines.append("### 📎 Referenced context (authoritative for this task)")
        lines.append(
            "Full section text from the task's context_refs. Read `text`, not `summary`."
        )
        lines.append("")
        lines.extend(hydrate_lines)
        lines.append("---")
        lines.append("")

    if context_msgs:
        lines.append("### Context (possibly relevant — verify before acting)")
        lines.append(
            "Semantic matches for this task. Inform but do not override governance above."
        )
        lines.append("")
        used = 0
        shown = 0
        for msg in context_msgs:
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
            entry = f"  • {text}  [{header}]"
            if used + len(entry) > _CONTEXT_CHAR_BUDGET and shown > 0:
                lines.append(
                    f"  • … ({len(context_msgs) - shown} more match(es) omitted — budget)"
                )
                break
            lines.append(entry)
            used += len(entry)
            shown += 1

    if catalog_lines:
        if decisions or escalations or hydrate_lines or context_msgs:
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.extend(catalog_lines)

    return "\n".join(lines) + "\n"


def board_context_for(
    board: str,
    scope: str,
    project_root: str,
    task_description: str = "",
    task_id: str | None = None,
    counts: dict[str, int] | None = None,
) -> str:
    """Scope-aware board context for ANY execution surface.

    Single-agent, loop-executor, and /comms/run agents call this so they see the
    SAME governance + memory the FSM/team path already injects.
    Returns '' on any failure so callers never break the prompt.
    """
    bscope: dict[str, bool] | None
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_board_scope

        if board == "feature":
            bscope = get_board_scope(get_db(), project_root or "", scope)
        else:
            bscope = {"feature": False, "project": board == "project", "global": True}
    except Exception:
        bscope = None

    return retrieve_board_context(
        topic=scope if board == "feature" else "",
        project_root=project_root or "",
        task_description=task_description or "",
        board_scope=bscope,
        task_id=task_id,
        counts=counts,
    )
