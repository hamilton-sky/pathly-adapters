"""Assemble the HQ context packet: board state -> compact, token-budgeted text.

Read-only: every reader takes a conn and never writes. If the packet cannot be
assembled, HQContextUnavailable is raised (the caller renders the visible
"board context unavailable" note) — a partial packet is never returned.

Ticket: hq-copilot/02. Schema and budget settled in hq-copilot/01.
"""

from __future__ import annotations

import sqlite3
import textwrap
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

ASSEMBLE_TIMEOUT_S = 5.0
DEFAULT_BUDGET_TOKENS = 6000

# Every section a packet can carry. The user picks which go in (Studio's context
# checkboxes); SECTION_DEFAULTS is what a turn carries when nobody chose —
# artifact summaries are opt-in, the largest section and rarely needed.
SECTION_NAMES = ("questions", "runs", "goals", "events", "artifacts", "summaries")
SECTION_DEFAULTS = ("questions", "runs", "goals", "events", "artifacts")

# Section priority per hq.packet_order (ticket 01): attention is the default,
# progress is user-selectable.
_ORDERS = {
    "attention": ("questions", "runs", "goals", "events", "artifacts", "summaries"),
    "progress": ("goals", "runs", "questions", "events", "artifacts", "summaries"),
}


class HQContextUnavailable(Exception):
    """The packet could not be assembled; render the fallback note instead."""


@dataclass
class SectionStatus:
    name: str
    included: bool
    cut_reason: str | None = None
    # Estimated tokens of the section's text: what it took, or would have taken
    # when cut over budget. 0 when it was never read (off / empty / no root).
    tokens: int = 0


@dataclass
class ContextPacket:
    text: str
    tokens_est: int
    sections: list[SectionStatus] = field(default_factory=list)
    budget: int = DEFAULT_BUDGET_TOKENS


def _estimate_tokens(text: str) -> int:
    """chars/4 heuristic (ticket 01, 2d finding: no runtime tokenizer endpoint)."""
    return len(text) // 4


def _packet_order() -> str:
    """Read the hq.packet_order setting via the hq_settings accessor."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.hq_settings import get_hq_packet_order

        order = get_hq_packet_order(get_db())
    except Exception:
        return "attention"
    return order if order in _ORDERS else "attention"


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise HQContextUnavailable("assembly exceeded the 5s deadline")


def _one_line(text: str, width: int = 120) -> str:
    return textwrap.shorten(
        (text or "").replace("\n", " "), width=width, placeholder="..."
    )


def _option_labels(raw: str | None) -> list[str]:
    """Option labels from the stored JSON. Agents post option OBJECTS
    ({id, label, description}); older/test rows hold plain strings. A
    malformed value yields no options rather than failing the packet."""
    import json

    try:
        options = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(options, list):
        return []
    labels = []
    for opt in options:
        if isinstance(opt, dict):
            label = opt.get("label") or opt.get("id")
        else:
            label = opt
        if label is not None and str(label).strip():
            labels.append(_one_line(str(label), 60))
    return labels


def _read_questions(conn: sqlite3.Connection, board_id: str):
    """Pending agent questions, oldest first. Never includes answered ones.

    Each names its goal by title (joined), so the model can tie it to the
    goals section instead of quoting an opaque id."""
    rows = conn.execute(
        "SELECT q.from_agent, q.text, q.options, q.goal_id, g.text AS goal_text "
        "FROM comms_messages q LEFT JOIN comms_messages g ON g.id = q.goal_id "
        "WHERE q.board='feature' AND q.scope=? AND q.type='question' "
        "AND q.deleted_at IS NULL "
        "AND COALESCE(q.status,'pending') != 'answered' "
        "ORDER BY q.ts ASC LIMIT 20",
        (board_id,),
    ).fetchall()
    if not rows:
        return "", ""
    lines = []
    for r in rows:
        labels = _option_labels(r["options"])
        opt = f" (options: {', '.join(labels)})" if labels else ""
        if r["goal_text"]:
            goal = f" [goal: {_one_line(r['goal_text'], 60)}]"
        elif r["goal_id"]:
            goal = f" [goal {r['goal_id'][:8]}]"
        else:
            goal = ""
        lines.append(
            f"- [{r['from_agent']}] \"{_one_line(r['text'], 140)}\"{opt}{goal}"
        )
    return f"## Pending questions ({len(rows)})", "\n".join(lines)


def _read_runs(conn: sqlite3.Connection, board_id: str, project_root: str | None):
    """Live runs first; the most recent finished ones when nothing is live.

    Returns None when there is no project_root to scope the run query — the
    section is then recorded as cut, not empty.
    """
    if not project_root:
        return None
    from pathly_orchestrator.db.queries.run_history_read import (
        get_run_detail,
        list_runs,
    )

    runs = list_runs(conn, project_root, limit=20)
    live = [r for r in runs if not r["finished_at"]]
    # Runs are project-wide (the fleet view), so every line names its board —
    # otherwise another board's run reads as this board's. With nothing live,
    # this board's own recent runs come first.
    on_board = [r for r in runs if _run_board(r) == board_id]
    shown = live[:10] if live else (on_board[:3] or runs[:3])
    if not shown:
        return "", ""
    lines = []
    for r in shown:
        stage = _current_stage(conn, r["run_id"], get_run_detail)
        stage_txt = f", stage: {stage}" if stage else ""
        board = _run_board(r)
        where = "this board" if board == board_id else f"board {board or 'unknown'}"
        lines.append(
            f"- run {r['run_id']} ({r['kind']}/{r['adapter'] or 'unknown'}, "
            f"{where}): {r['status']}{stage_txt}"
        )
    title = (
        f"## Live runs across the project ({len(live)})" if live else "## Recent runs"
    )
    return title, "\n".join(lines)


def _run_board(run: dict) -> str | None:
    return run.get("board_scope") or run.get("feature")


def _current_stage(conn, run_id: str, get_run_detail) -> str | None:
    """Name of the run's current (unfinished) stage, else the last stage."""
    try:
        stages = get_run_detail(conn, run_id).get("stages") or []
    except Exception:
        return None
    current = None
    for s in stages:
        current = s
        if not s.get("finished_at"):
            break
    return (current or {}).get("stage")


def _id_tag(row_id: str, with_ids: bool) -> str:
    """' (id 1a2b3c4d)' — how the operator names a goal or artifact."""
    return f" (id {str(row_id)[:8]})" if with_ids else ""


def _read_goals(conn: sqlite3.Connection, board_id: str, with_ids: bool = False):
    from pathly_orchestrator.db.queries.comms_goals_read import (
        get_goals_with_rollup,
    )

    goals = get_goals_with_rollup(conn, "feature", board_id)
    if not goals:
        return "", ""
    lines = []
    for g in goals:
        t = g["tasks"]
        lines.append(
            f"- {_one_line(g['text'], 100)} — "
            f"{t['done']}/{t['total']} tasks done{_id_tag(g['id'], with_ids)}"
        )
    return f"## Goals ({len(goals)})", "\n".join(lines)


def _read_events(conn: sqlite3.Connection, board_id: str):
    """Newest non-structural messages (goals/tasks/questions have sections)."""
    rows = conn.execute(
        "SELECT type, from_agent, text FROM comms_messages "
        "WHERE board='feature' AND scope=? AND deleted_at IS NULL "
        "AND type NOT IN ('goal','task','question') "
        "ORDER BY ts DESC LIMIT 25",
        (board_id,),
    ).fetchall()
    if not rows:
        return "", ""
    lines = [f"- [{r['type']}] {r['from_agent']}: {_one_line(r['text'])}" for r in rows]
    return f"## Recent events ({len(rows)})", "\n".join(lines)


def _read_artifacts(conn: sqlite3.Connection, board_id: str, with_ids: bool = False):
    """Artifact titles only — never bodies (ticket 01)."""
    rows = conn.execute(
        "SELECT a.id, a.title, a.type FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE m.board='feature' AND m.scope=? AND m.deleted_at IS NULL "
        "ORDER BY a.created_at DESC LIMIT 20",
        (board_id,),
    ).fetchall()
    if not rows:
        return "", ""
    lines = [
        f"- {r['title'] or '(untitled)'} ({r['type'] or 'artifact'})"
        f"{_id_tag(r['id'], with_ids)}"
        for r in rows
    ]
    return f"## Artifacts ({len(rows)})", "\n".join(lines)


def _read_summaries(conn: sqlite3.Connection, board_id: str):
    """One-line AI summaries of the newest artifacts (opt-in section)."""
    rows = conn.execute(
        "SELECT a.title, a.summary FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE m.board='feature' AND m.scope=? AND m.deleted_at IS NULL "
        "AND a.summary IS NOT NULL AND TRIM(a.summary) != '' "
        "ORDER BY a.created_at DESC LIMIT 12",
        (board_id,),
    ).fetchall()
    if not rows:
        return "", ""
    lines = [
        f"- {r['title'] or '(untitled)'}: {_one_line(r['summary'], 280)}" for r in rows
    ]
    return f"## Artifact summaries ({len(rows)})", "\n".join(lines)


def _assemble(
    board_id: str,
    budget_tokens: int,
    project_root: str | None,
    deadline: float,
    selected: set[str],
    with_ids: bool = False,
) -> ContextPacket:
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    order = _ORDERS[_packet_order()]
    readers = {
        "questions": lambda: _read_questions(conn, board_id),
        "runs": lambda: _read_runs(conn, board_id, project_root),
        "goals": lambda: _read_goals(conn, board_id, with_ids),
        "events": lambda: _read_events(conn, board_id),
        "artifacts": lambda: _read_artifacts(conn, board_id, with_ids),
        "summaries": lambda: _read_summaries(conn, board_id),
    }
    parts: list[str] = []
    sections: list[SectionStatus] = []
    used = 0
    over_budget = False
    for name in order:
        if name not in selected:
            sections.append(SectionStatus(name, False, "off"))
            continue
        _check_deadline(deadline)
        try:
            result = readers[name]()
        except Exception as exc:
            raise HQContextUnavailable(f"section '{name}' failed: {exc}") from exc
        if result is None:
            sections.append(SectionStatus(name, False, "no project_root"))
            continue
        title, body = result
        if not body.strip():
            sections.append(SectionStatus(name, False, "empty"))
            continue
        size = _estimate_tokens(title + "\n" + body)
        # Strict priority: once a section misses the budget, everything
        # below it is cut too — no low-priority section may displace a
        # higher one.
        if over_budget:
            sections.append(SectionStatus(name, False, "over budget", size))
            continue
        if used + size > budget_tokens:
            over_budget = True
            sections.append(SectionStatus(name, False, "over budget", size))
            continue
        used += size
        parts.append(f"{title}\n{body}")
        sections.append(SectionStatus(name, True, None, size))
    if parts:
        text = "<pathly-context>\n" + "\n\n".join(parts) + "\n</pathly-context>"
    elif not selected:
        text = (
            "<pathly-context>\n(no board sections selected — the user turned "
            "all board context off)\n</pathly-context>"
        )
    else:
        text = (
            "<pathly-context>\n(board is empty — no goals, runs, "
            "questions or artifacts yet)\n</pathly-context>"
        )
    return ContextPacket(
        text=text,
        tokens_est=_estimate_tokens(text),
        sections=sections,
        budget=budget_tokens,
    )


def assemble_packet(
    board_id: str,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    project_root: str | None = None,
    sections: Iterable[str] | None = None,
    with_ids: bool = False,
) -> ContextPacket:
    """Assemble the token-budgeted context packet for *board_id* (a scope).

    ``sections`` picks which sections go in (names from SECTION_NAMES; unknown
    names are ignored); None means SECTION_DEFAULTS. A section left out is
    recorded with cut_reason "off".

    Sections are added in priority order (ticket 01) and whole sections are
    dropped once the budget is exceeded; every cut is recorded in
    ``packet.sections``. ``project_root`` scopes the live-runs section — when
    omitted, that section is recorded as cut ("no project_root").
    ``with_ids`` adds a short id to each goal and artifact line — operator
    mode, where the model names them in proposed actions.
    """
    selected = (
        set(SECTION_DEFAULTS)
        if sections is None
        else {s for s in sections if s in SECTION_NAMES}
    )
    deadline = time.monotonic() + ASSEMBLE_TIMEOUT_S
    try:
        return _assemble(
            board_id, budget_tokens, project_root, deadline, selected, with_ids
        )
    except HQContextUnavailable:
        raise
    except Exception as exc:
        raise HQContextUnavailable(f"packet assembly failed: {exc}") from exc
