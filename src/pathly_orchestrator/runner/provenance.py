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

The same module holds the other half of "provenance": who wrote a board row.
``stamp`` / ``system_stamp`` give the three ``comms_messages`` author columns
(role-read-policy, SPEC C1), taken from the caller's run token or the code path, never
from the request body; ``post_system`` is ``post_message`` with the system stamp applied.
"""

from __future__ import annotations

import logging
import subprocess

from ..db.provenance_values import SOURCE_NONE, SOURCE_TOKEN, SYSTEM_AUTHOR

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


def stamp(identity) -> dict:
    """Author columns for a board write made by ``identity`` (a ``CallerIdentity``).

    A live run token whose run has a role gives ``author_role`` / ``author_run_id`` from
    the run it was minted for and ``author_source="token"``, whatever the request body says
    in ``from`` or ``run_id``. Anything else (no token, an unknown or revoked one, a UI
    caller, or a run with no role) is anonymous: no role, no run, ``author_source="none"``.
    A role-less run is logged: ``token`` with no role would pass every role wall, which only
    withholds ``none`` or a named role. The identity is a parameter because
    ``caller_identity`` lives in ``http_server/`` and this layer may not import it.
    """
    if getattr(identity, "kind", None) == "run":
        role = getattr(identity, "role", None)
        if isinstance(role, str) and role.strip():
            return {
                "author_role": role,
                "author_run_id": identity.run_id,
                "author_source": SOURCE_TOKEN,
            }
        logger.warning(
            "run %s has no role: its board write is stamped %r, not %r",
            getattr(identity, "run_id", None),
            SOURCE_NONE,
            SOURCE_TOKEN,
        )
    return {"author_role": None, "author_run_id": None, "author_source": SOURCE_NONE}


def system_stamp() -> dict:
    """Author columns for a row the server itself writes (supervisor, gates, lifecycle).

    A separate function, never chosen from a request field: only server code calls it.
    """
    return dict(SYSTEM_AUTHOR)


def post_system(conn, **fields) -> str:
    """``post_message`` for a row the server composes itself: always stamped ``system``.

    The blueprints that are over the 400-line ratchet import this as ``_post_message``, so
    their call sites need no stamp argument. Passing an ``author_*`` field raises
    ``TypeError``: the stamp is not the caller's to choose.
    """
    from ..db.queries.comms_messages import post_message

    return post_message(conn, **fields, **system_stamp())


def _is_own_storage(path: str) -> bool:
    """A run's own bookkeeping is not "changed code" — the whole ``pathly/`` tree is
    Pathly's own storage substrate (features/, project/, board-artifacts/, lessons/,
    the legacy plans/, …; see CLAUDE.md's storage layout), never builder-authored code.

    Matches the WHOLE ``pathly/`` prefix, wider than `fsm/gates/scope.py`, which under
    ``pathly/`` exempts only what the builder stage may write (``_proof.stage_writes``):
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
