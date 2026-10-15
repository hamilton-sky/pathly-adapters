"""Shared by the proof gates: what each stage role may write, and which window explains a change.

The floor, scope and reviewer gates (build-proof) judge a run's diff, but some changes inside it
are legitimate work of another role: a planner routed a feedback file inside BUILDING edits
``IMPLEMENTATION_PLAN.md``, a reviewer writes ``REVIEW.md``. The supervisor records a
``SPAWN_WINDOW`` event per single-path spawn (``supervisor/spawn_window.py``); these helpers read
them back and answer "may this role write that path" and "did a window by such a role leave the
path as it is now".

Never imports ``supervisor``; ``db`` (and ``eventlog``, which imports it) are imported lazily.
Paths are repo-relative POSIX paths, as git prints them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

from pathly_orchestrator.fsm_compose_tables import _FIX_MODE_ARTIFACT
from pathly_orchestrator.proof import tree

from ._helpers import project_root_of

logger = logging.getLogger("pathly.gates.proof")

# Files the server itself rewrites during a run (DB -> disk exports). A user project may not
# gitignore them, so they show up in a run's diff without any agent having written them.
EXPORT_FILES = frozenset({"STATE.json", "BOARD.json", "EVENTS.jsonl"})

# Roles that own the plan documents: the fix-mode roles plus retro. They may change any file
# directly inside the run's storage dir or its board home.
PLAN_ROLES = frozenset(_FIX_MODE_ARTIFACT) | {"retro"}

# A role's own file inside the storage dir.
_OWN_FILE = {"builder": "VERIFY.md", "reviewer": "REVIEW.md"}

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def storage_rel(storage_path: str | Path) -> str:
    """The storage dir relative to the project root the gates use, as a POSIX path."""
    storage = Path(storage_path)
    try:
        rel = storage.relative_to(project_root_of(storage)).as_posix()
    except ValueError:
        return ""
    return "" if rel == "." else rel


def board_home(storage_path: str | Path) -> str:
    """The repo-relative prefix the run's plan lives under, ending in ``/``.

    ``pathly/features/<feature>/`` for a feature storage dir or anything nested in one (a goal
    run's ``goals/<slug>``), else the storage dir itself (``pathly/plans/<name>/``,
    ``pathly/project/...``). Empty when the storage dir is the project root.
    """
    rel = storage_rel(storage_path)
    parts = rel.split("/") if rel else []
    if len(parts) >= 3 and parts[0] == "pathly" and parts[1] == "features":
        return "pathly/features/%s/" % parts[2]
    return rel + "/" if rel else ""


def stage_writes(storage_path: str | Path, role: str | None) -> Callable[[str], bool]:
    """A predicate: may a spawn of ``role`` change this repo-relative path?

    Every role: ``<storage>/feedback/**``, the server's export files anywhere under
    ``pathly/`` and any ``*.tsbuildinfo``. ``builder`` also ``<storage>/VERIFY.md``,
    ``reviewer`` also ``<storage>/REVIEW.md``. ``po``, ``planner``, ``architect``,
    ``designer`` and ``retro`` also any file directly inside the storage dir or the board home.
    """
    storage = storage_rel(storage_path)
    home = board_home(storage_path).rstrip("/")
    name = (role or "").strip().lower()
    feedback = storage + "/feedback/" if storage else None
    own = storage + "/" + _OWN_FILE[name] if storage and name in _OWN_FILE else None
    plan_dirs = {d for d in (storage, home) if d} if name in PLAN_ROLES else set()

    def may_write(path: str) -> bool:
        folder, _, base = path.rpartition("/")
        if feedback and path.startswith(feedback):
            return True
        if path.startswith("pathly/") and base in EXPORT_FILES:
            return True
        if path.endswith(".tsbuildinfo"):
            return True
        if own is not None and path == own:
            return True
        return folder in plan_dirs

    return may_write


def any_role_writes(storage_path: str | Path) -> Callable[[str], bool]:
    """A predicate: may a spawn of some role change this path, so a window could explain it?"""
    checks = [stage_writes(storage_path, role) for role in PLAN_ROLES | set(_OWN_FILE)]
    return lambda path: any(may_write(path) for may_write in checks)


def windows_since(
    storage_path: str | Path,
    since: str | datetime | None = None,
    roles: Iterable[str] | str | None = None,
) -> list[dict]:
    """``SPAWN_WINDOW`` events of the run with ``ts >= since``, optionally by role, oldest first.

    Times are compared parsed, not as strings: an event ``ts`` is ``%Y-%m-%dT%H:%M:%SZ`` while
    ``since`` stamps are ``isoformat()`` with an offset. An event ``ts`` has whole seconds, so
    ``since`` is cut to its second: a window stamped in that second is kept, one a second or
    more earlier is dropped. Raises ``ValueError`` when ``since`` is not a time.
    """
    from pathly_orchestrator.db.queries.task_proof import instant
    from pathly_orchestrator.eventlog import read_events

    start = None
    if since is not None:
        start = instant(since)
        if start is None:
            raise ValueError("since is not an ISO 8601 time: %r" % (since,))
        start = start.replace(microsecond=0)
    wanted = {roles} if isinstance(roles, str) else set(roles) if roles else None
    kept: list[tuple[datetime, dict]] = []
    for event in read_events(str(storage_path)):
        if event.get("type") != "SPAWN_WINDOW":
            continue
        if wanted is not None and event.get("role") not in wanted:
            continue
        when = instant(event.get("ts"))
        if start is not None and (when is None or when < start):
            continue
        kept.append((when or _EPOCH, event))
    kept.sort(key=lambda pair: pair[0])
    return [event for _, event in kept]


def explained(
    project_root: str | Path,
    path: str,
    now_tree: str | None,
    windows: Iterable[dict],
    storage_path: str | Path,
) -> bool:
    """True when a window whose role may write ``path`` left it at its blob in ``now_tree``.

    The window must have changed the path itself (its before and after blobs differ): a planner
    window that never touched the plan does not excuse a builder edit made before it. A
    deletion matches a deletion (no blob after the window, none now).
    """
    if not now_tree:
        return False
    current = tree.blob(project_root, now_tree, path)
    for window in windows:
        before, after = window.get("before"), window.get("after")
        if not (before and after):
            continue
        if not stage_writes(storage_path, window.get("role"))(path):
            continue
        left = tree.blob(project_root, after, path)
        if left == current and left != tree.blob(project_root, before, path):
            return True
    return False


def floor_enabled() -> bool:
    """The ``floor.enabled`` app setting: on unless it is ``false``, ``0`` or ``off``."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), "floor.enabled", None)
    except Exception:
        logger.warning(
            "floor.enabled could not be read; the floor stays on", exc_info=True
        )
        return True
    if raw is None:
        return True
    return str(raw).strip().lower() not in {"false", "0", "off"}
