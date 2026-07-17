"""Skills read/render endpoints: catalog, parse, preview, compose, summary-format."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import jsonify, request

from ._editor_bp import (
    _SKILL_KEY_RE,
    _SUMMARY_FORMAT_BY_SKILL,
    _read_summary_format,
    bp,
)


@bp.route("/skills/catalog", methods=["GET"])
def skills_catalog():
    """Return the fragment catalog for the skill notebook editor."""
    try:
        from pathly_orchestrator.skill_catalog import read_fragment_catalog
        from importlib.resources import files as _res_files

        core_skills_dir = str(_res_files("pathly_data").joinpath("core/skills"))
        catalog = read_fragment_catalog(core_skills_dir)
        return jsonify(catalog), 200
    except Exception as e:
        logging.exception("skills_catalog error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/composition", methods=["GET"])
def skills_composition():
    """Return every manifest skill's effective fragment list + the full fragment catalog.

    Merges per-project DB overrides over the packaged composition.yaml (never writes it)
    so the Skill Composition panel can show which skills are overridden and what fragments
    are available to toggle. ``source`` is ``"override"`` when a DB row exists for that skill.
    """
    try:
        from pathly_orchestrator.compose import (
            load_manifest,
            load_effective_manifest,
            _known_fragments,
            _entry_parts,
        )
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.skill_composition import (
            get_composition_overrides,
        )

        project_root = (request.args.get("project_root") or "").strip() or None

        base = load_manifest()
        effective = load_effective_manifest(project_root)
        fragments_dir = base.get("fragments_dir", "fragments")
        all_fragments = sorted(_known_fragments(fragments_dir))

        try:
            overrides = get_composition_overrides(get_db(project_root), project_root)
        except Exception:
            overrides = {}

        skills_out: dict[str, dict] = {}
        for skill_key, spec in (effective.get("skills") or {}).items():
            frag_names = []
            for entry in (spec or {}).get("fragments") or []:
                try:
                    name, _requires = _entry_parts(entry)
                except ValueError:
                    continue
                frag_names.append(name)
            skills_out[skill_key] = {
                "fragments": frag_names,
                "source": "override" if skill_key in overrides else "manifest",
            }

        return jsonify({"skills": skills_out, "all_fragments": all_fragments}), 200
    except Exception as e:
        logging.exception("skills_composition error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/parse", methods=["POST"])
def skills_parse():
    """Parse a skill .md file into body cells and fragment cells."""
    try:
        import uuid as _uuid
        import yaml as _yaml
        from pathly_orchestrator.skill_parser import parse_skill_document

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill_path = data.get("skill_path", "")
        if not isinstance(skill_path, str) or not skill_path.strip():
            return (
                jsonify({"error": "Field 'skill_path' must be a non-empty string"}),
                400,
            )

        document = parse_skill_document(skill_path)
        cells = document["body_cells"]
        frontmatter = document["frontmatter"]

        normalized = skill_path.replace("\\", "/")
        marker = "core/skills/"
        idx = normalized.find(marker)
        if idx != -1:
            rel = normalized[idx + len(marker) :]
        else:
            rel = normalized.split("/")[-1]
        composition_key = rel.removesuffix(".md")

        fragment_cells: list[dict] = []
        skills_dir_idx = normalized.find(marker)
        if skills_dir_idx != -1:
            skills_dir = normalized[: skills_dir_idx + len(marker)]
            composition_path = skills_dir + "composition.yaml"
            try:
                with open(composition_path, encoding="utf-8") as f:
                    comp = _yaml.safe_load(f)
                skill_entry = (comp.get("skills") or {}).get(composition_key)
                override = None
                try:
                    from pathly_orchestrator.db import get_db
                    from pathly_orchestrator.db.queries.skill_composition import (
                        get_composition_overrides,
                    )

                    _pr = (data.get("project_root") or "").strip() or None
                    override = get_composition_overrides(get_db(_pr), _pr).get(
                        composition_key
                    )
                except Exception:
                    override = None
                if skill_entry or override is not None:
                    fragments_dir = comp.get("fragments_dir") or "fragments"
                    defaults = comp.get("defaults") or []
                    effective_frags = (
                        override
                        if override is not None
                        else list((skill_entry or {}).get("fragments") or [])
                    )
                    all_fragment_names = list(defaults) + list(effective_frags)
                    for frag in all_fragment_names:
                        if isinstance(frag, dict):
                            frag_name = frag.get("name", "")
                        else:
                            frag_name = str(frag)
                        if not frag_name:
                            continue
                        frag_md = f"{skills_dir}{fragments_dir}/{frag_name}.md"
                        description = ""
                        try:
                            with open(frag_md, encoding="utf-8") as f:
                                first_line = f.readline().strip()
                                if first_line.startswith("##"):
                                    description = first_line.lstrip("#").strip()
                        except OSError:
                            pass
                        fragment_cells.append(
                            {
                                "id": str(_uuid.uuid4()),
                                "type": "fragment",
                                "fragmentName": frag_name,
                                "category": "core",
                                "description": description,
                            }
                        )
            except OSError:
                pass

        return (
            jsonify(
                {
                    "body_cells": cells,
                    "fragment_cells": fragment_cells,
                    "composition_key": composition_key,
                    "frontmatter": frontmatter,
                }
            ),
            200,
        )
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "type": "FileNotFoundError"}), 404
    except Exception as e:
        logging.exception("skills_parse error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


def _split_origin_sections(text: str, origin: str) -> list[dict]:
    """Split ``text`` on ``## `` headings into preview sections tagged with ``origin``.

    ``origin`` is the fragment name the text came from (or ``"body"`` for the skill's
    own text) so a client can group sections by which fragment produced them (e.g. the
    Skill Composition panel's fragment chips).
    """
    import re as _re

    parts_list = _re.split(r"(?m)^(## .+)$", text)
    sections: list[dict] = []
    preamble = parts_list[0].strip()
    if preamble:
        sections.append({"heading": "", "content": preamble, "origin": origin})
    for i in range(1, len(parts_list) - 1, 2):
        heading = parts_list[i].strip()
        content = parts_list[i + 1].strip() if i + 1 < len(parts_list) else ""
        sections.append({"heading": heading, "content": content, "origin": origin})
    return sections


@bp.route("/skills/preview", methods=["POST"])
def skills_preview():
    """Preview an assembled skill with live fragment substitution.

    Each section is tagged with the ``origin`` (fragment name, or ``"body"`` for the
    skill's own text) it was split from, computed by injecting + sectioning each part
    independently before concatenating — so a client can isolate one fragment's content.
    """
    try:
        from pathly_orchestrator.compose import compose_skill
        from pathly_orchestrator.fsm_compose import _inject_prompt_vars
        from pathly_orchestrator.skill_parser import serialize_skill_document

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = (data.get("skill") or "").strip()
        cells = data.get("cells", [])
        body_cells_raw = data.get("body_cells", [])
        feature_path = data.get("feature_path", "")

        body_cells_text = ""
        if body_cells_raw:
            body_cells_text = serialize_skill_document("", body_cells_raw).rstrip("\n")

        if not skill and not body_cells_text:
            return jsonify({"error": "Provide 'skill' key or 'body_cells'"}), 400

        fragment_names = [
            c["fragmentName"]
            for c in (cells or [])
            if isinstance(c, dict)
            and c.get("type") == "fragment"
            and c.get("fragmentName")
        ]

        if fragment_names or body_cells_text:
            from pathly_orchestrator.compose import load_manifest, _read_fragment

            manifest = load_manifest()
            fragments_dir = manifest.get("fragments_dir", "fragments")

            if body_cells_text:
                skill_body = body_cells_text
            else:
                try:
                    from pathly_orchestrator.compose import _read_skill_body

                    skill_body = _read_skill_body(skill)
                except Exception:
                    skill_body = ""

            origin_parts: list[tuple[str, str]] = [("body", skill_body.rstrip("\n"))]
            for fname in fragment_names:
                try:
                    origin_parts.append(
                        (fname, _read_fragment(fragments_dir, fname).rstrip("\n"))
                    )
                except Exception:
                    pass
        else:
            from pathly_orchestrator.skills.compose import build_adapter_caps

            origin_parts = [
                (
                    "body",
                    compose_skill(skill, build_adapter_caps("claude")).rstrip("\n"),
                )
            ]

        feature = Path(feature_path).name if feature_path else ""
        project_root = (
            str(Path(feature_path).parent.parent.parent) if feature_path else ""
        )
        agent_role = skill.split("/")[-1] if "/" in skill else skill
        storage_path = Path(feature_path) if feature_path else None

        sections: list[dict] = []
        injected_parts: list[str] = []
        for origin, part_text in origin_parts:
            if not part_text:
                continue
            injected = _inject_prompt_vars(
                part_text,
                feature=feature,
                project_root=project_root,
                agent_role=agent_role,
                storage_path=storage_path,
            )
            injected_parts.append(injected)
            sections.extend(_split_origin_sections(injected, origin))

        assembled = "\n\n".join(injected_parts) + "\n"
        tokens = int(len(assembled.split()) * 1.3)
        return jsonify({"sections": sections, "tokens": tokens}), 200
    except Exception as e:
        logging.exception("skills_preview error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


def _ability_segments(ability_ids: list, project_root: str) -> list:
    """Fetch selected layer-3 ability rows (prompt_library kind='ability') and turn each
    into an 'ability' segment appended after the skill's own fragments. Fail-soft: an
    unknown / non-ability id is skipped, so a bad selection never breaks composition."""
    if not ability_ids:
        return []
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.prompt_library import get_prompt

    conn = get_db(project_root or None)
    out: list = []
    for aid in ability_ids:
        try:
            row = get_prompt(conn, aid)
        except Exception:
            row = None
        if not row or row.get("kind") != "ability":
            continue
        out.append(
            {
                "id": "ability:" + row["name"],
                "kind": "ability",
                "label": row.get("label") or row["name"],
                "text": (row.get("body") or "").rstrip("\n"),
                "source": "ability",
                "optional": True,
                "requires": None,
                "included": True,
                "raw": False,
            }
        )
    return out


@bp.route("/skills/compose", methods=["POST"])
def skills_compose():
    """Compose a skill into one complete, dash-safe prompt for a client-side action."""
    try:
        from pathly_orchestrator.compose import (
            compose_skill_segments,
            load_effective_manifest,
            segments_to_prompt,
        )
        from pathly_orchestrator.fsm_compose import _inject_prompt_vars

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = (data.get("skill") or "").strip()
        if not skill or not _SKILL_KEY_RE.fullmatch(skill):
            return jsonify({"error": "Field 'skill' must be a valid skill key"}), 400

        adapter = (data.get("adapter") or "claude").strip() or "claude"
        goal_id = (data.get("goal_id") or "").strip()
        project_root = (data.get("project_root") or "").strip()
        transform = data.get("transform")
        if not isinstance(transform, dict):
            transform = {}

        # Layer-3 abilities: prompt_library row ids (kind='ability') to append to the skill.
        ability_ids = data.get("ability_ids")
        if not isinstance(ability_ids, list):
            ability_ids = []
        ability_ids = [a for a in ability_ids if isinstance(a, str)]

        manifest = load_effective_manifest(project_root or None)
        composed = skill in (manifest.get("skills") or {})
        try:
            from pathly_orchestrator.skills.compose import build_adapter_caps

            _caps = build_adapter_caps(adapter, goal_id=goal_id)
            extra_segments = _ability_segments(ability_ids, project_root)
            segments = compose_skill_segments(
                skill, _caps, manifest=manifest, extra_segments=extra_segments
            )
        except Exception:
            return jsonify({"error": f"unknown or unreadable skill {skill!r}"}), 404

        feature = (data.get("feature") or "").strip()
        agent_role = (data.get("agent_role") or skill.split("/")[-1]).strip()
        _summary_fmt = _read_summary_format(_SUMMARY_FORMAT_BY_SKILL.get(skill, ""))

        def _apply_subs(text: str) -> str:
            """The same placeholder substitutions, applied to the whole prompt AND to
            each segment's text — so join(segments) stays byte-identical to prompt
            (``_inject_prompt_vars`` + these replaces are all str.replace, distributive
            over the segment boundaries)."""
            text = _inject_prompt_vars(
                text,
                feature=feature,
                project_root=project_root,
                agent_role=agent_role,
            )
            text = (
                text.replace("<source_path>", str(transform.get("source_path") or ""))
                .replace("<out_path>", str(transform.get("out_path") or ""))
                .replace(
                    "<transform_kind>",
                    str(transform.get("kind") or transform.get("transform_kind") or ""),
                )
            )
            if "<summary_format>" in text:
                text = text.replace("<summary_format>", _summary_fmt)
            return text

        segments = [{**s, "text": _apply_subs(s["text"])} for s in segments]
        # Prompt is the join of the (substituted) segments — so selected abilities flow into
        # both; identical to the old compose_skill path when no abilities are selected.
        prompt = segments_to_prompt(segments)
        tokens = int(len(prompt.split()) * 1.3)

        return (
            jsonify(
                {
                    "prompt": prompt,
                    "segments": segments,
                    "tokens": tokens,
                    "skill": skill,
                    "composed": composed,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("skills_compose error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/summary-format/<style>", methods=["GET"])
def skills_summary_format(style: str):
    """Return the output-format contract for a summary DEPTH style."""
    fmt = _read_summary_format(style)
    if not fmt:
        return jsonify({"error": f"unknown summary style {style!r}"}), 404
    return jsonify({"style": style, "format": fmt}), 200
