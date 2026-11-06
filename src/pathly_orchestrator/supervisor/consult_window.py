"""What a consult run changed: its answer is withheld when it changed the project (round two, 03).

A consult is read-only: it may write only under its board's ``feedback/`` folder and post board
rows. ``supervisor/consult_run`` does not trust that. It calls :func:`open_window` before the
spawn (the git working tree, ``HEAD`` and the declared ``files`` of every task ``in_progress``
on the project's boards now) and :func:`blamed` after it, the way ``fsm/gates/reviewer.py`` measures a reviewer. A change
is blamed on the consult unless it is under the feedback folder, under Pathly's own ``pathly/``
storage (``runner/provenance._is_own_storage``: the mirror exports and run storage), or inside
the declared ``files`` of a task ``in_progress`` at the window's start, or of a task posted before
the window and claimed during it by another run (a builder running beside the consult; a task the
consult posted or claimed itself exempts nothing). A blamed consult is :func:`withhold`-en: no
answer row, route ``withheld``, the question handed to the person and one escalation listing the
findings. Nothing is reverted. The consult's spawn (:func:`spawn_until_stopped`) returns only
once its process exited, so the window closes after the consult's last write.

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
# Seconds to wait for the consult's process to exit after the spawn returned on its AGENT_DONE.
EXIT_WAIT = 600.0


@dataclass
class Window:
    """The project before the consult's spawn."""

    root: str
    before: str
    head: str | None
    declared: set[str] = field(default_factory=set)
    feedback: str | None = None
    run_id: str = ""
    known: set[str] = field(default_factory=set)


def _on_project_board(root: str, board: str, scope: str | None) -> bool:
    """A board of the project at ``root``: its project board (scope == the normalized root) or
    a feature board whose ``pathly/features/<scope>/`` folder exists under it. The feature path
    is ``board_mirror.board_mirror_path``'s, so a scope that is not one plain folder name (or is
    a reserved one) is no board of this project."""
    from ..board_mirror import _norm_project_root, board_mirror_path

    norm = _norm_project_root(root)
    if not norm or not scope:
        return False
    if board == "project":
        return scope == norm
    mirror = board_mirror_path("feature", scope, norm)
    return mirror is not None and mirror.parent.is_dir()


def _project_tasks(root: str) -> list[dict]:
    """Every live task row on the project's boards: id, status, claimer and files."""
    from ..db.connection import get_db

    rows = (
        get_db()
        .execute(
            "SELECT id, board, scope, files, task_status, claimed_by FROM comms_messages "
            "WHERE type='task' AND deleted_at IS NULL AND board IN ('project', 'feature')"
        )
        .fetchall()
    )
    boards: dict[tuple[str, str], bool] = {}
    tasks = []
    for row in rows:
        key = (row["board"], row["scope"])
        if key not in boards:
            boards[key] = _on_project_board(root, *key)
        if boards[key]:
            tasks.append(dict(row))
    return tasks


def _files_of(tasks: list[dict]) -> set[str]:
    from .task_proof import _declared

    files: set[str] = set()
    for task in tasks:
        files |= _declared({"files": task["files"]})
    return files


def _claimed_by_others(window: Window) -> set[str]:
    """The ``files`` of tasks posted before the window and ``in_progress`` now, claimed by a
    named run other than the consult. A task the consult posted, or claimed, exempts nothing.
    """
    return _files_of(
        [
            t
            for t in _project_tasks(window.root)
            if t["task_status"] == "in_progress"
            and t["id"] in window.known
            and t["claimed_by"]
            and t["claimed_by"] != window.run_id
        ]
    )


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


def open_window(
    project_root: str, *, scope: str | None = None, run_id: str = ""
) -> Window | None:
    """The tree, ``HEAD``, the in-progress declared files and the task ids now; None when git
    cannot snapshot. ``run_id`` is the consult's, whose own claims exempt nothing."""
    try:
        before = tree.snapshot(project_root)
        if before is None:
            return None
        tasks = _project_tasks(str(project_root))
        return Window(
            root=str(project_root),
            before=before,
            head=tree.head(project_root),
            declared=_files_of([t for t in tasks if t["task_status"] == "in_progress"]),
            feedback=_feedback(str(project_root), scope),
            run_id=run_id,
            known={t["id"] for t in tasks},
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
        window.declared |= _claimed_by_others(window)
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


def spawn_until_stopped(state, prompt, adapter, model, run_id, broadcast_fn) -> dict:
    """``terminal._run_stage_via_terminal``, returned only once the consult's process exited.

    With ``PATHLY_RUNNER_EARLY_ADVANCE`` on (the default) the terminal returns on the agent's
    AGENT_DONE while the PTY still runs, and keeps the run registered until the PTY reports its
    exit; every other return drops it first. So a registered run is waited on. Raises when the
    exit is not reported within :data:`EXIT_WAIT`: what the consult changed cannot be measured,
    so its answer is not delivered (the route fails and the question goes to the person).
    """
    from .registry import get_run
    from .terminal import _run_stage_via_terminal

    returned = _run_stage_via_terminal(
        state, prompt, adapter, model, run_id, broadcast_fn
    )
    run = get_run(run_id)
    if run is not None and not run.wait_pty_result(timeout=EXIT_WAIT):
        raise RuntimeError(
            "consult_exit_unconfirmed: its process was not confirmed stopped within "
            f"{EXIT_WAIT:g}s, so what it changed could not be measured"
        )
    return returned


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


def _why_unmeasured(project_root: str) -> str:
    if not tree._is_top(project_root):
        return f"{project_root} is not a git repository top"
    return f"git could not snapshot {project_root}"


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
            text=f"answer not measured: {_why_unmeasured(project_root)}",
            reply_to=question["id"],
        )
    except Exception as exc:
        logger.warning("consult: posting the not-measured status failed: %s", exc)
    return status
