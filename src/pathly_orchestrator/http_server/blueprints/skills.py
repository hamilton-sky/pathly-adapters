"""Skills catalog, parse, preview, and export endpoints."""
from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("skills", __name__)


@bp.route("/flows/", methods=["GET"])
@bp.route("/flows", methods=["GET"])
def list_flows():
    """Return all flow definitions as a list."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_definitions
        conn = get_db()
        flows = read_flow_definitions(conn, project_root=None)
        result = [
            {
                "name": f["name"],
                "file_path": (f.get("file_path") or "").replace("\\", "/"),
                "updated_at": f.get("updated_at", ""),
            }
            for f in flows
        ]
        return jsonify(result), 200
    except Exception as e:
        logging.exception("list_flows error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<path:name>", methods=["GET"])
def get_flow(name: str):
    """Return a flow definition by name."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_by_name
        conn = get_db()
        flow = read_flow_by_name(conn, name)
        if not flow:
            return jsonify({"error": f"Flow '{name}' not found"}), 404
        return jsonify({
            "name": flow["name"],
            "flow_yaml": flow["flow_yaml"],
            "file_path": (flow.get("file_path") or "").replace("\\", "/"),
            "updated_at": flow.get("updated_at", ""),
        }), 200
    except Exception as e:
        logging.exception("get_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<path:name>", methods=["PUT"])
def update_flow(name: str):
    """Update a flow's YAML content in DB and write-through to disk."""
    try:
        from pathlib import Path
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_by_name, upsert_flow_definition
        conn = get_db()
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
        flow_yaml = data.get("flow_yaml", "")
        existing = read_flow_by_name(conn, name)
        file_path = (existing.get("file_path") or "") if existing else ""
        upsert_flow_definition(conn, project_root=None, name=name, version="", flow_yaml=flow_yaml, file_path=file_path)
        # Write-through to disk
        if file_path:
            try:
                Path(file_path.replace("/", "\\")).write_text(flow_yaml, encoding="utf-8")
            except Exception:
                pass
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("update_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/content", methods=["GET"])
def catalog_content():
    """Return content of a catalog item by abs_path query param."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import read_catalog_item_by_path
        abs_path = request.args.get("path", "")
        if not abs_path:
            return jsonify({"error": "Missing 'path' query param"}), 400
        conn = get_db()
        item = read_catalog_item_by_path(conn, abs_path)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        return jsonify({
            "name": item["name"],
            "content": item.get("content") or "",
            "abs_path": (item.get("abs_path") or "").replace("\\", "/"),
        }), 200
    except Exception as e:
        logging.exception("catalog_content error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/new", methods=["POST"])
def create_flow():
    """Create a new .flow.yaml file from a name template.
    Body: {"name": "my-flow"}
    Returns: {"name": "my-flow", "file_path": "...", "flow_yaml": "..."}
    """
    try:
        import re as _re
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import upsert_flow_definition, _refresh_flows
        from pathly_orchestrator.db.queries.catalog_items import _find_data_root

        data = request.get_json() or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Field 'name' is required"}), 400
        # Sanitize: lowercase, hyphens only
        name = _re.sub(r"[^a-z0-9\-]", "-", name.lower()).strip("-")
        if not name:
            return jsonify({"error": "Invalid name"}), 400

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        flows_dir = data_root / "core" / "flows"
        flows_dir.mkdir(parents=True, exist_ok=True)
        file_path = flows_dir / f"{name}.flow.yaml"

        if file_path.exists():
            return jsonify({"error": f"Flow '{name}' already exists"}), 409

        flow_yaml = f"""---

---
version: 1
flow: {name}
storage_path: "pathly/plans/{{topic}}/"
states:
  - STORMING
  - PLANNING
  - BUILDING
  - DONE
transitions:
  STORMING:
    - PLANNING
  PLANNING:
    - BUILDING
  BUILDING:
    - DONE
"""
        file_path.write_text(flow_yaml, encoding="utf-8")
        conn = get_db()
        upsert_flow_definition(conn, project_root=None, name=name, version="1",
                               flow_yaml=flow_yaml, file_path=str(file_path).replace("\\", "/"))
        return jsonify({
            "name": name,
            "file_path": str(file_path).replace("\\", "/"),
            "flow_yaml": flow_yaml,
        }), 201
    except Exception as e:
        logging.exception("create_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<path:name>", methods=["DELETE"])
def delete_flow(name: str):
    """Delete a flow from DB and disk."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_by_name
        from pathly_orchestrator.db.connection import _get_write_lock

        conn = get_db()
        flow = read_flow_by_name(conn, name)
        if not flow:
            return jsonify({"error": f"Flow '{name}' not found"}), 404

        # Delete from DB
        with _get_write_lock(conn):
            conn.execute("DELETE FROM flow_definitions WHERE name=? AND project_root IS NULL", (name,))
            conn.commit()

        # Delete from disk
        file_path = (flow.get("file_path") or "").replace("/", "\\")
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("delete_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/item/new", methods=["POST"])
def create_catalog_item():
    """Create a new .md file and index it.
    Body: {"type": "skill", "name": "my-skill", "category": "development", "content": "# My Skill\\n\\n"}
    Returns: {"name": "...", "abs_path": "..."}
    """
    try:
        import re as _re
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import upsert_catalog_item, _find_data_root, _rel

        data = request.get_json() or {}
        item_type = data.get("type", "")
        name = (data.get("name") or "").strip()
        category = (data.get("category") or "").strip()
        content = data.get("content") or f"# {name}\n\n"

        if item_type not in ("skill", "agent", "fragment", "template"):
            return jsonify({"error": "type must be skill|agent|fragment|template"}), 400
        if not name:
            return jsonify({"error": "Field 'name' is required"}), 400

        # Sanitize name
        safe_name = _re.sub(r"[^a-z0-9\-_]", "-", name.lower()).strip("-")
        if not safe_name:
            return jsonify({"error": "Invalid name"}), 400

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        core = data_root / "core"
        fragment_dir = (core / "skills" / "fragments" / category) if category else (core / "skills" / "fragments")
        type_to_dir = {
            "skill":    core / "skills" / (category or "custom"),
            "agent":    core / "agents",
            "fragment": fragment_dir,
            "template": core / "templates" / (category or "custom"),
        }
        target_dir = type_to_dir[item_type]
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{safe_name}.md"

        if file_path.exists():
            return jsonify({"error": f"Item '{safe_name}' already exists in {category}"}), 409

        file_path.write_text(content, encoding="utf-8")
        abs_path = str(file_path).replace("\\", "/")
        rel_path = _rel(file_path, data_root.parent)

        if item_type in ("skill", "template", "fragment"):
            item_name = f"{category}/{safe_name}" if category else safe_name
        else:
            item_name = safe_name

        conn = get_db()
        upsert_catalog_item(
            conn,
            item_type=item_type,
            name=item_name,
            rel_path=rel_path,
            abs_path=abs_path,
            category=category or "",
            description="",
            content=content,
        )
        return jsonify({"name": item_name, "abs_path": abs_path}), 201
    except Exception as e:
        logging.exception("create_catalog_item error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/item", methods=["DELETE"])
def delete_catalog_item():
    """Delete a catalog item by type+name query params.
    Query: ?type=skill&name=development/my-skill
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import read_catalog_item_by_path
        from pathly_orchestrator.db.connection import _get_write_lock

        item_type = request.args.get("type", "")
        name = request.args.get("name", "")
        if not item_type or not name:
            return jsonify({"error": "Query params 'type' and 'name' required"}), 400

        conn = get_db()
        # Find by type+name
        row = conn.execute(
            "SELECT * FROM catalog_items WHERE item_type=? AND name=?", (item_type, name)
        ).fetchone()
        if not row:
            return jsonify({"error": f"Item '{name}' of type '{item_type}' not found"}), 404

        abs_path = (dict(row).get("abs_path") or "").replace("/", "\\")

        # Delete from DB
        with _get_write_lock(conn):
            conn.execute("DELETE FROM catalog_items WHERE item_type=? AND name=?", (item_type, name))
            conn.commit()

        # Delete from disk
        if abs_path:
            try:
                Path(abs_path).unlink(missing_ok=True)
            except Exception:
                pass

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("delete_catalog_item error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/item/move", methods=["POST"])
def move_catalog_item_route():
    """Move a catalog item to a different category.
    Body: {"type": "skill", "name": "development/my-skill", "newCategory": "planning"}
    Returns updated fields: {name, category, abs_path, rel_path}
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import move_catalog_item

        data = request.get_json() or {}
        item_type = data.get("type", "")
        name = (data.get("name") or "").strip()
        new_category = (data.get("newCategory") or "").strip()

        if item_type not in ("skill", "agent", "fragment", "template"):
            return jsonify({"error": "type must be skill|agent|fragment|template"}), 400
        if not name:
            return jsonify({"error": "Field 'name' is required"}), 400

        conn = get_db()
        result = move_catalog_item(conn, item_type, name, new_category)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        logging.exception("move_catalog_item error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/item/rename", methods=["POST"])
def rename_catalog_item_route():
    """Rename a catalog item (same directory, new filename stem).
    Body: {"type": "skill", "name": "development/my-skill", "newName": "better-name"}
    Returns updated fields: {name, abs_path, rel_path}
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import rename_catalog_item

        data = request.get_json() or {}
        item_type = data.get("type", "")
        name = (data.get("name") or "").strip()
        new_name = (data.get("newName") or "").strip()

        if item_type not in ("skill", "agent", "fragment", "template"):
            return jsonify({"error": "type must be skill|agent|fragment|template"}), 400
        if not name or not new_name:
            return jsonify({"error": "Fields 'name' and 'newName' are required"}), 400

        conn = get_db()
        result = rename_catalog_item(conn, item_type, name, new_name)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        logging.exception("rename_catalog_item error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/category/rename", methods=["POST"])
def rename_catalog_category_route():
    """Rename a catalog category directory.
    Body: {"type": "skill", "oldName": "dev", "newName": "development"}
    Returns: {oldName, newName, updatedItems}
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import rename_catalog_category

        data = request.get_json() or {}
        item_type = data.get("type", "skill")
        old_name = (data.get("oldName") or "").strip()
        new_name = (data.get("newName") or "").strip()

        if not old_name or not new_name:
            return jsonify({"error": "Fields 'oldName' and 'newName' are required"}), 400

        conn = get_db()
        result = rename_catalog_category(conn, item_type, old_name, new_name)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        logging.exception("rename_catalog_category error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/category/new", methods=["POST"])
def create_category():
    """Create a new category (subdirectory under skills or templates).
    Body: {"type": "skill", "name": "mycategory"}
    Returns: {"name": "mycategory", "path": "..."}
    """
    try:
        import re as _re
        from pathly_orchestrator.db.queries.catalog_items import _find_data_root

        data = request.get_json() or {}
        item_type = data.get("type", "skill")
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Field 'name' is required"}), 400

        safe = _re.sub(r"[^a-z0-9\-_]", "-", name.lower()).strip("-")
        if not safe:
            return jsonify({"error": "Invalid name"}), 400

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        if item_type == "fragment":
            base = data_root / "core" / "skills" / "fragments"
        elif item_type in ("skill",):
            base = data_root / "core" / "skills"
        else:
            base = data_root / "core" / "templates"
        new_dir = base / safe
        if new_dir.exists():
            return jsonify({"error": f"Category '{safe}' already exists"}), 409

        new_dir.mkdir(parents=True, exist_ok=True)
        (new_dir / ".gitkeep").write_text("", encoding="utf-8")
        return jsonify({"name": safe, "path": str(new_dir).replace("\\", "/")}), 201
    except Exception as e:
        logging.exception("create_category error")
        return jsonify({"error": str(e)}), 500


@bp.route("/catalog/category", methods=["DELETE"])
def delete_category():
    """Delete a category and all items in it.
    Query: ?type=skill&name=mycategory
    """
    try:
        import shutil
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.connection import _get_write_lock
        from pathly_orchestrator.db.queries.catalog_items import _find_data_root

        item_type = request.args.get("type", "skill")
        name = request.args.get("name", "")
        if not name:
            return jsonify({"error": "Query param 'name' required"}), 400

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        base = data_root / "core" / ("skills" if item_type in ("skill", "fragment") else "templates")
        cat_dir = base / name

        # Delete from DB (all items in this category)
        conn = get_db()
        with _get_write_lock(conn):
            conn.execute(
                "DELETE FROM catalog_items WHERE item_type=? AND category=?", (item_type, name)
            )
            conn.commit()

        # Delete from disk
        if cat_dir.exists():
            shutil.rmtree(str(cat_dir), ignore_errors=True)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("delete_category error")
        return jsonify({"error": str(e)}), 500


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
