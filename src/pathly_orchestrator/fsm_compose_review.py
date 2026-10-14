"""The Review packet: what a reviewer's prompt carries instead of the builder's own account.

``build_prompt`` puts :func:`review_packet` in place of the pipeline history block (the
builder's ``AGENT_DONE`` summaries) when the stage's role is ``reviewer``. The packet has the
task text frozen at claim (``claimed_text``), the diff of the last build against the working
tree ``next_action`` snapshotted before it began (``review_base.tree``), and the supervisor's
own notes (``TASK_PROOF`` and ``FLOOR_CHECKED`` events), so the reviewer judges what changed
against what was asked, not against what the builder says it did.

Prompts travel as one argv string and Linux caps a single argument at 128 KiB, so the diff is
clipped to 48 KiB (head and tail) and the task text and the notes are clipped too.

Never raises: a packet that cannot be built becomes a short section saying so.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pathly_orchestrator.proof import tree

logger = logging.getLogger("pathly.review_packet")

DIFF_LIMIT = 48 * 1024
TASK_LIMIT = 16 * 1024
# The heading and fences around the diff count toward its 48 KiB.
_DIFF_OVERHEAD = 512
_CONTEXT_LINES = 3
_MAX_WARNINGS = 20
_WARNING_CHARS = 300
_MARKER_RESERVE = 96

_CHECK_NOTES = {
    "passed": "checks passed",
    "failed": "checks failed",
    "none": "no check block: review its acceptance by reading the code",
    "error": "checks could not be run",
}

_HEADING = "\n## Review packet\n\n"
_INTRO = (
    "Judge this diff against the task. The builder's own account of its work is "
    "deliberately left out.\n"
)


def _unavailable(reason: str) -> str:
    return (
        _HEADING
        + "No review packet for this run: %s. The builder's own account is still "
        "left out. The stage orchestrator runs `git diff HEAD` itself and passes the "
        "output to the reviewer.\n" % reason
    )


def _clip(text: str, limit: int, what: str) -> str:
    """``text`` cut to at most ``limit`` bytes of UTF-8, head and tail, whole lines."""
    raw = text.encode("utf-8", "replace")
    if len(raw) <= limit:
        return text
    budget = limit - _MARKER_RESERVE
    head_size = budget * 2 // 3
    tail_size = budget - head_size
    head = raw[:head_size].decode("utf-8", "ignore")
    cut = head.rfind("\n")
    if cut > 0:
        head = head[: cut + 1]
    tail = raw[len(raw) - tail_size :].decode("utf-8", "ignore")
    cut = tail.find("\n")
    if 0 <= cut < len(tail) - 1:
        tail = tail[cut + 1 :]
    omitted = len(raw) - len(head.encode("utf-8")) - len(tail.encode("utf-8"))
    return "%s\n[... %d bytes of the %s omitted ...]\n%s" % (head, omitted, what, tail)


def _review_base(storage_path: Path) -> dict | None:
    """``review_base`` from the run's state when it holds a tree, else None."""
    try:
        from pathly_orchestrator import eventlog

        state = eventlog.read_state(str(storage_path)) or {}
    except Exception:
        logger.warning("review packet could not read the run state", exc_info=True)
        return None
    base = state.get("review_base")
    if isinstance(base, dict) and isinstance(base.get("tree"), str) and base["tree"]:
        return base
    return None


def _claimed_tasks(
    board: str, scope: str, goal_id: str, since: str | None
) -> list[dict] | None:
    """The tasks claimed since the build began, or None when they cannot be read."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import tasks_claimed_since

        return tasks_claimed_since(
            get_db(), board or "feature", scope or "", goal_id or None, since or ""
        )
    except Exception:
        logger.warning("review packet could not read the claimed tasks", exc_info=True)
        return None


def _events_since(storage_path: Path, since: str | None) -> list[dict] | None:
    """``TASK_PROOF`` and ``FLOOR_CHECKED`` events since the build began, oldest first."""
    try:
        from pathly_orchestrator import eventlog
        from pathly_orchestrator.db.queries.task_proof import instant

        start = instant(since)
        if start is None:
            raise ValueError("review_base.started_at is not a time: %r" % (since,))
        # An event ts has whole seconds, so a stamp in the build's first second still counts.
        start = start.replace(microsecond=0)
        kept = []
        for event in eventlog.read_events(str(storage_path)):
            if event.get("type") not in ("TASK_PROOF", "FLOOR_CHECKED"):
                continue
            when = instant(event.get("ts"))
            if when is not None and when >= start:
                kept.append(event)
        return kept
    except Exception:
        logger.warning("review packet could not read the proof events", exc_info=True)
        return None


def _short(task: dict) -> str:
    return str(task.get("id") or "")[:8]


def _task_section(tasks: list[dict] | None) -> str:
    if tasks is None:
        return (
            "(The tasks claimed during this build could not be read. Judge the diff "
            "against the feature's plan and user stories.)\n"
        )
    if not tasks:
        return (
            "(No task was claimed during this build. Judge the diff against the "
            "feature's plan and user stories.)\n"
        )
    parts = []
    for task in tasks:
        text = task.get("claimed_text") or task.get("text") or ""
        parts.append("#### Task %s\n\n%s\n" % (_short(task), text.strip()))
    return _clip("\n".join(parts), TASK_LIMIT, "task text")


def _diff_section(diff: str | None) -> str:
    if diff is None:
        return (
            "(The diff could not be read: git failed. The stage orchestrator runs "
            "`git diff HEAD` itself and passes the output to the reviewer.)\n"
        )
    if not diff.strip():
        return "(Nothing changed outside `pathly/` during this build.)\n"
    body = _clip(diff, DIFF_LIMIT - _DIFF_OVERHEAD, "diff")
    # A context line of a markdown fence in the diff (" ```") would close a three-backtick
    # fence, so the fence is one backtick longer than any run inside the diff.
    runs = [len(run) for run in re.findall(r"`+", body)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    return "%sdiff\n%s\n%s\n" % (fence, body.rstrip("\n"), fence)


def _notes(tasks: list[dict] | None, events: list[dict] | None) -> str:
    if events is None:
        return "(The supervisor's records could not be read.)\n"
    latest: dict[str, dict] = {}
    for event in events:
        if event.get("type") == "TASK_PROOF":
            latest[str(event.get("task_id"))] = event
    lines = []
    for task in tasks or []:
        event = latest.get(str(task.get("id")))
        if event is not None:
            checks = str(event.get("checks"))
            note = _CHECK_NOTES.get(checks, "checks: %s" % checks)
            lines.append("- Task %s: %s." % (_short(task), note))
    floor = [e for e in events if e.get("type") == "FLOOR_CHECKED"]
    warnings = [str(w) for w in (floor[-1].get("warnings") or [])] if floor else []
    for warning in warnings[:_MAX_WARNINGS]:
        lines.append("- Floor guard warning: %s" % warning[:_WARNING_CHARS])
    if len(warnings) > _MAX_WARNINGS:
        lines.append(
            "- ... and %d more floor guard warnings." % (len(warnings) - _MAX_WARNINGS)
        )
    return "\n".join(lines) + "\n" if lines else "none recorded\n"


def _packet(
    storage_path: Path, project_root: str, board: str, board_scope: str, goal_id: str
) -> str:
    base = _review_base(storage_path)
    if base is None:
        return _unavailable(
            "it has no recorded build base (an interactive run, or git is not available)"
        )
    now = tree.snapshot(project_root)
    if now is None:
        return _unavailable(
            "the project could not be snapshotted (git is not available)"
        )
    started = base.get("started_at")
    diff = tree.diff_text_or_none(
        project_root, base["tree"], now, exclude=["pathly/"], unified=_CONTEXT_LINES
    )
    tasks = _claimed_tasks(board, board_scope, goal_id, started)
    events = _events_since(storage_path, started)
    return (
        _HEADING
        + _INTRO
        + "\n### The task\n\n"
        + _task_section(tasks)
        + "\n### The diff\n"
        + _diff_section(diff)
        + "\n### Supervisor notes\n\n"
        + _notes(tasks, events)
    )


def review_packet(
    storage_path: Path, project_root: str, board: str, board_scope: str, goal_id: str
) -> str:
    """The ``## Review packet`` section for a reviewer's prompt; never raises."""
    try:
        return _packet(storage_path, project_root, board, board_scope, goal_id)
    except Exception:
        logger.warning("the review packet could not be built", exc_info=True)
        return _unavailable("it could not be built (see the server log)")
