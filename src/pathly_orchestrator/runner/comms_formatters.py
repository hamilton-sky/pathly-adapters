"""Pure formatting helpers and hydration channel builder for comms board context."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

_logger = logging.getLogger(__name__)


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


def _confidence_label(distance: float | None) -> str:
    """Bucket a cosine distance into a legible confidence tag for the Context line.

    Raw MiniLM cosine values aren't intuitively scaled (a 0.42 "sim" can be a decent
    match), so we surface a coarse bucket — NOT a float — that reads cleanly in the
    human /preview audit AND gives the agent a light signal without implying false
    precision. Empty string for keyword/recency hits (no _distance). Thresholds are
    calibrated to the live board: same-board matches ~0.48–0.67, tangential cross-tier
    ~0.68–0.79 (so ≤0.55 = strong, ≤0.70 = moderate, else weak).
    """
    if distance is None:
        return ""
    if distance <= 0.55:
        return "match: strong"
    if distance <= 0.70:
        return "match: moderate"
    return "match: weak"


def _format_decision(msg: dict) -> str:
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
    line = f"- [{header}] {text}"
    matched = (msg.get("_matched_chunk") or "").strip()
    if matched:
        snippet = " ".join(matched.split())
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        line += f"\n    matched topic: {snippet}"
    return line


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


def _collect_hydrate_channel(
    task_id: str | None,
    topic: str,
    project_root: str,
    conn,
) -> tuple[list[str], int]:
    """Build the Referenced context channel from a task's context_refs manifest.

    Returns (lines, count). Lines is empty when task_id is None or no refs found.
    """
    hydrate_lines: list[str] = []
    hydrate_count = 0
    if task_id is None:
        return hydrate_lines, hydrate_count
    try:
        task_row = conn.execute(
            "SELECT context_refs, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
            (task_id,),
        ).fetchone()
        if task_row is None:
            return hydrate_lines, hydrate_count
        refs_raw = task_row["context_refs"]
        task_scope = task_row["scope"] or topic
        if not refs_raw:
            return hydrate_lines, hydrate_count
        try:
            refs = json.loads(refs_raw) if isinstance(refs_raw, str) else refs_raw
        except (json.JSONDecodeError, TypeError):
            refs = []
        if refs:
            from pathly_orchestrator.runner.hydrate import hydrate_section as _hydrate

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
                        # Surface the ACTUAL resolution error (artifact_not_found /
                        # path_out_of_scope / anchor_not_found) rather than a blanket
                        # "section not found" that hides a path-resolution failure.
                        err = (result.get("body") or {}).get("error", "unavailable")
                        hydrate_lines.append(f"- {art}{anchor_label} — {err}")
                except Exception:
                    _logger.debug(
                        "hydrate_section failed for ref %r", ref, exc_info=True
                    )
                    art = ref.get("artifact", "?")
                    anc = ref.get("anchor")
                    anchor_label = f" §{anc}" if anc else ""
                    hydrate_lines.append(
                        f"- {art}{anchor_label} — hydration error (skipped)"
                    )
    except Exception:
        _logger.debug("comms_context: task_id hydration failed", exc_info=True)
    return hydrate_lines, hydrate_count


# Which board's decision wins a conflict: a global decision outranks a project one, and a
# project decision a feature one. The feature board accepts a post from any role, so ranking
# by recency alone let any newer feature-board note outrank an older director or human call.
_TIER_RANK = {"global": 0, "project": 1, "feature": 2}


def render_governance_lines(
    decisions: list[dict], escalations: list[dict]
) -> list[str]:
    """Render the unconditional governance block: active decisions + open escalations.

    Pure formatting — the caller does the retrieval. Returns [] when there is nothing to
    render, so the caller can `lines.extend(...)` unconditionally.
    """
    if not decisions and not escalations:
        return []
    lines: list[str] = []
    lines.append("### Governance (always applies — do not override)")
    lines.append("Active decisions and open escalations injected unconditionally.")
    lines.append("")
    if decisions:
        # NEWEST FIRST, and say so. get_pending_decisions returns ts ASC, and _format_age
        # renders day granularity — so a board whose decisions all landed on one afternoon
        # rendered every bullet as an indistinguishable "13d ago" in oldest-first order.
        # An agent then read "X remains a hard human gate" and "X is resolved, unblocked"
        # as equally-live governance with no way to tell which one won. Ordering is the
        # cheap half of supersession: until `superseded_by` is set (POST /comms/supersede),
        # recency is the only signal the reader has, so make it unmissable.
        ordered = sorted(decisions, key=lambda m: str(m.get("ts") or ""), reverse=True)
        # Stable sort: tier rank first, recency kept within each tier.
        ordered.sort(key=lambda m: _TIER_RANK.get(str(m.get("board") or "feature"), 2))
        lines.append("**Decisions (higher tier first, NEWEST FIRST within a tier):**")
        lines.append(
            "  A global decision outranks a project one, and a project decision a feature "
            "one. Within a tier, if two decisions conflict, the one listed FIRST wins — it "
            "was made later. Do not act on a superseded decision because it appears more "
            "detailed. To replace one, post a decision with `supersedes` naming its id."
        )
        seen_tiers: set[str] = set()
        for msg in ordered:
            tier = msg.get("board", "feature")
            text = msg.get("text", "")
            ts_str = msg.get("ts", "")
            age = _format_age(ts_str) if ts_str else ""
            # Minute-precision stamp alongside the age: same-day decisions are the ones
            # that actually conflict, and "13d ago" cannot order them.
            stamp = ts_str[:16].replace("T", " ") if len(ts_str) >= 16 else ts_str
            marker = "LATEST · " if tier not in seen_tiers else ""
            seen_tiers.add(tier)
            ident = f"id: {msg['id']}" if msg.get("id") else ""
            meta = " · ".join(p for p in (ident, marker + tier, stamp, age) if p)
            lines.append(f"  • {text}  [{meta}]")
    if escalations:
        lines.append("**Open escalations (human input required):**")
        newest_decision_ts = (
            max((str(m.get("ts") or "") for m in decisions), default="")
            if decisions
            else ""
        )
        for msg in escalations:
            tier = msg.get("board", "feature")
            text = msg.get("text", "")
            ts_str = msg.get("ts", "")
            age = _format_age(ts_str) if ts_str else ""
            stamp = ts_str[:16].replace("T", " ") if len(ts_str) >= 16 else ts_str
            meta = " · ".join(p for p in (tier, stamp, age) if p)
            lines.append(f"  • {text}  [{meta}]")
        # An escalation stays status='pending' until a human acknowledges it, so a later
        # agent decision claiming to "resolve" it leaves BOTH on the board — the reader
        # sees "human input required" and "unblocked, start now" at once. Name that
        # collision instead of letting the agent silently pick whichever it read last.
        if newest_decision_ts and newest_decision_ts > max(
            (str(m.get("ts") or "") for m in escalations), default=""
        ):
            lines.append(
                "  NOTE: decisions above are newer than these escalations and may claim to "
                "resolve them. An agent decision does NOT close a human gate — only a human "
                "acknowledgement does. If a decision contradicts an open escalation, treat "
                "the gate as OPEN and say so rather than proceeding."
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def _build_context_entries(context_msgs: list[dict]) -> list[tuple[str, str]]:
    """Render each kept context message as ``(tier, line)`` for the budget pass.

    Split out of ``comms_context`` (which was at the 400-line SOLID limit) rather than
    inlined: this is pure formatting over ``_format_age`` + ``_confidence_label``, both
    of which already live here.

    The tier is read from ``_tier`` — stamped by the per-board search loop, and
    authoritative — falling back to ``board`` only for a row that never went through it.
    """
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
    return entries
