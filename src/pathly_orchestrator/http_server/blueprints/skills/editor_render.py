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


@bp.route("/skills/preview", methods=["POST"])
def skills_preview():
    """Preview an assembled skill with live fragment substitution."""
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

            fragment_bodies = []
            for fname in fragment_names:
                try:
                    fragment_bodies.append(
                        _read_fragment(fragments_dir, fname).rstrip("\n")
                    )
                except Exception:
                    pass
            raw_parts = [skill_body.rstrip("\n")] + fragment_bodies
            assembled = "\n\n".join(p for p in raw_parts if p) + "\n"
        else:
            from pathly_orchestrator.skills.compose import build_adapter_caps

            assembled = compose_skill(skill, build_adapter_caps("claude"))

        feature = Path(feature_path).name if feature_path else ""
        project_root = (
            str(Path(feature_path).parent.parent.parent) if feature_path else ""
        )
        agent_role = skill.split("/")[-1] if "/" in skill else skill
        storage_path = Path(feature_path) if feature_path else None
        assembled = _inject_prompt_vars(
            assembled,
            feature=feature,
            project_root=project_root,
            agent_role=agent_role,
            storage_path=storage_path,
        )

        import re as _re

        parts_list = _re.split(r"(?m)^(## .+)$", assembled)
        sections: list[dict] = []
        preamble = parts_list[0].strip()
        if preamble:
            sections.append({"heading": "", "content": preamble, "origin": "body"})
        for i in range(1, len(parts_list) - 1, 2):
            heading = parts_list[i].strip()
            content = parts_list[i + 1].strip() if i + 1 < len(parts_list) else ""
            sections.append({"heading": heading, "content": content, "origin": "body"})

        tokens = int(len(assembled.split()) * 1.3)
        return jsonify({"sections": sections, "tokens": tokens}), 200
    except Exception as e:
        logging.exception("skills_preview error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/compose", methods=["POST"])
def skills_compose():
    """Compose a skill into one complete, dash-safe prompt for a client-side action."""
    try:
        from pathly_orchestrator.compose import compose_skill, load_effective_manifest
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

        manifest = load_effective_manifest(project_root or None)
        composed = skill in (manifest.get("skills") or {})
        try:
            from pathly_orchestrator.skills.compose import build_adapter_caps

            _caps = build_adapter_caps(adapter, goal_id=goal_id)
            prompt = compose_skill(skill, _caps, manifest=manifest)
        except Exception:
            return jsonify({"error": f"unknown or unreadable skill {skill!r}"}), 404

        feature = (data.get("feature") or "").strip()
        agent_role = (data.get("agent_role") or skill.split("/")[-1]).strip()
        prompt = _inject_prompt_vars(
            prompt,
            feature=feature,
            project_root=project_root,
            agent_role=agent_role,
        )

        prompt = (
            prompt.replace("<source_path>", str(transform.get("source_path") or ""))
            .replace("<out_path>", str(transform.get("out_path") or ""))
            .replace(
                "<transform_kind>",
                str(transform.get("kind") or transform.get("transform_kind") or ""),
            )
        )

        if "<summary_format>" in prompt:
            prompt = prompt.replace(
                "<summary_format>",
                _read_summary_format(_SUMMARY_FORMAT_BY_SKILL.get(skill, "")),
            )

        return jsonify({"prompt": prompt, "skill": skill, "composed": composed}), 200
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
