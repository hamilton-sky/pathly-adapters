"""Prompt CRUD — system-prompts are FILES; the ``ability`` kind stays a DB row (legacy).

    GET    /skills/prompts?kind=&category=&project_root=   list (global+project merged)
    POST   /skills/prompts                                  create / overwrite a prompt
    DELETE /skills/prompts/<category>/<name>?scope=         remove a system-prompt FILE
    PUT    /skills/prompts/<pid>                            (legacy DB ability) edit by id
    DELETE /skills/prompts/<pid>?project_root=              (legacy DB ability) remove by id

``kind='preset'`` (the single-select dropdown alternatives — analyze/split/comment/diagram/
system) is now backed by markdown FILES (``skills/prompt_files.py``), mirroring layer-3
abilities — so a system-prompt is browsable in the Library, **openable in the MD editor**,
``##``-splittable, and git-trackable. Its **id is ``"<category>/<name>"``**. The row shape is
kept DB-compatible so ``useMergedPresets`` and the Sections modal are unchanged. The legacy
``kind='ability'`` rows still resolve from ``prompt_library`` for back-compat.
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from ._editor_bp import bp

_KINDS = {"preset", "ability"}


@bp.route("/skills/prompts", methods=["GET"])
def skills_prompts_list():
    """List prompts (global + project merged), optionally filtered by kind/category.

    ``preset`` → files (with a one-time lazy lift of any legacy DB rows); ``ability`` → DB.
    """
    try:
        project_root = (request.args.get("project_root") or "").strip() or None
        kind = (request.args.get("kind") or "").strip() or None
        category = (request.args.get("category") or "").strip() or None
        if kind and kind not in _KINDS:
            return jsonify({"error": f"invalid kind {kind!r}"}), 400

        if kind == "ability":
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.prompt_library import list_prompts

            rows = list_prompts(
                get_db(project_root),
                kind="ability",
                category=category,
                project_root=project_root,
            )
            return jsonify({"prompts": rows}), 200

        # preset (or unfiltered): file-backed system-prompts.
        from pathly_orchestrator.skills.prompt_files import (
            list_prompt_files,
            migrate_db_presets_to_files,
        )

        try:
            from pathly_orchestrator.db.connection import get_db

            migrate_db_presets_to_files(get_db(project_root), project_root)
        except Exception:
            logging.debug("prompt preset migration skipped", exc_info=True)
        rows = list_prompt_files(project_root, category=category)
        return jsonify({"prompts": rows}), 200
    except Exception as e:
        logging.exception("skills_prompts_list error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/prompts", methods=["POST"])
def skills_prompts_create():
    """Create/overwrite a prompt. ``preset`` writes a FILE; ``ability`` upserts a DB row."""
    try:
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

        if kind == "ability":
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.prompt_library import create_prompt

            row = create_prompt(
                get_db(project_root),
                kind="ability",
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

        # preset → write a system-prompt file.
        from pathly_orchestrator.skills.prompt_files import write_prompt_file

        scope = (data.get("scope") or "project").strip()
        if scope not in ("project", "global"):
            return jsonify({"error": f"invalid scope {scope!r}"}), 400
        row = write_prompt_file(
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
        return jsonify({"prompt": row}), 200
    except Exception as e:
        logging.exception("skills_prompts_create error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/prompts/<category>/<name>", methods=["DELETE"])
def skills_prompts_delete_file(category: str, name: str):
    """Remove a system-prompt FILE by its ``<category>/<name>`` id."""
    try:
        from pathly_orchestrator.skills.prompt_files import delete_prompt_file

        scope = (request.args.get("scope") or "project").strip()
        project_root = (request.args.get("project_root") or "").strip() or None
        if not delete_prompt_file(
            f"{category}/{name}", project_root=project_root, scope=scope
        ):
            return jsonify({"error": f"no prompt {category}/{name}"}), 404
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_prompts_delete_file error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@bp.route("/skills/prompts/<pid>", methods=["PUT"])
def skills_prompts_update(pid: str):
    """(Legacy DB ability) patch a prompt by id — only the JSON keys present are changed."""
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
    """(Legacy DB ability) remove a prompt by id."""
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
