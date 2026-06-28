"""Skills write endpoints: save (to disk+DB) and export (composition override)."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import jsonify, request

from ._editor_bp import _SKILL_KEY_RE, bp


@bp.route("/skills/save", methods=["POST"])
def skills_save():
    """Save skill body cells back to disk and upsert to DB."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.skill_defs import upsert_skill_definition
        from pathly_orchestrator.skill_parser import serialize_skill_document

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill_path = data.get("skill_path", "")
        body_cells = data.get("body_cells", [])
        frontmatter = data.get("frontmatter", "")

        if not isinstance(skill_path, str) or not skill_path.strip():
            return (
                jsonify({"error": "Field 'skill_path' must be a non-empty string"}),
                400,
            )
        if not isinstance(body_cells, list):
            return jsonify({"error": "Field 'body_cells' must be a list"}), 400
        if not isinstance(frontmatter, str):
            frontmatter = ""

        markdown = serialize_skill_document(frontmatter, body_cells)

        Path(skill_path).parent.mkdir(parents=True, exist_ok=True)
        Path(skill_path).write_text(markdown, encoding="utf-8")

        normalized = skill_path.replace("\\", "/")
        marker = "core/skills/"
        idx = normalized.find(marker)
        skill_key = (
            normalized[idx + len(marker):].removesuffix(".md")
            if idx != -1
            else Path(skill_path).stem
        )
        filename = Path(skill_path).name
        natural_language = (
            body_cells[0].get("heading", skill_key) if body_cells else skill_key
        )

        conn = get_db()
        upsert_skill_definition(
            conn,
            project_root=None,
            skill=skill_key,
            filename=filename,
            natural_language=natural_language,
            content=markdown,
        )

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_save error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/export", methods=["PUT"])
def skills_export():
    """Persist a skill's fragment order as a per-project composition override in the DB."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = data.get("skill", "")
        fragment_order = data.get("fragment_order", [])
        if not isinstance(skill, str) or not skill.strip():
            return jsonify({"error": "Field 'skill' must be a non-empty string"}), 400
        if not isinstance(fragment_order, list) or not all(
            isinstance(x, str) for x in fragment_order
        ):
            return (
                jsonify({"error": "Field 'fragment_order' must be a list of strings"}),
                400,
            )
        if not _SKILL_KEY_RE.fullmatch(skill):
            return (
                jsonify(
                    {
                        "error": "Field 'skill' must be a skill name like 'team/build', not a path"
                    }
                ),
                400,
            )

        project_root = (data.get("project_root") or "").strip() or None
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.skill_composition import (
            set_composition_override,
        )

        set_composition_override(
            get_db(project_root), project_root, skill, fragment_order
        )
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_export error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
