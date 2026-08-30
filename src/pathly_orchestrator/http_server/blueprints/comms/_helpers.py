"""Shared constants and helpers for all comms blueprints."""

from __future__ import annotations

import re

_EMBED_TYPES: frozenset[str] = frozenset(
    {"decision", "discovery", "constraint", "warning", "escalation", "artifact"}
)

# 'evaluator' is included on both non-feature tiers: it only ever runs human-initiated (the
# "Suggest tasks" / auto-eval of a board the human opened), so letting it post to the board it
# was launched on matches intent — and is what stops the scope leak where an evaluate run on a
# project/global board escaped to a feature board named after the scope. Keep this in sync with
# _DEFAULT_WRITE_PERMISSIONS in db/queries/app_settings.py (the live perm_table is built there).
_PROJECT_WRITERS: frozenset[str] = frozenset(
    {
        "builder",
        "tester",
        "reviewer",
        "explorer",
        "architect",
        "planner",
        "designer",
        "research",
        "evaluator",
        "director",
        "human",
    }
)
_GLOBAL_WRITERS: frozenset[str] = frozenset({"director", "evaluator", "human"})

# POST /comms/promote has its OWN gate, deliberately NOT _GLOBAL_WRITERS above.
# `retro` is the pipeline role for the RETRO stage (core/flows/team-build.flow.yaml
# `role_map: RETRO: retro`) whose entire job is capturing lessons — if promotion
# reused the raw global-write gate, the one headless stage designed for
# consolidation would be locked out of the higher boards, reproducing the exact
# "knowledge can never move upward" failure that promotion exists to fix.
# Promoting is safe to allow more widely than raw writing because it is
# CONSTRAINED: it can only copy an EXISTING decision/constraint upward, carrying
# provenance columns back to the source — it can never author new global content.
# Deliberately a fixed set, not perm_table-driven: the settings table describes
# who may AUTHOR on a tier, which is the very question promotion sidesteps.
_PROMOTE_WRITERS: frozenset[str] = frozenset(
    {"director", "evaluator", "human", "retro"}
)

_PATH_RE = re.compile(r"(?:[\w.\-]+[/\\])+[\w.\-]+\.[A-Za-z0-9]{1,8}")

_EXT_ARTIFACT_TYPE: dict[str, str] = {
    "md": "md",
    "markdown": "md",
    "txt": "md",
    "py": "code",
    "ts": "code",
    "tsx": "code",
    "js": "code",
    "jsx": "code",
    "go": "code",
    "rs": "code",
    "java": "code",
    "rb": "code",
    "c": "code",
    "h": "code",
    "cpp": "code",
    "css": "code",
    "html": "code",
    "sh": "code",
    "yaml": "code",
    "yml": "code",
    "toml": "code",
    "json": "json",
    "pdf": "pdf",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "gif": "image",
    "svg": "image",
}


def check_write_permission(
    from_agent: str, board: str, perm_table: dict | None = None
) -> bool:
    """Return True when from_agent is allowed to write to the given board tier."""
    if board == "feature":
        return True
    if perm_table is not None:
        roles = perm_table.get(board)
        if roles is not None:
            return "*" in roles or from_agent in roles
    if board == "project":
        return from_agent in _PROJECT_WRITERS
    if board == "global":
        return from_agent in _GLOBAL_WRITERS
    return False


def check_promote_permission(from_agent: str) -> bool:
    """Return True when *from_agent* may promote a message to a higher tier.

    Separate from ``check_write_permission`` on purpose — see _PROMOTE_WRITERS.
    """
    return from_agent in _PROMOTE_WRITERS


def extract_artifact_path(text: str) -> str | None:
    """Recover a file path mentioned in prose when artifact_path was omitted."""
    if not text:
        return None
    match = _PATH_RE.search(text)
    return match.group(0) if match else None


def guess_artifact_type(path: str) -> str | None:
    """Map a file extension to an artifact_type bucket; None when unrecognized."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _EXT_ARTIFACT_TYPE.get(ext)


def norm_project_root(project_root: str) -> str:
    return project_root.replace("\\", "/").rstrip("/")


def post_task_status(conn, message_id: str, verb: str, reason: str = "") -> None:
    """Post a guaranteed board ``status`` line for a task state transition.

    The SINGLE executor's drain agent transitions each task through
    ``/comms/tasks/{claim,complete,fail}``; this makes each transition emit a
    ``Started`` / ``Done`` / ``Failed`` status on the board, so a headless
    single-agent run shows per-task progress WITHOUT relying on the agent posting
    it. The LOOP executor emits the equivalent supervisor-side via
    ``scheduler._post_task_status`` — the two paths are disjoint (loop claims
    in-process, single via HTTP), so there is no double-post.

    Best-effort: never raises — a status-post failure must not fail the task
    transition. Matches the supervisor's format (Started/Done use text[:110];
    Failed uses text[:80] + reason[:80]).
    """
    try:
        from pathly_orchestrator.db.queries.comms import post_message

        row = conn.execute(
            "SELECT board, scope, text FROM comms_messages "
            "WHERE id=? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        if row is None:
            return
        text = row["text"] or message_id
        if reason:
            line = f"{verb}: {text[:80]} — {reason[:80]}"
        else:
            line = f"{verb}: {text[:110]}"
        post_message(
            conn,
            board=row["board"] or "feature",
            scope=row["scope"] or "",
            from_agent="supervisor",
            type="status",
            text=line,
        )
    except Exception:
        import logging

        logging.getLogger("pathly.http").debug("post_task_status failed", exc_info=True)


def task_duration_seconds(task: dict) -> float | None:
    """Wall-clock seconds from claim to completion for a task row.

    Uses ``completed_at`` (done) or ``failed_at`` (failed) as the end stamp. Returns
    ``None`` when either bound is missing (still pending/in_progress, or a legacy row
    predating the columns). Negative deltas from clock skew clamp to 0.
    """
    from datetime import datetime

    claimed = task.get("claimed_at")
    completed = task.get("completed_at") or task.get("failed_at")
    if not claimed or not completed:
        return None
    try:
        start = datetime.fromisoformat(str(claimed).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
        secs = (end - start).total_seconds()
        return secs if secs > 0 else 0.0
    except Exception:
        return None
