"""Skills catalog, parse, preview, and export endpoints."""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("skills", __name__)


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


@bp.route("/catalog/all", methods=["GET"])
def catalog_all():
    """Return all catalog items grouped by type.

    Response:
      {
        "agents":    [{"name", "description", "category", "path"}],
        "fragments": [...],
        "skills":    [...],
        "templates": [...]
      }
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import read_all_catalog_items

        conn = get_db()
        items = read_all_catalog_items(conn)

        result: dict = {"agents": [], "fragments": [], "skills": [], "templates": []}
        type_to_key = {
            "agent": "agents",
            "fragment": "fragments",
            "skill": "skills",
            "template": "templates",
        }
        for item in items:
            group = type_to_key.get(item.get("item_type", ""))
            if group:
                result[group].append({
                    "name":        item["name"],
                    "description": item.get("description") or "",
                    "category":    item.get("category") or "",
                    "path":        (item.get("abs_path") or "").replace("\\", "/"),
                })

        return jsonify(result), 200
    except Exception as e:
        logging.exception("catalog_all error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/parse", methods=["POST"])
def skills_parse():
    """Parse a skill .md file into body cells and fragment cells.

    Body: {"skill_path": "src/pathly_data/core/skills/team/build.md"}
    Returns: {"body_cells": [...], "fragment_cells": [...], "composition_key": "team/build"}
    """
    try:
        import uuid as _uuid
        import yaml as _yaml
        from pathly_orchestrator.skill_parser import parse_skill_body

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill_path = data.get("skill_path", "")
        if not isinstance(skill_path, str) or not skill_path.strip():
            return jsonify({"error": "Field 'skill_path' must be a non-empty string"}), 400

        cells = parse_skill_body(skill_path)

        # Derive composition_key from path: strip leading dirs down to team/build form
        # Normalize slashes and strip any known prefix to arrive at skill name
        normalized = skill_path.replace("\\", "/")
        # Remove everything up to and including "core/skills/"
        marker = "core/skills/"
        idx = normalized.find(marker)
        if idx != -1:
            rel = normalized[idx + len(marker):]
        else:
            rel = normalized.split("/")[-1]
        composition_key = rel.removesuffix(".md")

        # Load fragment cells from composition.yaml if the skill is listed there
        fragment_cells: list[dict] = []
        skills_dir_idx = normalized.find(marker)
        if skills_dir_idx != -1:
            skills_dir = normalized[: skills_dir_idx + len(marker)]
            composition_path = skills_dir + "composition.yaml"
            try:
                with open(composition_path, encoding="utf-8") as f:
                    comp = _yaml.safe_load(f)
                skill_entry = (comp.get("skills") or {}).get(composition_key)
                if skill_entry:
                    fragments_dir = (comp.get("fragments_dir") or "fragments")
                    defaults = comp.get("defaults") or []
                    all_fragment_names = list(defaults) + list(skill_entry.get("fragments") or [])
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
                        fragment_cells.append({
                            "id": str(_uuid.uuid4()),
                            "type": "fragment",
                            "fragmentName": frag_name,
                            "category": "core",
                            "description": description,
                        })
            except OSError:
                pass

        return jsonify({"body_cells": cells, "fragment_cells": fragment_cells, "composition_key": composition_key}), 200
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "type": "FileNotFoundError"}), 404
    except Exception as e:
        logging.exception("skills_parse error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/preview", methods=["POST"])
def skills_preview():
    """Preview an assembled skill with live fragment substitution.

    Body: {
        "skill": "team/build",        # skill key for disk lookup (optional if body_cells given)
        "cells": [...],               # fragment cells [{type:"fragment", fragmentName:...}]
        "body_cells": [...],          # live body cells [{heading, content}] from the notebook editor
        "feature_path": "pathly/plans/foo"
    }
    Returns: {"sections": [{heading, content, origin}], "tokens": int}
    """
    try:
        from pathly_orchestrator.compose import compose_skill
        from pathly_orchestrator.fsm_ops import _inject_prompt_vars

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = (data.get("skill") or "").strip()
        cells = data.get("cells", [])
        body_cells_raw = data.get("body_cells", [])
        feature_path = data.get("feature_path", "")

        # Build skill body text from live editor body cells (preferred over disk read)
        body_cells_text = ""
        if body_cells_raw:
            parts_bc = []
            for bc in body_cells_raw:
                if not isinstance(bc, dict):
                    continue
                heading = (bc.get("heading") or "").strip()
                content = (bc.get("content") or "").strip()
                if heading:
                    parts_bc.append(f"## {heading}\n\n{content}" if content else f"## {heading}")
                elif content:
                    parts_bc.append(content)
            body_cells_text = "\n\n".join(parts_bc)

        if not skill and not body_cells_text:
            return jsonify({"error": "Provide 'skill' key or 'body_cells'"}), 400

        # Collect fragment names from cells where type == "fragment"
        fragment_names = [
            c["fragmentName"]
            for c in (cells or [])
            if isinstance(c, dict) and c.get("type") == "fragment" and c.get("fragmentName")
        ]

        # Build assembled text: body (live cells or disk) + fragment bodies
        if fragment_names or body_cells_text:
            from pathly_orchestrator.compose import load_manifest, _read_fragment

            manifest = load_manifest()
            fragments_dir = manifest.get("fragments_dir", "fragments")

            # Prefer live body cells; fall back to reading skill from disk
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
                    fragment_bodies.append(_read_fragment(fragments_dir, fname).rstrip("\n"))
                except Exception:
                    pass
            raw_parts = [skill_body.rstrip("\n")] + fragment_bodies
            assembled = "\n\n".join(p for p in raw_parts if p) + "\n"
        else:
            assembled = compose_skill(skill, adapter_caps={"can_spawn": True})

        # Variable substitution
        feature = Path(feature_path).name if feature_path else ""
        project_root = str(Path(feature_path).parent.parent.parent) if feature_path else ""
        agent_role = skill.split("/")[-1] if "/" in skill else skill
        storage_path = Path(feature_path) if feature_path else None
        assembled = _inject_prompt_vars(
            assembled,
            feature=feature,
            project_root=project_root,
            agent_role=agent_role,
            storage_path=storage_path,
        )

        # Split into sections on ## headings
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


@bp.route("/skills/export", methods=["PUT"])
def skills_export():
    """Update composition.yaml with a new fragment_order for a skill.

    Body: {"skill": "team/build", "fragment_order": ["name1", "name2"]}
    Returns: {"ok": True}
    """
    try:
        import yaml
        from importlib.resources import files as _res_files
        from pathlib import Path as _Path

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = data.get("skill", "")
        fragment_order = data.get("fragment_order", [])
        if not isinstance(skill, str) or not skill.strip():
            return jsonify({"error": "Field 'skill' must be a non-empty string"}), 400
        if not isinstance(fragment_order, list):
            return jsonify({"error": "Field 'fragment_order' must be a list"}), 400

        # Locate the composition.yaml file on disk (importlib resources path)
        skills_resource = _res_files("pathly_data").joinpath("core/skills")
        composition_path = _Path(str(skills_resource)) / "composition.yaml"

        with open(composition_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}

        if "skills" not in manifest or manifest["skills"] is None:
            manifest["skills"] = {}
        if skill not in manifest["skills"] or manifest["skills"][skill] is None:
            manifest["skills"][skill] = {}
        manifest["skills"][skill]["fragments"] = fragment_order

        with open(composition_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_export error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
