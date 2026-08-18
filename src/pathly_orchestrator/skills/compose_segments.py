"""Segmented composition — the same assembly as an ordered list of labeled parts.

Split from the string assembler so the HTTP/editor surface that renders "what the agent will
see" cannot drift from what actually runs: ``segments_to_prompt(compose_skill_segments(...))``
is byte-identical to ``compose_skill(...)``, asserted in tests.
"""

from __future__ import annotations

from typing import Any

from .compose_base import _BOARD_DEFAULT_FRAGMENTS, _strip_leading_frontmatter
from .compose_caps import _coerce_caps
from .compose_resources import (
    load_manifest,
    _read_skill_body,
    _read_fragment,
    _entry_parts,
)

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
