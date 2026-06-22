"""Shared constants and helpers for all comms blueprints."""

from __future__ import annotations

import re

_EMBED_TYPES: frozenset[str] = frozenset(
    {"decision", "discovery", "constraint", "warning", "escalation", "artifact"}
)

_PROJECT_WRITERS: frozenset[str] = frozenset(
    {
        "tester",
        "reviewer",
        "explorer",
        "architect",
        "planner",
        "designer",
        "director",
        "human",
    }
)
_GLOBAL_WRITERS: frozenset[str] = frozenset({"director", "human"})

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
