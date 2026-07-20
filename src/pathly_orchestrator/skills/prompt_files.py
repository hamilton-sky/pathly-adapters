"""System-prompts as MARKDOWN FILES — the user-authored preset layer.

Historically ``kind='preset'`` prompts lived in the ``prompt_library`` DB table. They are
now FILES, mirroring layer-3 abilities (``skills/abilities.py``) exactly — so a system-prompt
is browsable in the Library, **openable/editable in the MD editor**, ``##``-splittable, and
git-trackable, instead of an opaque DB row.

Two scopes, mirroring the rest of Pathly:

    <project_root>/pathly/prompts/<category>/<name>.md   project-scoped (git-trackable)
    ~/.pathly/prompts/<category>/<name>.md               global (cross-project)

A project prompt OVERRIDES a global one with the same ``<category>/<name>``.

The row shape is kept BYTE-COMPATIBLE with the old DB rows (``id``/``kind``/``category``/
``name``/``label``/``hint``/``body``/``skill_ref``/``source``/``sort_order``) plus ``scope`` +
``path`` — so ``useMergedPresets`` (the analyze/split/comment/diagram dropdowns), the Library,
and the Sections modal all keep working unchanged; the only new thing is ``path`` (which lets
the Library open the file in the MD editor). A prompt's **id is its ``"<category>/<name>"``**.

The app-shipped builtin presets stay CLIENT-side (read-only), exactly as before — this module
owns only the user's own prompts.
"""

from __future__ import annotations

import re
from pathlib import Path

# The canonical system-prompt buckets (mirrors FIXED_CATEGORIES.system in the renderer).
CATEGORIES = ("system", "analyze", "split", "comment", "diagram")

_SEG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$")


def _global_root() -> Path:
    return Path.home() / ".pathly" / "prompts"


def _project_root_dir(project_root: str | None) -> Path | None:
    if not project_root:
        return None
    return Path(project_root) / "pathly" / "prompts"


def _label_of(body: str, name: str) -> str:
    """A prompt's display label: its first ``# `` heading, else the file stem."""
    for line in body.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip() or name
    return name


def _row(category: str, name: str, body: str, scope: str, path: Path) -> dict:
    """Build a DB-row-compatible dict (+ scope/path) for one prompt file."""
    return {
        "id": f"{category}/{name}",
        "project_root": None,
        "kind": "preset",
        "category": category,
        "name": name,
        "label": _label_of(body, name),
        "hint": "",
        "body": body,
        "skill_ref": None,
        "source": "user",
        "sort_order": 0,
        "scope": scope,
        "path": str(path).replace("\\", "/"),
    }


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
            out[f"{cat_dir.name}/{f.stem}"] = _row(cat_dir.name, f.stem, body, scope, f)
    return out


def list_prompt_files(
    project_root: str | None = None, *, category: str | None = None
) -> list[dict]:
    """Every user prompt, global + project merged — a project prompt overrides a global one
    on the same ``<category>/<name>``. Optionally filtered by ``category``. Sorted by id."""
    merged = _scan(_global_root(), "global")
    merged.update(_scan(_project_root_dir(project_root), "project"))
    rows = [merged[k] for k in sorted(merged)]
    if category:
        rows = [r for r in rows if r["category"] == category]
    return rows


def read_prompt_file(prompt_id: str, project_root: str | None = None) -> dict | None:
    """One prompt by its ``<category>/<name>`` id, or None when unknown/malformed."""
    if not prompt_id or not _ID_RE.match(prompt_id):
        return None
    for row in list_prompt_files(project_root):
        if row["id"] == prompt_id:
            return row
    return None


def write_prompt_file(
    category: str,
    name: str,
    body: str,
    *,
    project_root: str | None = None,
    scope: str = "project",
) -> dict | None:
    """Create/overwrite a system-prompt ``.md``.

    ``scope='project'`` writes under ``<project_root>/pathly/prompts/``; ``'global'`` under
    ``~/.pathly/prompts/``. Returns the stored row, or None when the inputs are malformed or the
    target is unresolvable (``scope='project'`` with no ``project_root``).
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
    return read_prompt_file(f"{category}/{name}", project_root)


def delete_prompt_file(
    prompt_id: str, *, project_root: str | None = None, scope: str = "project"
) -> bool:
    """Remove a prompt file. Returns True when a file was deleted."""
    if not prompt_id or not _ID_RE.match(prompt_id):
        return False
    root = _project_root_dir(project_root) if scope == "project" else _global_root()
    if root is None:
        return False
    path = root / f"{prompt_id}.md"
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        pass
    return False


def migrate_db_presets_to_files(conn, project_root: str | None = None) -> int:
    """One-time, idempotent lift of legacy ``kind='preset'`` DB rows into files.

    For each DB preset row visible to this project (global + project), write its body to the
    matching ``.md`` (skipping any file that already exists, so a user edit is never clobbered)
    and then delete the DB row. Runs lazily off the list endpoint; once the table is drained it
    is a cheap no-op SELECT. Never raises — a migration hiccup must not break listing.

    Returns the number of rows migrated.
    """
    try:
        from pathly_orchestrator.db.queries.prompt_library import (
            delete_prompt,
            list_prompts,
        )
    except Exception:
        return 0
    migrated = 0
    try:
        rows = list_prompts(conn, kind="preset", project_root=project_root)
    except Exception:
        return 0
    for r in rows:
        category, name = r.get("category") or "", r.get("name") or ""
        if not _SEG_RE.match(category) or not _SEG_RE.match(name):
            continue
        scope = "global" if not r.get("project_root") else "project"
        # A custom label that the body wouldn't reproduce is preserved as a leading heading.
        body = r.get("body") or ""
        label = (r.get("label") or "").strip()
        if label and label != name and _label_of(body, name) != label:
            body = f"# {label}\n\n{body}"
        root = _project_root_dir(project_root) if scope == "project" else _global_root()
        if root is None:
            continue
        existing = root / category / f"{name}.md"
        try:
            if not existing.is_file():
                if write_prompt_file(
                    category, name, body, project_root=project_root, scope=scope
                ) is None:
                    continue
            delete_prompt(conn, r["id"])
            migrated += 1
        except Exception:
            continue
    return migrated
