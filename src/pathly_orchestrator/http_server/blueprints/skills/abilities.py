"""Layer-3 ability endpoints — user-authored approach packs stored as .md FILES.

    GET    /skills/abilities?project_root=              list (global + project merged)
    POST   /skills/abilities                            create / overwrite one
    DELETE /skills/abilities/<category>/<name>?scope=   remove one

Abilities are files (see ``skills/abilities.py``), not prompt_library rows — so they're
browsable in the Library, editable in the MD editor, ``##``-splittable, and git-trackable.
``prompt_library`` remains the store for kind='preset' (the dropdown alternatives).
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from ._editor_bp import bp


@bp.route("/skills/abilities", methods=["GET"])
def skills_abilities_list():
    """List abilities (global + project merged; project wins on a shared id)."""
    try:
        from pathly_orchestrator.skills.abilities import CATEGORIES, list_abilities

        project_root = (request.args.get("project_root") or "").strip() or None
        return (
            jsonify(
                {
                    "abilities": list_abilities(project_root),
                    "categories": list(CATEGORIES),
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("skills_abilities_list error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/abilities", methods=["POST"])
def skills_abilities_create():
    """Create/overwrite an ability .md. Returns the stored row."""
    try:
        from pathly_orchestrator.skills.abilities import write_ability

        data = request.get_json() or {}
        category = (data.get("category") or "").strip()
        name = (data.get("name") or "").strip()
        body = data.get("body") or ""
        scope = (data.get("scope") or "project").strip()
        project_root = (data.get("project_root") or "").strip() or None
        if scope not in ("project", "global"):
            return jsonify({"error": f"invalid scope {scope!r}"}), 400
        row = write_ability(
            category, name, body, project_root=project_root, scope=scope
        )
        if row is None:
            return (
                jsonify(
                    {
                        "error": "category + name must be alphanumeric/-/_ and body non-empty; "
                        "scope='project' also needs project_root"
                    }
                ),
                400,
            )
        return jsonify({"ability": row}), 200
    except Exception as e:
        logging.exception("skills_abilities_create error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/abilities/<category>/<name>", methods=["DELETE"])
def skills_abilities_delete(category: str, name: str):
    """Remove an ability .md by its <category>/<name> id."""
    try:
        from pathly_orchestrator.skills.abilities import delete_ability

        scope = (request.args.get("scope") or "project").strip()
        project_root = (request.args.get("project_root") or "").strip() or None
        if not delete_ability(
            f"{category}/{name}", project_root=project_root, scope=scope
        ):
            return jsonify({"error": f"no ability {category}/{name}"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_abilities_delete error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
