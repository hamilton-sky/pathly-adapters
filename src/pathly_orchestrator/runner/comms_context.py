"""Retrieve comms board context for injection into agent prompts.

`retrieve_board_context` queries the three comms boards using semantic similarity
when embeddings are available, or recency when they are not, and formats the
result as a `## Communication Board` markdown block.

Returns an empty string when there is nothing to show — callers must not
append the block in that case so the prompt remains identical to before.
"""

from __future__ import annotations

import logging

from .board_scope import resolve_board_scope_setting
from .comms_formatters import _collect_hydrate_channel, _confidence_label, _format_age
from .context_budget import CONTEXT_CHAR_BUDGET, select_within_budget

logger = logging.getLogger(__name__)

# Per-tier cosine DISTANCE cutoffs (sqlite-vec vec_distance_cosine, 0=identical … ~1.0+=unrelated).
# The agent's OWN board is presumed relevant (feature 0.75); cross-tier boards must clear a
# stricter bar so project/global slots don't fill with tangential matches (ISSUE-1). Calibrated
# against the live board (2026-07-02): same-board matches land ~0.48–0.67, tangential cross-tier
# matches ~0.68–0.79, so project 0.55 / global 0.50 admit only genuinely-close cross-tier items.
# NOTE: keyword/recency hits carry no _distance and bypass this gate — see CT4 for the keyword bound.
_SEMANTIC_MAX_DISTANCE = {"feature": 0.75, "project": 0.55, "global": 0.50}
_SEMANTIC_MAX_DISTANCE_DEFAULT = 0.75
# Caps the rendered Context body so a long board can't bloat the prompt. The budget is
# SPLIT PER TIER (see context_budget.py) — a single shared budget let the feature tier,
# which renders first, spend the whole allowance before project/global ever got a slot.
_CONTEXT_CHAR_BUDGET = CONTEXT_CHAR_BUDGET


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
        and emits the Referenced context channel (§5). Default None ⇒
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

    # The agent's OWN board is the highest-priority enabled one — feature for a feature
    # run, but PROJECT for a project-level decompose (feature disabled). The own board
    # gets the lenient cutoff + keeps keyword-only hits; the strict per-tier cutoffs
    # exist to keep tangential CROSS-tier items out, so they must not fire on the own
    # board (else a project-decompose agent can't see its own sibling feature cards).
    own_board_type = enabled_boards[0][0]

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
                conn,
                task_description,
                task_embedding,
                [board_type],
                [scope_val],
                fetch_k,
            )
            if not rows and task_embedding is None:
                from pathly_orchestrator.db.queries.comms import get_messages

                rows = get_messages(
                    conn, board=board_type, scope=scope_val, limit=fetch_k
                )
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
            if dist is None:
                # CT4: a row with no cosine score. When semantic search is ACTIVE
                # (task_embedding present), an unscored cross-tier row is a BM25-only
                # keyword match that bypassed the distance gate — the ISSUE-1 leak — so
                # drop it on cross-tier boards (keep on the agent's OWN board — feature,
                # or project for a project-level decompose — for lexical recall). When
                # semantic search is INACTIVE (no embedding — the whole board is in
                # recency fallback), keep the row so cross-tier context isn't starved.
                if task_embedding is not None and board_type != own_board_type:
                    continue
            else:
                # Own board → lenient DEFAULT cutoff; cross-tier boards keep their strict
                # per-tier cutoff so tangential project/global items don't leak in.
                cutoff = (
                    _SEMANTIC_MAX_DISTANCE_DEFAULT
                    if board_type == own_board_type
                    else _SEMANTIC_MAX_DISTANCE.get(
                        board_type, _SEMANTIC_MAX_DISTANCE_DEFAULT
                    )
                )
                if dist > cutoff:
                    continue
            seen_ids.add(row_id)
            # Tag the tier from the LOOP, not from row["board"]: authoritative here and
            # independent of the search SELECT's shape. Consumed by the per-tier budget.
            row["_tier"] = board_type
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
        lines.append("### Governance (always applies — do not override)")
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
        lines.append("### Referenced context (authoritative for this task)")
        lines.append(
            "Full section text from the task's context_refs. Read `text`, not `summary`."
        )
        lines.append("")
        lines.extend(hydrate_lines)
        lines.append("---")
        lines.append("")

    if context_msgs:
        # T3b: when a task carries NO curated context_refs (hydrate_count == 0), the
        # semantic matches ARE the task's context — surface them under a distinct
        # UNVERIFIED header so the agent knows they're auto-derived guesses, never
        # authoritative. Transient: computed here, never persisted onto the task row.
        autoderived = task_id is not None and hydrate_count == 0
        if autoderived:
            lines.append(
                "### Auto-derived context (UNVERIFIED — no curated refs for this task)"
            )
            lines.append(
                "This task has no context_refs, so these semantic matches are auto-derived "
                "guesses — NOT authoritative. Verify before relying; pull artifacts from the "
                "catalog as needed."
            )
        else:
            lines.append("### Context (possibly relevant — verify before acting)")
            lines.append(
                "Semantic matches for this task. Inform but do not override governance above."
            )
        lines.append("")
        # Build every candidate line first, tagged with the tier it came from, and let
        # the per-tier budget decide what survives (CT5). Charging a shared budget in
        # render order meant a chatty feature board starved project/global outright.
        entries: list[tuple[str, str]] = []
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
            # CT2: surface match confidence as a coarse bucket (strong/moderate/weak),
            # not a raw float — legible in the /preview audit AND to the agent, without
            # implying false precision. Absent for keyword/recency hits (no _distance).
            confidence = _confidence_label(msg.get("_distance"))
            if confidence:
                parts.append(confidence)
            header = ", ".join(parts)
            text = msg.get("text", "")
            tier = msg.get("_tier") or msg.get("board") or "feature"
            entries.append((tier, f"  • {text}  [{header}]"))

        kept = select_within_budget(
            entries, [b for b, _, _ in enabled_boards], _CONTEXT_CHAR_BUDGET
        )
        for idx in kept:
            lines.append(entries[idx][1])
        omitted = len(entries) - len(kept)
        if omitted:
            lines.append(f"  • … ({omitted} more match(es) omitted — budget)")

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
    role: str = "",
) -> str:
    """Scope-aware board context for ANY execution surface.

    Single-agent, loop-executor, and /comms/run agents call this so they see the
    SAME governance + memory the FSM/team path already injects.
    Returns '' on any failure so callers never break the prompt.

    ``role`` picks up that agent's own tier allocation when one is configured — an architect
    and a builder on the same board can need different mixes. Absent a per-role row it
    resolves to exactly the per-feature answer this helper has always returned.
    """
    bscope = resolve_board_scope_setting(board, scope, project_root or "", role)

    return retrieve_board_context(
        topic=scope if board == "feature" else "",
        project_root=project_root or "",
        task_description=task_description or "",
        board_scope=bscope,
        task_id=task_id,
        counts=counts,
    )
