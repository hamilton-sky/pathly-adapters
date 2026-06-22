"""Catalog item and category CRUD endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

bp = Blueprint("catalog", __name__)


@bp.route("/catalog/content", methods=["GET"])
def catalog_content():
    """Return content of a catalog item by abs_path query param."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.catalog_items import (
            read_catalog_item_by_path,
        )

        abs_path = request.args.get("path", "")
        if not abs_path:
            return jsonify({"error": "Missing 'path' query param"}), 400
        conn = get_db()
        item = read_catalog_item_by_path(conn, abs_path)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        return (
            jsonify(
                {
                    "name": item["name"],
                    "content": item.get("content") or "",
                    "abs_path": (item.get("abs_path") or "").replace("\\", "/"),
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("catalog_content error")
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
        from pathly_orchestrator.db.queries.catalog_items import (
            upsert_catalog_item,
            _find_data_root,
            _rel,
        )

        data = request.get_json() or {}
        item_type = data.get("type", "")
        name = (data.get("name") or "").strip()
        category = (data.get("category") or "").strip()
        content = data.get("content") or f"# {name}\n\n"

        if item_type not in ("skill", "agent", "fragment", "template"):
            return jsonify({"error": "type must be skill|agent|fragment|template"}), 400
        if not name:
            return jsonify({"error": "Field 'name' is required"}), 400

        safe_name = _re.sub(r"[^a-z0-9\-_]", "-", name.lower()).strip("-")
        if not safe_name:
            return jsonify({"error": "Invalid name"}), 400

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        core = data_root / "core"
        fragment_dir = (
            (core / "skills" / "fragments" / category)
            if category
            else (core / "skills" / "fragments")
        )
        type_to_dir = {
            "skill": core / "skills" / (category or "custom"),
            "agent": core / "agents",
            "fragment": fragment_dir,
            "template": core / "templates" / (category or "custom"),
        }
        target_dir = type_to_dir[item_type]
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{safe_name}.md"

        if file_path.exists():
            return (
                jsonify({"error": f"Item '{safe_name}' already exists in {category}"}),
                409,
            )

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
        from pathly_orchestrator.db.connection import _get_write_lock

        item_type = request.args.get("type", "")
        name = request.args.get("name", "")
        if not item_type or not name:
            return jsonify({"error": "Query params 'type' and 'name' required"}), 400

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM catalog_items WHERE item_type=? AND name=?",
            (item_type, name),
        ).fetchone()
        if not row:
            return (
                jsonify({"error": f"Item '{name}' of type '{item_type}' not found"}),
                404,
            )

        abs_path = (dict(row).get("abs_path") or "").replace("/", "\\")

        with _get_write_lock(conn):
            conn.execute(
                "DELETE FROM catalog_items WHERE item_type=? AND name=?",
                (item_type, name),
            )
            conn.commit()

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
            return (
                jsonify({"error": "Fields 'oldName' and 'newName' are required"}),
                400,
            )

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

        segments = [
            _re.sub(r"[^a-z0-9\-_]", "-", s.lower()).strip("-") for s in name.split("/")
        ]
        segments = [s for s in segments if s]
        if not segments:
            return jsonify({"error": "Invalid name"}), 400
        safe = "/".join(segments)

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        if item_type == "fragment":
            base = data_root / "core" / "skills" / "fragments"
        elif item_type in ("skill",):
            base = data_root / "core" / "skills"
        else:
            base = data_root / "core" / "templates"
        new_dir = base.joinpath(*segments)
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

        base = (
            data_root
            / "core"
            / ("skills" if item_type in ("skill", "fragment") else "templates")
        )
        cat_dir = base / name

        conn = get_db()
        with _get_write_lock(conn):
            conn.execute(
                "DELETE FROM catalog_items WHERE item_type=? AND category=?",
                (item_type, name),
            )
            conn.commit()

        if cat_dir.exists():
            shutil.rmtree(str(cat_dir), ignore_errors=True)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("delete_category error")
        return jsonify({"error": str(e)}), 500


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
                result[group].append(
                    {
                        "name": item["name"],
                        "description": item.get("description") or "",
                        "category": item.get("category") or "",
                        "path": (item.get("abs_path") or "").replace("\\", "/"),
                    }
                )

        return jsonify(result), 200
    except Exception as e:
        logging.exception("catalog_all error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
