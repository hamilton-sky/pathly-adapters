"""Skill fragment composition — assemble stage skills from reusable fragments.

One resolver serves both skill-delivery modes:
  - runtime:    ``build_prompt()`` composes the runner skill (``team/*``) for the live adapter
  - build-time: ``pathly-setup`` / ``stitch_skill`` composes the installed skill (``development/*``)

The manifest (``core/skills/composition.yaml``) is keyed by the core-skills-relative
skill path without the ``.md`` suffix — e.g. ``team/build``, ``development/build``.

Composition contract:
    assembled = [stage skill body] + [defaults + skill fragments, in declared order]
  - ``defaults`` apply ONLY to skills present in the ``skills:`` map.
  - A skill ABSENT from ``skills:`` is returned raw and unchanged (no fragments, no defaults)
    — UNLESS ``compose_skill`` is called with ``board_default=True`` (the board-run / flow
    paths do this for a genuinely custom skill), in which case the unrecognized skill instead
    composes the ``board_defaults`` bundle (``progress-logging`` + ``comms-post``) so a
    user-created skill run on a board still reads + posts to it. Build-time install and
    editor-preview paths leave ``board_default`` False, preserving the raw contract.
  - A fragment entry is either a bare name (``feedback-protocol``) or an object with a gate
    (``{name: spawn-rules, requires: can_spawn}``); a gated fragment is dropped when the active
    adapter's capability flag is false.
"""

from __future__ import annotations

import re
from importlib.resources import files
from typing import Any

import yaml

# Capabilities a fragment may gate on via ``requires:``. Extend as adapters grow.
_KNOWN_CAPABILITIES = {"can_spawn", "goal_id"}

# Adapters whose ``_meta`` capability flags we can derive caps from.
_KNOWN_ADAPTERS = {"claude", "codex", "copilot", "antigravity"}

# Default board-fragment bundle given to a skill ABSENT from the manifest that is run on a
# board (/comms/run) or in a flow (``board_default=True``). Used only when the manifest has no
# explicit ``board_defaults:`` key. Keeps a custom skill wired to the board: ``comms-post``
# (post artifacts/findings) + ``progress-logging`` (phase telemetry). Board *context* injection
# is separate — it happens at the run level (start_board_run / retrieve_board_context).
_BOARD_DEFAULT_FRAGMENTS = ["progress-logging", "comms-post"]

# A composed prompt must NOT start with ``---``: it is delivered to the CLI via a
# ``-p`` argv token, and an argument starting with ``--`` is parsed as an unknown
# option (e.g. claude: ``error: unknown option '---...'``). Several skill bodies
# begin with ``---\n\n---`` (empty/doubled rule) or real frontmatter (team/team).
_LEADING_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n.*?\n---[ \t]*\n", re.DOTALL)


def _strip_leading_frontmatter(text: str) -> str:
    """Drop a leading YAML-frontmatter / horizontal-rule block from a skill body."""
    if not text.startswith("---"):
        return text
    m = _LEADING_FRONTMATTER_RE.match(text)
    if not m:
        return text
    return text[m.end() :].lstrip("\n")


# ── Resource helpers ────────────────────────────────────────────────────────────


def _skills_root():
    return files("pathly_data").joinpath("core/skills")


def load_manifest() -> dict:
    """Read and parse ``core/skills/composition.yaml`` (the version-controlled default)."""
    text = _skills_root().joinpath("composition.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def load_artifact_manifest() -> dict:
    """Load artifact-manifest.yaml (role->file->gate). Mirrors load_manifest."""
    text = _skills_root().joinpath("artifact-manifest.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def manifest_role_file(role: str, skill: str | None = None) -> tuple[str, str] | None:
    """Resolve (file, gate) for a role, honoring (role, skill) overrides first.

    Returns None when the role has no manifest entry (the allow-list gate).
    """
    m = load_artifact_manifest()
    overrides = m.get("overrides", {}) or {}
    if skill and f"{role}.{skill}" in overrides:
        e = overrides[f"{role}.{skill}"]
        return (e["file"], e["gate"])
    roles = m.get("roles", {}) or {}
    if role in roles:
        e = roles[role]
        return (e["file"], e["gate"])
    return None


def load_effective_manifest(project_root: str | None = None) -> dict:
    """The composition manifest with per-project DB overrides merged over the packaged
    YAML defaults.

    The YAML stays the source of truth; rows in ``skill_composition`` (written by the
    skill editor) replace a skill's ``fragments`` list. **Fail-safe:** any DB error or
    absent override layer returns the pure YAML manifest, so the runner / install path
    never breaks because of this layer. With no overrides the result is identical to
    :func:`load_manifest`.
    """
    base = load_manifest()
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.skill_composition import (
            get_composition_overrides,
        )

        overrides = get_composition_overrides(get_db(project_root), project_root)
    except Exception:
        return base
    if not overrides:
        return base
    merged = dict(base)
    skills = dict(base.get("skills") or {})
    for skill_key, fragments in overrides.items():
        entry = dict(skills.get(skill_key) or {})
        entry["fragments"] = list(fragments)
        skills[skill_key] = entry
    merged["skills"] = skills
    return merged


def _read_skill_body(skill: str) -> str:
    return _skills_root().joinpath(f"{skill}.md").read_text(encoding="utf-8")


def _skill_exists(skill: str) -> bool:
    return _skills_root().joinpath(f"{skill}.md").is_file()


def _read_fragment(fragments_dir: str, name: str) -> str:
    return (
        _skills_root()
        .joinpath(f"{fragments_dir}/{name}.md")
        .read_text(encoding="utf-8")
    )


def _known_fragments(fragments_dir: str) -> set[str]:
    root = _skills_root().joinpath(fragments_dir)
    names: set[str] = set()
    for entry in root.iterdir():
        if entry.name.endswith(".md"):
            names.add(entry.name[:-3])
    return names


def _entry_parts(entry: Any) -> tuple[str, str | None]:
    """Normalize a fragment entry into ``(name, requires)``."""
    if isinstance(entry, str):
        return entry, None
    if isinstance(entry, dict):
        name = entry.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(
                f"composition: fragment object missing a 'name' string: {entry!r}"
            )
        return name, entry.get("requires")
    raise ValueError(
        f"composition: fragment entry must be a string or object, got {entry!r}"
    )


# ── Adapter capabilities ──────────────────────────────────────────────────────


def adapter_caps_for(adapter: str) -> dict:
    """Derive capability flags for an adapter from its ``_meta/*.yaml`` files.

    Currently derives ``can_spawn``: true when any agent meta declares a non-empty
    ``can_spawn`` list. Raises ``ValueError`` for an unknown adapter.
    """
    adapter = adapter or "claude"
    if adapter not in _KNOWN_ADAPTERS:
        raise ValueError(
            f"composition: unknown adapter {adapter!r}; known adapters: {sorted(_KNOWN_ADAPTERS)}"
        )
    meta_dir = files("pathly_data").joinpath(f"adapters/{adapter}/_meta")
    can_spawn = False
    try:
        for entry in meta_dir.iterdir():
            if not entry.name.endswith(".yaml"):
                continue
            try:
                meta = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if meta.get("can_spawn"):
                can_spawn = True
                break
    except (FileNotFoundError, OSError):
        pass
    return {"can_spawn": can_spawn}


def build_adapter_caps(
    adapter: str,
    *,
    goal_id: str = "",
    executor: str = "",
    kind: str = "",
) -> dict:
    """Build a capability dict by merging adapter hardware flags with goal context.

    Extends adapter_caps_for(adapter) with goal-level fields so fragments gated on
    requires:goal_id can be included when a goal run provides a goal_id.
    """
    caps = adapter_caps_for(adapter or "claude")
    caps["goal_id"] = goal_id or ""
    caps["executor"] = executor or ""
    caps["kind"] = kind or ""
    return caps


def _coerce_caps(adapter_caps: Any) -> dict:
    """Accept either a caps dict or an adapter-name string."""
    if adapter_caps is None:
        return {}
    if isinstance(adapter_caps, str):
        return adapter_caps_for(adapter_caps)
    if isinstance(adapter_caps, dict):
        return adapter_caps
    raise ValueError(
        f"composition: adapter_caps must be a dict or adapter-name str, got {type(adapter_caps).__name__}"
    )


# ── Resolver ──────────────────────────────────────────────────────────────────


def resolve_block(
    block_name: str,
    adapter_caps: Any,
    *,
    user_blocks: dict | None = None,
    manifest: dict | None = None,
) -> list[str]:
    """Return the list of fragment bodies for ``block_name`` under the given adapter caps.

    ``user_blocks`` entries take precedence over manifest blocks of the same name.
    Raises ``KeyError`` if ``block_name`` is not found in the merged block map.
    """
    caps = _coerce_caps(adapter_caps)
    if manifest is None:
        manifest = load_manifest()
    merged_blocks = {**manifest.get("blocks", {}), **(user_blocks or {})}
    if block_name not in merged_blocks:
        raise KeyError(block_name)
    fragments_dir = manifest.get("fragments_dir", "fragments")
    result: list[str] = []
    for entry in merged_blocks[block_name]:
        name, requires = _entry_parts(entry)
        if requires and not caps.get(requires):
            continue
        result.append(_read_fragment(fragments_dir, name).rstrip())
    return result


def compose_skill_with_block(
    skill: str,
    block_name: str,
    adapter_caps: Any,
    *,
    user_blocks: dict | None = None,
    manifest: dict | None = None,
) -> str:
    """Return the assembled markdown for ``skill`` with ``block_name`` fragments appended."""
    caps = _coerce_caps(adapter_caps)
    if manifest is None:
        manifest = load_manifest()
    skill_body = _read_skill_body(skill)
    fragment_bodies = resolve_block(
        block_name, caps, user_blocks=user_blocks, manifest=manifest
    )
    parts = [_strip_leading_frontmatter(skill_body).rstrip()] + fragment_bodies
    return "\n\n".join(parts) + "\n"


def _assemble(raw: str, entries: list, caps: dict, fragments_dir: str) -> str:
    """Join a skill body with its resolved fragment bodies (gated entries dropped)."""
    parts = [_strip_leading_frontmatter(raw).rstrip("\n")]
    for entry in entries:
        name, requires = _entry_parts(entry)
        if requires and not caps.get(requires):
            continue  # gated out for this adapter
        parts.append(_read_fragment(fragments_dir, name).rstrip("\n"))
    return "\n\n".join(parts) + "\n"


def compose_skill(
    skill: str,
    adapter_caps: Any,
    *,
    manifest: dict | None = None,
    board_default: bool = False,
) -> str:
    """Return the assembled markdown for ``skill`` under the given adapter caps.

    ``adapter_caps`` may be a caps dict (``{"can_spawn": True}``) or an adapter-name
    string (``"claude"``), which is resolved via :func:`adapter_caps_for`.

    A skill absent from the manifest's ``skills:`` map is returned raw and unchanged,
    preserving current behaviour until it is explicitly converted — UNLESS
    ``board_default=True``, which the board-run / flow paths pass for a genuinely custom
    skill. Then the unrecognized skill composes the ``board_defaults`` bundle
    (:data:`_BOARD_DEFAULT_FRAGMENTS` = ``progress-logging`` + ``comms-post`` when the
    manifest declares no ``board_defaults:`` key) so a user-created skill run on a board
    still posts its artifacts/progress back. Build-time install and editor-preview paths
    leave ``board_default`` False, keeping the raw contract. (Board *context* is injected
    separately at the run level — start_board_run / retrieve_board_context.)
    """
    if manifest is None:
        manifest = load_manifest()
    skills_map = manifest.get("skills") or {}
    raw = _read_skill_body(skill)

    # Non-board callers (install, editor preview) keep the exact raw fast-path — no
    # caps coercion, byte-identical body — for a skill absent from the manifest.
    if skill not in skills_map and not board_default:
        return raw

    caps = _coerce_caps(adapter_caps)
    fragments_dir = manifest.get("fragments_dir", "fragments")

    if skill not in skills_map:
        # board_default=True on an unrecognized (custom) skill: hand it the default board
        # bundle so it connects through fragments like every recognized skill. Falls back to
        # the hardcoded bundle when the manifest omits `board_defaults:`.
        board_frags = manifest.get("board_defaults")
        if board_frags is None:
            board_frags = list(_BOARD_DEFAULT_FRAGMENTS)
        return _assemble(raw, board_frags, caps, fragments_dir)

    spec = skills_map[skill] or {}
    # `no_defaults: true` on a skill opts it out of the global defaults (e.g. progress-logging).
    # Pure client transforms (summarize/analyze/split) are one-shot file derivations with no
    # pipeline phases, so the phase-telemetry default is dead weight in their prompt.
    default_frags = (
        [] if spec.get("no_defaults") else list(manifest.get("defaults") or [])
    )
    entries = default_frags + list(spec.get("fragments") or [])
    return _assemble(raw, entries, caps, fragments_dir)


# ── Segmented composition ──────────────────────────────────────────────────────
#
# ``compose_skill`` returns the assembly as ONE string. ``compose_skill_segments``
# returns the SAME assembly as an ordered list of labeled parts — the skill body plus
# each fragment as its own unit — so a client can (a) show "what the agent will see"
# broken into pieces and (b) toggle optional parts (layer-3 abilities) on/off before a
# run. The two are kept in lockstep: ``segments_to_prompt(compose_skill_segments(...))``
# is byte-identical to ``compose_skill(...)`` (asserted in tests) — segments are the
# source of truth, the string is their join, so the two can never drift.
#
# Segment shape (plain JSON-safe dict, since it crosses the HTTP boundary):
#   id       stable id — "body", or the fragment name
#   kind     "body" | "default" | "fragment" | "ability"
#   label    human label for the UI
#   text     the part's text (body: frontmatter-stripped; fragment: rstripped)
#   source   "skill" | "default" | "fragment" | "board-default" | "ability"
#   optional may the UI toggle it? (platform fragments False; abilities True)
#   requires capability gate name, or None
#   included is it in the joined prompt for THIS adapter? (a gated-out fragment is
#            listed included=False so the UI can grey it, but the joiner skips it)
#   raw      True only for the absent-skill raw passthrough (join returns it verbatim)


def _body_segment(raw: str, *, stripped: bool = True) -> dict:
    """The skill-body segment. ``stripped=False`` is the raw passthrough (absent skill)."""
    text = _strip_leading_frontmatter(raw).rstrip("\n") if stripped else raw
    return {
        "id": "body",
        "kind": "body",
        "label": "skill body",
        "text": text,
        "source": "skill",
        "optional": False,
        "requires": None,
        "included": True,
        "raw": not stripped,
    }


def _fragment_segment(
    name: str,
    requires: str | None,
    caps: dict,
    fragments_dir: str,
    *,
    kind: str,
    source: str,
) -> dict:
    """One fragment as a segment. A gated-out fragment is carried ``included=False``."""
    included = not (requires and not caps.get(requires))
    return {
        "id": name,
        "kind": kind,
        "label": name,
        "text": _read_fragment(fragments_dir, name).rstrip("\n"),
        "source": source,
        "optional": False,
        "requires": requires,
        "included": included,
        "raw": False,
    }


def compose_skill_segments(
    skill: str,
    adapter_caps: Any,
    *,
    manifest: dict | None = None,
    board_default: bool = False,
    extra_segments: list[dict] | None = None,
) -> list[dict]:
    """Return the assembly of ``skill`` as an ordered list of labeled segments.

    Mirrors :func:`compose_skill` branch-for-branch — the raw passthrough for an
    absent non-board skill, the ``board_defaults`` bundle for an absent board skill,
    and the ``defaults + per-skill fragments`` assembly for a manifest skill — but
    yields labeled parts instead of a joined string. ``segments_to_prompt`` of the
    result (with no ``extra_segments``) equals ``compose_skill`` of the same inputs.

    ``extra_segments`` (layer-3 abilities) are appended AFTER the skill's own
    fragments — always server-supplied, never renderer-concatenated. Each must
    already be a segment dict.
    """
    if manifest is None:
        manifest = load_manifest()
    skills_map = manifest.get("skills") or {}
    raw = _read_skill_body(skill)

    # Absent + non-board → raw passthrough (byte-identical to compose_skill's `return raw`).
    if skill not in skills_map and not board_default:
        return [_body_segment(raw, stripped=False)]

    caps = _coerce_caps(adapter_caps)
    fragments_dir = manifest.get("fragments_dir", "fragments")

    if skill not in skills_map:
        board_frags = manifest.get("board_defaults")
        if board_frags is None:
            board_frags = list(_BOARD_DEFAULT_FRAGMENTS)
        segs = [_body_segment(raw)]
        for entry in board_frags:
            name, requires = _entry_parts(entry)
            segs.append(
                _fragment_segment(
                    name,
                    requires,
                    caps,
                    fragments_dir,
                    kind="default",
                    source="board-default",
                )
            )
        return segs + list(extra_segments or [])

    spec = skills_map[skill] or {}
    default_frags = (
        [] if spec.get("no_defaults") else list(manifest.get("defaults") or [])
    )
    segs = [_body_segment(raw)]
    for entry in default_frags:
        name, requires = _entry_parts(entry)
        segs.append(
            _fragment_segment(
                name, requires, caps, fragments_dir, kind="default", source="default"
            )
        )
    for entry in list(spec.get("fragments") or []):
        name, requires = _entry_parts(entry)
        segs.append(
            _fragment_segment(
                name, requires, caps, fragments_dir, kind="fragment", source="fragment"
            )
        )
    return segs + list(extra_segments or [])


def segments_to_prompt(segments: list[dict]) -> str:
    """Join composed segments into the final prompt — the inverse of the split.

    Only ``included`` segments contribute (a gated-out fragment is carried in the list
    for display but never joined). The single raw-passthrough body segment is returned
    verbatim; otherwise parts join with a blank line + a trailing newline, exactly as
    :func:`_assemble`.
    """
    included = [s for s in segments if s.get("included", True)]
    if len(included) == 1 and included[0].get("raw"):
        return included[0]["text"]
    if not included:
        return ""
    return "\n\n".join(s["text"] for s in included) + "\n"


# ── Validator ─────────────────────────────────────────────────────────────────


def validate_composition(manifest: dict | None = None) -> None:
    """Validate the manifest, raising ``ValueError`` on the first problem found.

    Rejects: unknown fragment name, unknown skill name, duplicate include
    (counting defaults), and unknown ``requires:`` capability. A missing fragment
    file referenced by the manifest also fails here.
    """
    if manifest is None:
        manifest = load_manifest()

    fragments_dir = manifest.get("fragments_dir", "fragments")
    known_fragments = _known_fragments(fragments_dir)

    def _check(name: str, where: str) -> None:
        if name not in known_fragments:
            raise ValueError(f"composition: unknown fragment {name!r} in {where}")

    # defaults
    seen_defaults: set[str] = set()
    for entry in manifest.get("defaults") or []:
        name, requires = _entry_parts(entry)
        _check(name, "defaults")
        if requires and requires not in _KNOWN_CAPABILITIES:
            raise ValueError(
                f"composition: unknown capability {requires!r} in defaults"
            )
        if name in seen_defaults:
            raise ValueError(f"composition: duplicate fragment {name!r} in defaults")
        seen_defaults.add(name)

    # board_defaults (optional — absent key falls back to _BOARD_DEFAULT_FRAGMENTS at runtime)
    seen_board_defaults: set[str] = set()
    for entry in manifest.get("board_defaults") or []:
        name, requires = _entry_parts(entry)
        _check(name, "board_defaults")
        if requires and requires not in _KNOWN_CAPABILITIES:
            raise ValueError(
                f"composition: unknown capability {requires!r} in board_defaults"
            )
        if name in seen_board_defaults:
            raise ValueError(
                f"composition: duplicate fragment {name!r} in board_defaults"
            )
        seen_board_defaults.add(name)

    # per-skill
    for skill, spec in (manifest.get("skills") or {}).items():
        if not _skill_exists(skill):
            raise ValueError(
                f"composition: unknown skill {skill!r} (no core/skills/{skill}.md)"
            )
        spec = spec or {}
        seen = set(seen_defaults)
        for entry in spec.get("fragments") or []:
            name, requires = _entry_parts(entry)
            _check(name, f"skill {skill!r}")
            if requires and requires not in _KNOWN_CAPABILITIES:
                raise ValueError(
                    f"composition: unknown capability {requires!r} in skill {skill!r}"
                )
            if name in seen:
                raise ValueError(
                    f"composition: duplicate include {name!r} in skill {skill!r}"
                )
            seen.add(name)

    # blocks (optional — absent key is backward-compatible)
    if "blocks" not in manifest:
        return
    for block_name, entries in manifest["blocks"].items():
        if not isinstance(entries, list):
            raise ValueError(f"blocks[{block_name!r}]: must be a list")
        seen_block: set[str] = set()
        for entry in entries:
            try:
                name, requires = _entry_parts(entry)
            except ValueError as exc:
                raise ValueError(f"blocks[{block_name!r}]: {exc}") from exc
            if name not in known_fragments:
                raise ValueError(f"blocks[{block_name!r}]: unknown fragment {name!r}")
            if requires is not None and requires not in _KNOWN_CAPABILITIES:
                raise ValueError(
                    f"blocks[{block_name!r}]: unknown capability {requires!r}"
                )
            if name in seen_block:
                raise ValueError(f"blocks[{block_name!r}]: duplicate fragment {name!r}")
            seen_block.add(name)
