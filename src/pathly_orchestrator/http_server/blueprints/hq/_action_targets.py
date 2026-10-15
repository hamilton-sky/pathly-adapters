"""Resolve an HQ operator proposal against the live board (local-operator 02).

``resolve`` turns ``(action, args)`` into a Target: the card's verb + target
title, the normalized args execution uses (full ids, file paths), and a
*fingerprint* of the state the user saw. ``POST /hq/actions/run`` resolves
again at the click and compares fingerprints — a run that stopped, a goal that
got planned, a diagram that changed since the card was shown makes the card
stale instead of acting on a board the user is no longer looking at.

Read-only. Lazy imports inside functions (layer rule).
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field

_MIN_ID_PREFIX = 6


@dataclass
class Target:
    ok: bool
    title: str = ""
    args: dict = field(default_factory=dict)
    reason: str = ""
    fingerprint: str = ""


def _fail(reason: str) -> Target:
    return Target(False, reason=reason)


def _short(text: str, width: int = 60) -> str:
    one = " ".join((text or "").split())
    return one if len(one) <= width else one[: width - 1] + "…"


# ── runs ───────────────────────────────────────────────────────────────────────


def _find_run(ref: str):
    """``(run_id, state)`` for a registry run (any status, exact id or a unique
    prefix), ``(run_id, None)`` for a board-lock holder, else ``(None, None)``."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.registry import _lock, _registry

    with _lock:
        states = [s for s in _registry.values() if getattr(s, "run_id", "")]
    exact = [s for s in states if s.run_id == ref]
    if exact:
        return ref, exact[0]
    if board_lock.find_by_holder(ref) is not None:
        return ref, None
    if len(ref) >= _MIN_ID_PREFIX:
        prefixed = [s for s in states if s.run_id.startswith(ref)]
        if len(prefixed) == 1:
            return prefixed[0].run_id, prefixed[0]
    return None, None


def _run_label(run_id: str, state) -> str:
    if state is None:
        return f"run {run_id[:12]} (board run)"
    stage = f" · {state.current_state}" if state.current_state else ""
    return f"run {run_id[:12]} ({state.flow}{stage})"


def _run_target(name: str, ref: str) -> Target:
    from ..control._helpers import ACTIVE_STATUSES

    run_id, state = _find_run(ref)
    if run_id is None:
        return _fail(f"no run '{_short(ref, 24)}' on this machine")
    status = state.status if state is not None else "board"
    label = _run_label(run_id, state)
    args = {"run_id": run_id}
    if name in ("pause_run", "resume_run"):
        if state is None:
            return _fail("board and goal runs can't pause or resume — only stop")
        want = "running" if name == "pause_run" else "paused"
        if status != want:
            return _fail(f"{label} is {status}, not {want}")
        verb = "Pause" if name == "pause_run" else "Resume"
        return Target(True, f"{verb} {label}", args, fingerprint=status)
    if name == "stop_run":
        if state is not None and status not in ACTIVE_STATUSES:
            return _fail(f"{label} already ended ({status})")
        return Target(True, f"Stop {label}", args, fingerprint=status)
    # retry_run
    if state is None:
        return _fail("board and goal runs can't be retried here")
    if status in ACTIVE_STATUSES:
        return _fail(f"{label} is still {status}")
    args.update(flow=state.flow, project_root=state.project_root)
    return Target(True, f"Retry {label}", args, fingerprint=status)


# ── goals and artifacts ───────────────────────────────────────────────────────


def _match(rows: list, ref: str, kind: str, text_key: str):
    """One row by id prefix or title (exact, then substring); ambiguity fails."""
    key = ref.strip().rstrip("…").strip().lower()
    if len(key) >= _MIN_ID_PREFIX:
        by_id = [r for r in rows if str(r["id"]).lower().startswith(key)]
        if len(by_id) == 1:
            return by_id[0], None
    titled = [r for r in rows if (r[text_key] or "").strip().lower() == key]
    if not titled:
        titled = [r for r in rows if key and key in (r[text_key] or "").lower()]
    if len(titled) == 1:
        return titled[0], None
    if titled:
        return (
            None,
            f"'{_short(ref, 30)}' matches {len(titled)} {kind}s — name one by id",
        )
    return None, f"no {kind} '{_short(ref, 30)}' on this board"


def _goal_target(conn: sqlite3.Connection, name: str, ref: str, board: str) -> Target:
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.registry import find_active_run_for_goal

    rows = conn.execute(
        "SELECT id, text, executor FROM comms_messages WHERE type='goal' "
        "AND board='feature' AND scope=? AND deleted_at IS NULL",
        (board,),
    ).fetchall()
    goal, err = _match(rows, ref, "goal", "text")
    if goal is None:
        return _fail(err or "goal not found")
    title = f"goal “{_short(goal['text'])}”"
    tasks = conn.execute(
        "SELECT COUNT(*) FROM comms_messages WHERE type='task' AND goal_id=? "
        "AND deleted_at IS NULL",
        (goal["id"],),
    ).fetchone()[0]
    args = {"goal_id": goal["id"]}
    if name == "plan_goal":
        if tasks:
            return _fail(f"{title} already has {tasks} tasks")
        return Target(True, f"Plan {title} (planner)", args, fingerprint="0")
    _topic, live = find_active_run_for_goal(goal["id"], board)
    if live is not None or board_lock.holder("feature", board):
        return _fail(f"{title} or its board is already running")
    executor = goal["executor"] or "single"
    return Target(True, f"Run {title} ({executor})", args, fingerprint=f"{tasks}")


def _artifact_file(path: str, project_root: str | None) -> str:
    if os.path.isabs(path) or not project_root:
        return path
    return os.path.join(project_root, path)


def _latest_diagram(file_path: str):
    try:
        with open(file_path + ".diagrams.json", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    diagrams = data.get("diagrams") if isinstance(data, dict) else None
    good = [
        d
        for d in (diagrams or [])
        if isinstance(d, dict) and isinstance(d.get("id"), str)
    ]
    return good[-1] if good else None


def _artifact_target(
    conn: sqlite3.Connection,
    name: str,
    args: dict,
    board: str,
    project_root: str | None,
) -> Target:
    rows = conn.execute(
        "SELECT a.id, a.path, a.title FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE m.board='feature' AND m.scope=? AND m.deleted_at IS NULL "
        "ORDER BY a.created_at DESC LIMIT 200",
        (board,),
    ).fetchall()
    art, err = _match(rows, args["artifact"], "artifact", "title")
    if art is None:
        return _fail(err or "artifact not found")
    path = _artifact_file(art["path"], project_root)
    title = f"“{_short(art['title'] or os.path.basename(path))}”"
    if not os.path.isfile(path):
        return _fail(f"artifact {title} has no file on disk")
    out = {"artifact_id": art["id"], "path": path, "title": art["title"] or ""}
    if name == "diagram_artifact":
        style = args.get("style")
        out["style"] = style
        return Target(
            True, f"Diagram {title} ({style or 'default style'})", out, fingerprint=path
        )
    latest = _latest_diagram(path)
    if latest is None:
        return _fail(f"{title} has no diagram yet — diagram it first")
    out.update(diagram_id=latest["id"], diagram_title=latest.get("title") or "")
    label = _short(latest.get("title") or latest["id"], 40)
    return Target(
        True,
        f"Add diagram “{label}” of {title} to the board",
        out,
        fingerprint=latest["id"],
    )


# ── entry point ───────────────────────────────────────────────────────────────


def resolve(
    conn: sqlite3.Connection,
    name: str,
    args: dict,
    board: str,
    project_root: str | None,
) -> Target:
    """Resolve validated *args* for catalog action *name* on *board*."""
    if name in ("pause_run", "resume_run", "retry_run", "stop_run"):
        return _run_target(name, args["run_id"])
    if name in ("run_goal", "plan_goal"):
        return _goal_target(conn, name, args["goal"], board)
    if name == "post_note":
        text = args["text"]
        return Target(
            True,
            f"Post a note to {board}: “{_short(text)}”",
            {"text": text},
            fingerprint="",
        )
    if name in ("diagram_artifact", "add_diagram_to_board"):
        return _artifact_target(conn, name, args, board, project_root)
    return _fail(f"unknown action '{name}'")
