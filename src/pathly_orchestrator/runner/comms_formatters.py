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
