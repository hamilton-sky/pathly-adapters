"""Agent + skill registry list endpoints — back the board Run modal's dropdowns.

The Studio catalog hooks previously enumerated the OPEN PROJECT's
``src/pathly_data/core/{agents,skills}`` dir, which only exists in the Pathly dev repo —
so a user project fell back to a tiny hardcoded list. These endpoints enumerate the
INSTALLED ``pathly_data`` core (the FSM server always has it), so the REAL agent/skill set
is available for any project, and user-created agents/skills surface automatically once they
land in the installed core.

Shape mirrors the frontend ``CatalogItem``: ``[{"name": str, "path": str}]``.
"""

from __future__ import annotations

import logging
import os

from flask import Blueprint, jsonify

bp = Blueprint("registry", __name__)


def _core_dir(sub: str) -> str:
    from importlib.resources import files as _res_files

    return str(_res_files("pathly_data").joinpath(f"core/{sub}"))


def _is_md(name: str) -> bool:
    return name.endswith(".md") and not name.startswith("README")


@bp.route("/registry/agents", methods=["GET"])
def registry_agents():
    """List core agent roles: root-level ``<stem>`` and grouped ``<category>/<stem>``."""
    try:
        base = _core_dir("agents")
        out: list[dict] = []
        for entry in sorted(os.listdir(base)):
            path = os.path.join(base, entry)
            if os.path.isfile(path) and _is_md(entry):
                stem = entry[:-3]
                out.append({"name": stem, "path": stem})
            elif os.path.isdir(path):
                for f in sorted(os.listdir(path)):
                    if _is_md(f):
                        stem = f[:-3]
                        out.append({"name": stem, "path": f"{entry}/{stem}"})
        return jsonify(out), 200
    except Exception as e:
        logging.exception("registry_agents error")
        return jsonify({"error": str(e)}), 500


@bp.route("/registry/skills", methods=["GET"])
def registry_skills():
    """List core skills as ``<category>/<stem>`` (the fragments/ dir is excluded)."""
    try:
        base = _core_dir("skills")
        out: list[dict] = []
        for cat in sorted(os.listdir(base)):
            cat_path = os.path.join(base, cat)
            if not os.path.isdir(cat_path) or cat == "fragments":
                continue
            for f in sorted(os.listdir(cat_path)):
                if _is_md(f):
                    stem = f[:-3]
                    out.append({"name": f"{cat}/{stem}", "path": f"{cat}/{stem}"})
        return jsonify(out), 200
    except Exception as e:
        logging.exception("registry_skills error")
        return jsonify({"error": str(e)}), 500
