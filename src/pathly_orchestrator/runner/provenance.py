"""Per-stage git provenance — what a stage MEASURABLY changed, not what it claims to.

``AGENT_DONE.summary`` is written by the agent itself (the `completion-report` fragment
runs agent-authored Python) — a true self-report, same category as the file-presence gates
`command_gate` closed a hole for. This module answers a different, server-measured
question: as of the moment this stage's spawn reported its result, what does `git` say
actually changed on disk? The server runs the commands itself, from a chokepoint the agent
never touches (``POST /runner/terminal/result``), so nothing the agent writes or omits can
affect the answer.

Deliberately NOT an attempt to isolate ONE stage's incremental delta (that would need a
per-stage baseline snapshot, which `scope_gate`'s `build_baseline` already captures for a
narrower purpose — stale scope-drift detection, not general provenance). With
``pathly.auto_commit`` off by default, changes routinely accumulate across several stages
before a human commits, so "the full working-tree diff from the last commit, as of right
now" is the natural, honest unit here — cumulative, not per-stage-isolated, and stated as
such in the event this writes.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("pathly.provenance")

_GIT_TIMEOUT = 15


def capture_stage_provenance(project_root: str) -> dict | None:
    """Return ``{head_sha, diff_stat, files_changed}`` for *project_root*, or ``None``.

    ``git diff HEAD`` alone would miss a builder's most common act — creating a brand
    new file — since `diff` only covers TRACKED paths; an untracked file never appears
    in it. `scope_gate` (`fsm/gates/scope.py`) already had to learn this the same way,
    so ``diff_stat`` here is diff-stat for tracked changes PLUS an explicit listing of
    untracked paths (from ``git status --porcelain``'s ``??`` lines), and
    ``files_changed`` counts both.

    Returns ``None`` — never raises — when ``project_root`` is not a git repo, git is
    unavailable, or the required commands fail: this is supplementary audit trail, not
    something that may ever block or fail a stage's result callback.
    """
    head_sha = _run(project_root, ["git", "rev-parse", "HEAD"])
    if head_sha is None:
        return None

    diff_stat = _run(project_root, ["git", "diff", "--stat", "HEAD"]) or ""
    name_only = _run(project_root, ["git", "diff", "--name-only", "HEAD"]) or ""
    changed = {
        line.strip()
        for line in name_only.splitlines()
        if line.strip() and not _is_own_storage(line.strip())
    }

    untracked = sorted(
        path
        for line in (
            _run(project_root, ["git", "status", "--porcelain"]) or ""
        ).splitlines()
        if line.startswith("??")
        and (path := line[3:].strip())
        and not _is_own_storage(path)
    )
    if untracked:
        diff_stat = (
            (diff_stat + "\n" if diff_stat else "")
            + "new (untracked):\n"
            + "\n".join(f" {path}" for path in untracked)
        )

    return {
        "head_sha": head_sha,
        "diff_stat": diff_stat,
        "files_changed": len(changed | set(untracked)),
    }


def record_stage_provenance(runner_state, run_id: str) -> None:
    """Capture git provenance for a finished spawn and append it as a ``STAGE_PROVENANCE``
    event — the FULL working-tree diff from HEAD, not a self-report and not isolated to
    this one stage (see module docstring). Best-effort: never raises, never blocks the
    result callback that calls it.
    """
    try:
        info = capture_stage_provenance(runner_state.project_root)
        if info is None:
            return
        from pathly_orchestrator.eventlog import append_event

        from .argv import _storage_path

        storage = _storage_path(
            runner_state.flow, runner_state.project_root, runner_state.topic
        )
        append_event(
            str(storage),
            {
                "type": "STAGE_PROVENANCE",
                "run_id": run_id,
                "stage": runner_state.current_state,
                **info,
            },
        )
    except Exception:
        logger.debug("provenance: record_stage_provenance failed", exc_info=True)


def _is_own_storage(path: str) -> bool:
    """A run's own bookkeeping is not "changed code" — the whole ``pathly/`` tree is
    Pathly's own storage substrate (features/, project/, board-artifacts/, lessons/,
    the legacy plans/, …; see CLAUDE.md's storage layout), never builder-authored code.

    Matches the WHOLE ``pathly/`` prefix, not just ``pathly/features/``/``pathly/plans/``
    (which is as far as `fsm/gates/scope.py::_scope_clean`'s narrower exemption goes):
    when a project's `pathly/` directory has never been committed at all — a brand new
    project's very first feature — git collapses an entirely-untracked tree to its
    SHALLOWEST boundary in `git status --porcelain` (``?? pathly/``, not the deeper
    ``?? pathly/features/<f>/``), so a prefix check narrower than the whole tree would
    miss it on exactly the run it exists to exempt.
    """
    return path == "pathly" or path.startswith("pathly/")


def _run(cwd: str, argv: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("provenance: %s failed: %s", " ".join(argv), exc)
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
