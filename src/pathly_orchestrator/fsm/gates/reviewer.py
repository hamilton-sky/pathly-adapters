"""Reviewer-unchanged gate — ``reviewer_unchanged`` (build-proof).

A reviewer judges the work; it does not edit it. The supervisor records a ``SPAWN_WINDOW`` (the
git working tree and ``HEAD`` before and after) around every single-path spawn, so this gate
does not trust the reviewer's own report: it reads back the windows of the ``reviewer`` role
since the run last entered REVIEWING and fails when one moved ``HEAD`` or changed a path the
reviewer may not write (``_proof.stage_writes``: ``REVIEW.md`` and feedback files).

Only reviewer windows count. A builder fix round also runs inside REVIEWING and may change code.
A window this gate already reported is left out (its ``run_id`` is in an earlier ``GATE_FAILED``
event's ``run_ids``): the gate only runs again once the feedback folder is clear, so a reported
window means a human resolved that checkpoint. Nothing is reverted here; a human decides.

Fail-open on read problems (windows or git unreadable): the gate must not wedge a run on a
hiccup. A moved ``HEAD`` needs no git call, so it still fails.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from pathly_orchestrator.proof import tree

from . import _proof
from ._helpers import gate_failed, gate_skipped, project_root_of

logger = logging.getLogger("pathly.gates.reviewer")

_GATE = "reviewer_unchanged"

# The failure text lists at most this many lines, then a count of the rest.
_MAX_LISTED = 20


def _window_key(window: dict) -> str:
    """What names a window in ``GATE_FAILED.run_ids``: its run id, else its event seq."""
    return str(window.get("run_id") or "seq-%s" % window.get("seq"))


def _last_entered_reviewing(events: list[dict]) -> str | None:
    """The ``ts`` of the newest ``STATE_TRANSITION`` into REVIEWING, or None."""
    for event in reversed(events):
        if event.get("type") == "STATE_TRANSITION" and event.get("to") == "REVIEWING":
            return event.get("ts")
    return None


def _already_reported(events: list[dict]) -> set[str]:
    return {
        str(key)
        for event in events
        if event.get("type") == "GATE_FAILED" and event.get("gate") == _GATE
        for key in event.get("run_ids") or []
    }


def _findings(
    window: dict, root: Path, may_write: Callable[[str], bool]
) -> tuple[list[str], bool]:
    """What one reviewer window did wrong, and whether git could not diff its trees."""
    found: list[str] = []
    head_before, head_after = window.get("head_before"), window.get("head_after")
    if head_before != head_after:
        found.append(
            "HEAD moved from %s to %s (the reviewer committed)"
            % (head_before or "(no commit)", head_after or "(no commit)")
        )
    before, after = window.get("before"), window.get("after")
    if not (before and after):
        return found, False
    diff = tree.changes_or_none(root, before, after)
    if diff is None:
        return found, True
    found += ["%s %s" % (status, path) for status, path in diff if not may_write(path)]
    return found, False


def _failure_text(blamed: list[tuple[dict, list[str]]]) -> str:
    listed: list[str] = []
    for window, found in blamed:
        listed.append("Reviewer run %s:" % _window_key(window))
        listed += ["- " + line for line in found]
    if len(listed) > _MAX_LISTED:
        rest = len(listed) - _MAX_LISTED
        listed = listed[:_MAX_LISTED] + ["- ... and %d more" % rest]
    return "\n".join(
        [
            "Reviewer gate failed: a reviewer spawn changed the project.",
            "",
            "A reviewer must judge the work, not edit it. It may write only `REVIEW.md` "
            "and its feedback files, and it must not commit.",
            "",
            *listed,
            "",
            "Decide for each change whether to keep it or revert it; nothing was reverted "
            "for you. Then delete this file and resume the run.",
            "",
        ]
    )


def check_reviewer_unchanged(
    gate: dict,
    storage_path: Path,
    prev_state: str,
    next_state: str,
    **_: object,
) -> dict | None:
    try:
        from pathly_orchestrator import eventlog

        events = eventlog.read_events(str(storage_path))
        windows = _proof.windows_since(
            storage_path, _last_entered_reviewing(events), roles={"reviewer"}
        )
    except Exception:
        logger.warning("reviewer_unchanged could not read the windows", exc_info=True)
        gate_skipped(storage_path, _GATE, "windows_unreadable")
        return None

    reported = _already_reported(events)
    windows = [w for w in windows if _window_key(w) not in reported]
    if not windows:
        gate_skipped(storage_path, _GATE, "no_reviewer_window")
        return None

    root = project_root_of(storage_path)
    may_write = _proof.stage_writes(storage_path, "reviewer")
    blamed: list[tuple[dict, list[str]]] = []
    unreadable = False
    for window in windows:
        found, failed = _findings(window, root, may_write)
        unreadable = unreadable or failed
        if found:
            blamed.append((window, found))
    if not blamed:
        if unreadable:
            logger.warning("reviewer_unchanged could not diff a reviewer window")
            gate_skipped(storage_path, _GATE, "git_diff_failed")
        return None

    return gate_failed(
        storage_path,
        gate,
        _GATE,
        prev_state,
        next_state,
        _failure_text(blamed),
        extra={"run_ids": [_window_key(window) for window, _ in blamed]},
    )
