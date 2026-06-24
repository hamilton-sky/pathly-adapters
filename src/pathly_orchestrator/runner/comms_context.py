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
            opts: list = (
                json.loads(options_raw) if isinstance(options_raw, str) else options_raw
            )
            if opts:
                opt_parts = [
                    f"{o.get('id', i)}) {o.get('label', '')}"
                    for i, o in enumerate(opts)
                ]
                line += "\n  Options: " + "  ".join(opt_parts)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return line


# 💡 Context channel relevance gate (Phase: memory consolidation).
# _SEMANTIC_MAX_DISTANCE is a cosine DISTANCE cutoff (sqlite-vec vec_distance_cosine,
# 0 = identical … ~1.0+ = unrelated for MiniLM-384). Semantic hits weaker than this are
# dropped so marginal matches never fill the k slots on a small/early board. Conservative
# by design — only the clearly-weak tail is cut; keyword/recency hits (no _distance) are
# always kept. _CONTEXT_CHAR_BUDGET caps the rendered 💡 body so a long board can't bloat
# the prompt. Both are tunable.
_SEMANTIC_MAX_DISTANCE = 0.75
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
        counts (``governance``/``referenced``/``semantic``/``catalog``) as the
        block is assembled — single source of truth for the preview endpoint
        (board-context-pull Solution C), no re-querying or block parsing.
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
            get_active_escalations,
            get_pending_decisions,
            search_by_embedding,
            search_by_hybrid,
        )
        from pathly_orchestrator.runner.embeddings import embed

        conn = get_db()
    except Exception:
        logger.debug("comms_context: could not open DB — returning empty block")
        return ""

    # --- Governance first: pending decisions + active escalations -----------
    # SPEC convention: board = tier, scope = identifier.
    # Computed *before* the semantic search so governance messages can be
    # excluded from the context pool before the per-board k-cap is applied.
    # Decisions and escalations are embedded (they are in _EMBED_TYPES), so if
    # filtering happened after a fixed k-fetch they would consume the tight
    # semantic slots (k=3/2/1) and then be discarded, starving the 💡 Context
    # channel (Phase 1.4c). Over-fetching below restores the channel separation.
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
        """A semantic hit qualifies as advisory context only when it is not a
        governance message, not an escalation, and not superseded."""
        if msg.get("id", "") in governance_ids:
            return False
        if msg.get("type", "") == "escalation":
            return False
        if msg.get("superseded_by"):
            return False
        return True

    # --- Semantic (or recency) search for each enabled board ----------------
    # Over-fetch, then filter down to the per-board budget k: governance,
    # escalation, and superseded rows must not consume context slots.
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
                # Pure recency fallback when both FTS and embeddings are unavailable.
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
            # Relevance gate: drop weak SEMANTIC matches. Keyword/recency hits carry no
            # _distance and are kept (they matched query terms, or are the fallback).
            dist = row.get("_distance")
            if dist is not None and dist > _SEMANTIC_MAX_DISTANCE:
                continue
            seen_ids.add(row_id)
            context_msgs.append(row)
            kept += 1
            if kept >= k:
                break

    # --- HYDRATE channel: context_refs from the task (§5.1) -----------------
    # Only runs when task_id is provided — otherwise byte-identical to today.
    hydrate_lines: list[str] = []
    hydrate_count = 0
    if task_id is not None:
        try:
            task_row = conn.execute(
                "SELECT context_refs, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
                (task_id,),
            ).fetchone()
            if task_row is not None:
                refs_raw = task_row["context_refs"]
                task_scope = task_row["scope"] or topic
                if refs_raw:
                    try:
                        refs = (
                            json.loads(refs_raw)
                            if isinstance(refs_raw, str)
                            else refs_raw
                        )
                    except (json.JSONDecodeError, TypeError):
                        refs = []
                    if refs:
                        from pathly_orchestrator.runner.hydrate import (
                            hydrate_section as _hydrate,
                        )

                        for ref in refs:
                            try:
                                art = ref.get("artifact", "")
                                anc = ref.get("anchor")
                                if not art:
                                    continue
                                hydrate_count += 1
                                result = _hydrate(
                                    conn,
                                    scope=task_scope,
                                    artifact=art,
                                    anchor=anc,
                                    project_root=project_root,
                                )
                                if result.get("status") == 200:
                                    body = result["body"]
                                    anchor_label = f" §{anc}" if anc else ""
                                    hydrate_lines.append(f"**{art}{anchor_label}**")
                                    if body.get("heading"):
                                        hydrate_lines.append(f"_{body['heading']}_")
                                    hydrate_lines.append("")
                                    hydrate_lines.append(body.get("text", ""))
                                    hydrate_lines.append("")
                                else:
                                    anchor_label = f" §{anc}" if anc else ""
                                    hydrate_lines.append(
                                        f"- ⚠ {art}{anchor_label} — section not found"
                                    )
                            except Exception:
                                logger.debug(
                                    "hydrate_section failed for ref %r",
                                    ref,
                                    exc_info=True,
                                )
                                art = ref.get("artifact", "?")
                                anc = ref.get("anchor")
                                anchor_label = f" §{anc}" if anc else ""
                                hydrate_lines.append(
                                    f"- ⚠ {art}{anchor_label} — hydration error (skipped)"
                                )
        except Exception:
            logger.debug("comms_context: task_id hydration failed", exc_info=True)

    # --- CATALOG channel: index-first pull affordance (Solution A) ----------
    # Scoped to the agent's PRIMARY board (feature > project > global, the order
    # enabled_boards was built in) so the URL it is handed is already permission-
    # bounded and it cannot enumerate another board's artifacts. Omitted when the
    # catalog is empty so the block stays byte-identical on artifact-free boards.
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

    # Nothing to show
    if (
        not decisions
        and not escalations
        and not context_msgs
        and not hydrate_lines
        and not catalog_lines
    ):
        return ""

    # --- Build two-channel markdown block ------------------------------------
    lines: list[str] = ["## Communication Board", ""]

    # Governance channel — always applies, injected deterministically
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

    # Referenced context channel — authoritative manifest for this task (§5.1)
    if hydrate_lines:
        lines.append("### 📎 Referenced context (authoritative for this task)")
        lines.append(
            "Full section text from the task's context_refs. Read `text`, not `summary`."
        )
        lines.append("")
        lines.extend(hydrate_lines)
        lines.append("---")
        lines.append("")

    # Semantic / context channel — labeled as advisory
    if context_msgs:
        lines.append("### 💡 Context (possibly relevant — verify before acting)")
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
            # Token budget: stop once the channel body would exceed the cap, so a large
            # board can't bloat the prompt (the k-cap bounds count; this bounds size).
            if used + len(entry) > _CONTEXT_CHAR_BUDGET and shown > 0:
                lines.append(
                    f"  • … ({len(context_msgs) - shown} more match(es) omitted — budget)"
                )
                break
            lines.append(entry)
            used += len(entry)
            shown += 1

    # Catalog channel — index-first pull affordance (advisory, opt-in pull)
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

    Single-agent, loop-executor, and ``/comms/run`` agents call this so they see
    the SAME governance + memory the FSM/team path already injects. It resolves
    the user's per-feature "Reads" selection (the ``board_scope`` toggle set from
    Studio) and delegates to :func:`retrieve_board_context`:

    * Feature board → the stored toggle is honoured (turning a tier off here drops
      it from every agent's prompt).
    * Project / global board run → only that tier (plus global) is pulled, since
      there is no feature topic.

    Returns ``''`` on any failure so callers never break the prompt.
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
