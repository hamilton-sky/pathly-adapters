"""What a consult run changed: its answer is withheld when it changed the project (round two, 03).

A consult is read-only: it may write only under its board's ``feedback/`` folder and post board
rows. ``supervisor/consult_run`` does not trust that. It calls :func:`open_window` before the
spawn (the git working tree, ``HEAD`` and the declared ``files`` of every task ``in_progress``
now) and :func:`blamed` after it, the way ``fsm/gates/reviewer.py`` measures a reviewer. A change
is blamed on the consult unless it is under the feedback folder, under Pathly's own ``pathly/``
storage (``runner/provenance._is_own_storage``: the mirror exports and run storage), or inside
the declared ``files`` of a task ``in_progress`` at the window's start or end (a builder running
beside the consult). A blamed consult is :func:`withhold`-en: no answer row, route ``withheld``,
the question handed to the person and one escalation listing the findings. Nothing is reverted.

Fail-open: when git cannot measure (not a repo top, git failed) :func:`blamed` is None and the
answer is delivered with an "answer not measured" status reply (:func:`noted`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pathly_orchestrator.proof import tree

logger = logging.getLogger("pathly.consult_window")

# The escalation lists at most this many findings, then a count of the rest.
_MAX_LISTED = 20


@dataclass
class Window:
    """The project before the consult's spawn."""

    root: str
    before: str
    head: str | None
    declared: set[str] = field(default_factory=set)
    feedback: str | None = None


def _in_progress_files() -> set[str]:
    """The declared ``files`` of every task ``in_progress`` on the boards now."""
    from ..db.connection import get_db
    from .task_proof import _declared

    rows = (
        get_db()
        .execute(
            "SELECT files FROM comms_messages WHERE type='task' "
            "AND task_status='in_progress' AND deleted_at IS NULL"
        )
        .fetchall()
    )
    files: set[str] = set()
    for row in rows:
        files |= _declared({"files": row["files"]})
    return files


def _feedback(root: str, scope: str | None) -> str | None:
    """The board storage's ``feedback/`` folder relative to ``root``, or None."""
    if not scope:
        return None
    from pathlib import Path

    from ..fsm_ops import _resolve_storage_path

    try:
        storage = Path(str(_resolve_storage_path(None, root, scope)))
        return (
            (storage / "feedback")
            .resolve()
            .relative_to(Path(root).resolve())
            .as_posix()
        )
    except (ValueError, OSError):
        return None


def open_window(project_root: str, *, scope: str | None = None) -> Window | None:
    """The tree, ``HEAD`` and in-progress declared files now; None when git cannot snapshot."""
    try:
        before = tree.snapshot(project_root)
        if before is None:
            return None
        return Window(
            root=str(project_root),
            before=before,
            head=tree.head(project_root),
            declared=_in_progress_files(),
            feedback=_feedback(str(project_root), scope),
        )
    except Exception:
        logger.warning(
            "consult window: snapshot of %s failed", project_root, exc_info=True
        )
        return None


def _covered(path: str, entries: set[str]) -> bool:
    return any(path == e or path.startswith(e + "/") for e in entries)


def _may_write(window: Window, path: str) -> bool:
    from ..runner.provenance import _is_own_storage

    if window.feedback and _covered(path, {window.feedback}):
        return True
    return _is_own_storage(path) or _covered(path, window.declared)


def blamed(window: Window | None) -> list[str] | None:
    """What the consult changed that it may not; None when git cannot measure."""
    if window is None:
        return None
    try:
        after = tree.snapshot(window.root)
        head_after = tree.head(window.root)
        if after is None:
            return None
        found: list[str] = []
        if head_after != window.head:
            found.append(
                "HEAD moved from %s to %s"
                % (window.head or "(no commit)", head_after or "(no commit)")
            )
        diff = tree.changes_or_none(window.root, window.before, after)
        if diff is None:
            return found or None
        window.declared |= _in_progress_files()
        found += [
            "%s %s" % (status, path)
            for status, path in diff
            if not _may_write(window, path)
        ]
        return found
    except Exception:
        logger.warning(
            "consult window: measuring %s failed", window.root, exc_info=True
        )
        return None


def _listed(findings: list[str]) -> list[str]:
    listed = ["- " + line for line in findings[:_MAX_LISTED]]
    if len(findings) > _MAX_LISTED:
        listed.append("- ... and %d more" % (len(findings) - _MAX_LISTED))
    return listed


def _escalation_text(role: str, run_id: str, findings: list[str]) -> str:
    return "\n".join(
        [
            f"The {role} consult {run_id} changed the project, so its answer was withheld.",
            "",
            "A consult must answer the question, not edit the work. It may write only under "
            "its board's `feedback/` folder, and it must not commit.",
            "",
            *_listed(findings),
            "",
            "Decide for each change whether to keep it or revert it; nothing was reverted "
            "for you. The question is now yours to answer.",
        ]
    )


def withhold(conn, question: dict, role: str, run_id: str, findings: list[str]) -> str:
    """No answer row: route ``withheld`` (findings in its reason), the question to the person,
    and one escalation to ``human`` listing the findings. Returns the route's status."""
    from ..db.queries.consult_routes import hand_to_person
    from ..runner.provenance import post_system
    from .consult_run import _move, _status

    qid = question["id"]
    reason = "changed the project: " + "; ".join(findings[:_MAX_LISTED])
    if _move(conn, qid, run_id, "running", "withheld", reason):
        hand_to_person(conn, qid, f"the {role} consult changed the project", by=role)
    try:  # the change is in the project whatever the route says now: the person must see it
        post_system(
            conn,
            board=question["board"],
            scope=question["scope"],
            from_agent="system",
            to_agent="human",
            type="escalation",
            text=_escalation_text(role, run_id, findings),
            reply_to=qid,
        )
    except Exception as exc:
        logger.warning("consult %s: posting the escalation failed: %s", run_id, exc)
    return _status(conn, qid)


def noted(
    conn, question: dict, run_id: str, findings, project_root: str, status: str
) -> str:
    """After delivery: an "answer not measured" status reply when git could not measure the
    consult and this consult's answer was posted. Returns ``status``."""
    if findings is not None or status != "answered":
        return status
    if not conn.execute(
        "SELECT 1 FROM comms_messages WHERE reply_to=? AND type='answer' "
        "AND author_run_id=? AND deleted_at IS NULL LIMIT 1",
        (question["id"], run_id),
    ).fetchone():
        return status
    from ..runner.provenance import post_system

    try:
        post_system(
            conn,
            board=question["board"],
            scope=question["scope"],
            from_agent="system",
            type="status",
            text=f"answer not measured: {project_root} is not a git repository top",
            reply_to=question["id"],
        )
    except Exception as exc:
        logger.warning("consult: posting the not-measured status failed: %s", exc)
    return status
