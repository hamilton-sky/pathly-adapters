"""Layer-3 abilities — user-authored approach/domain packs, stored as MARKDOWN FILES.

An ability is the voluntary "how it approaches THIS task" layer (React-web vs desktop,
TDD-per-task vs at-the-end) — orthogonal to the skill (the task), and distinct from the
un-editable platform fragments (which own board CRUD / progress / completion-report).

They are FILES, not DB rows, and are read at compose time exactly like fragments
(``compose._read_fragment``) — ONE authority, no DB/file duality — so they are browsable in
the Library, editable in the MD editor, ``##``-splittable into per-section toggles, and
git-trackable.

Two scopes, mirroring the rest of Pathly:

    <project_root>/pathly/abilities/<category>/<name>.md   project-scoped (git-trackable)
    ~/.pathly/abilities/<category>/<name>.md               global (cross-project)

A project ability OVERRIDES a global one with the same ``<category>/<name>``.

They must NOT live under ``core/skills/`` — that is packaged data (site-packages for an
installed user; ``pathly-setup --repair`` overwrites Pathly-owned files and ``python -m build``
regenerates the adapters from it), so user content there would be clobbered.

An ability's **id is its ``"<category>/<name>"`` path**.
"""

from __future__ import annotations

import re
from pathlib import Path

# The buckets an ability can belong to — the pipeline roles whose approach it modifies.
CATEGORIES = ("plan", "build", "review", "test")

_SEG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$")


def _global_root() -> Path:
    return Path.home() / ".pathly" / "abilities"


def _project_root_dir(project_root: str | None) -> Path | None:
    if not project_root:
        return None
    return Path(project_root) / "pathly" / "abilities"


def _label_of(body: str, name: str) -> str:
    """An ability's display label: its first ``# `` heading, else the file stem."""
    for line in body.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip() or name
    return name


def _scan(root: Path | None, scope: str) -> dict[str, dict]:
    """Read every ``<category>/<name>.md`` under ``root`` into ``{id: row}``. Never raises."""
    out: dict[str, dict] = {}
    if root is None or not root.is_dir():
        return out
    try:
        cat_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return out
    for cat_dir in cat_dirs:
        try:
            files = sorted(cat_dir.glob("*.md"))
        except OSError:
            continue
        for f in files:
            try:
                body = f.read_text(encoding="utf-8")
            except OSError:
                continue
            aid = f"{cat_dir.name}/{f.stem}"
            out[aid] = {
                "id": aid,
                "category": cat_dir.name,
                "name": f.stem,
                "label": _label_of(body, f.stem),
                "body": body,
                "scope": scope,
                "path": str(f).replace("\\", "/"),
            }
    return out


def list_abilities(project_root: str | None = None) -> list[dict]:
    """Every ability, global + project merged — a project ability overrides a global one on
    the same ``<category>/<name>``. Sorted by id."""
    merged = _scan(_global_root(), "global")
    merged.update(_scan(_project_root_dir(project_root), "project"))
    return [merged[k] for k in sorted(merged)]


def read_ability(ability_id: str, project_root: str | None = None) -> dict | None:
    """One ability by its ``<category>/<name>`` id, or None when unknown/malformed."""
    if not ability_id or not _ID_RE.match(ability_id):
        return None
    for row in list_abilities(project_root):
        if row["id"] == ability_id:
            return row
    return None


def write_ability(
    category: str,
    name: str,
    body: str,
    *,
    project_root: str | None = None,
    scope: str = "project",
) -> dict | None:
    """Create/overwrite an ability ``.md``.

    ``scope='project'`` writes under ``<project_root>/pathly/abilities/``; ``'global'`` under
    ``~/.pathly/abilities/``. Returns the stored row, or None when the inputs are malformed or
    the target is unresolvable (``scope='project'`` with no ``project_root``).
    """
    if not _SEG_RE.match(category or "") or not _SEG_RE.match(name or ""):
        return None
    if not (body or "").strip():
        return None
    root = _project_root_dir(project_root) if scope == "project" else _global_root()
    if root is None:
        return None
    try:
        target_dir = root / category
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / f"{name}.md").write_text(
            body if body.endswith("\n") else body + "\n", encoding="utf-8"
        )
    except OSError:
        return None
    return read_ability(f"{category}/{name}", project_root)


def delete_ability(
    ability_id: str, *, project_root: str | None = None, scope: str = "project"
) -> bool:
    """Remove an ability file. Returns True when a file was deleted."""
    if not ability_id or not _ID_RE.match(ability_id):
        return False
    root = _project_root_dir(project_root) if scope == "project" else _global_root()
    if root is None:
        return False
    path = root / f"{ability_id}.md"
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        pass
    return False


def ability_segments(ability_ids: list, project_root: str | None = None) -> list[dict]:
    """Turn selected ability ids into compose ``ability`` segments, appended AFTER a skill's
    own fragments (``compose_skill_segments(extra_segments=…)``).

    Fail-soft: an unknown id is skipped, so a stale selection never breaks composition. The
    ONE place both the /skills/compose route and supervisor/board_run build these, so the
    preview and the spawn can never disagree.
    """
    if not ability_ids:
        return []
    by_id = {r["id"]: r for r in list_abilities(project_root)}
    out: list[dict] = []
    for aid in ability_ids:
        row = by_id.get(aid)
        if not row:
            continue
        out.append(
            {
                "id": "ability:" + row["id"],
                "kind": "ability",
                "label": row["label"],
                "text": (row["body"] or "").rstrip("\n"),
                "source": "ability",
                "optional": True,
                "requires": None,
                "included": True,
                "raw": False,
            }
        )
    return out
