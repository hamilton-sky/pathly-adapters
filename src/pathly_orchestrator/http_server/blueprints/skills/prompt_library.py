"""Prompt-library CRUD — the DB store behind every prompt dropdown + ability packs.

    GET    /skills/prompts?kind=&category=&project_root=   list (global+project merged)
    POST   /skills/prompts                                  create / upsert a prompt
    PUT    /skills/prompts/<pid>                            edit a prompt by id
    DELETE /skills/prompts/<pid>?project_root=              remove a prompt by id

``kind`` is ``preset`` (single-select dropdown alternatives) or ``ability`` (stackable
layer-3 modifiers). The shared ``PromptActionConfig`` merges these DB rows with the
built-in presets so a user-added prompt appears in the same dropdown.
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from ._editor_bp import bp

_KINDS = {"preset", "ability"}


@bp.route("/skills/prompts", methods=["GET"])
def skills_prompts_list():
    """List prompts (global + project merged), optionally filtered by kind/category."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.prompt_library import list_prompts

        project_root = (request.args.get("project_root") or "").strip() or None
        kind = (request.args.get("kind") or "").strip() or None
        category = (request.args.get("category") or "").strip() or None
        if kind and kind not in _KINDS:
            return jsonify({"error": f"invalid kind {kind!r}"}), 400
        rows = list_prompts(
            get_db(project_root),
            kind=kind,
            category=category,
            project_root=project_root,
        )
        return jsonify({"prompts": rows}), 200
    except Exception as e:
        logging.exception("skills_prompts_list error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/prompts", methods=["POST"])
def skills_prompts_create():
    """Create (or upsert on name-within-scope) a prompt. Returns the stored row."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.prompt_library import create_prompt

        data = request.get_json() or {}
        kind = (data.get("kind") or "preset").strip()
        category = (data.get("category") or "").strip()
        name = (data.get("name") or "").strip()
        label = (data.get("label") or name).strip()
        body = data.get("body") or ""
        if kind not in _KINDS:
            return jsonify({"error": f"invalid kind {kind!r}"}), 400
        if not category or not name or not body.strip():
            return jsonify({"error": "category, name, and body are required"}), 400
        project_root = (data.get("project_root") or "").strip() or None
        row = create_prompt(
            get_db(project_root),
            kind=kind,
            category=category,
            name=name,
            label=label,
            body=body,
            hint=(data.get("hint") or "").strip(),
            skill_ref=(data.get("skill_ref") or None),
            project_root=project_root,
            sort_order=int(data.get("sort_order") or 0),
        )
        return jsonify({"prompt": row}), 200
    except Exception as e:
        logging.exception("skills_prompts_create error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/prompts/<pid>", methods=["PUT"])
def skills_prompts_update(pid: str):
    """Patch a prompt by id (only the JSON keys present are changed)."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.prompt_library import update_prompt

        data = request.get_json() or {}
        project_root = (data.get("project_root") or "").strip() or None
        fields = {
            k: data[k]
            for k in ("label", "hint", "body", "skill_ref", "sort_order")
            if k in data
        }
        row = update_prompt(get_db(project_root), pid, fields)
        if row is None:
            return jsonify({"error": f"no prompt {pid!r}"}), 404
        return jsonify({"prompt": row}), 200
    except Exception as e:
        logging.exception("skills_prompts_update error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/prompts/<pid>", methods=["DELETE"])
def skills_prompts_delete(pid: str):
    """Remove a prompt by id."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.prompt_library import delete_prompt

        project_root = (request.args.get("project_root") or "").strip() or None
        if not delete_prompt(get_db(project_root), pid):
            return jsonify({"error": f"no prompt {pid!r}"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_prompts_delete error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500
