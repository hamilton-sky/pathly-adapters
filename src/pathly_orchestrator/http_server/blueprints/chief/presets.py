"""GET /chief/presets: the styles a chief can be opened with, and the tier each one gets.

Studio's Chief launcher lists these, so the tier it shows is the one the server will enforce:
``open_chief`` resolves the tier from the preset name (``chief_tiers.resolve_preset_tier``), never
from anything Studio sends, and this route asks the same function. A user's file ``chief/<name>``
(project over global) replaces the built-in text of that name and names its own tier in front
matter; a file without a ``tier:`` line is ``status``.

``text`` is the style as stored, front matter included, so a launcher that saves an edited copy
keeps the ``tier:`` line it read. Without ``project_root`` only the built-ins and the global
files are listed. ``limits`` are the run and cost limits an operator chief opened now would get
(``chief_budget``), which ``GET /chief/session`` reports only while a chief is open.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("chief_presets", __name__)


@bp.route("/chief/presets", methods=["GET"])
def chief_presets():
    """``{presets: [{name, label, tier, text, source, scope}], tiers: {tier: [action, …]},
    limits: {max_runs_per_session, max_cost_usd_per_run}}``.

    The built-ins come first (status, planner, operator), then the user's other files by name.
    ``source`` is ``builtin`` or ``user``; ``scope`` is ``project``, ``global`` or null.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.skills.prompt_files import list_prompt_files
        from pathly_orchestrator.supervisor.chief_presets import BUILT_IN
        from pathly_orchestrator.supervisor.chief_session import (
            normalise_project_root,
        )
        from pathly_orchestrator.supervisor.chief_tiers import (
            ACTIONS,
            TIERS,
            resolve_preset_tier,
        )

        from ...chief_budget import ceiling_usd, run_limit

        raw_root = request.args.get("project_root", "")
        root = normalise_project_root(raw_root) if raw_root else None
        files = {row["name"]: row for row in list_prompt_files(root, category="chief")}
        names = list(BUILT_IN) + sorted(n for n in files if n not in BUILT_IN)

        presets = []
        for name in names:
            row = files.get(name)
            presets.append(
                {
                    "name": name,
                    "label": row["label"] if row else name.capitalize(),
                    "tier": resolve_preset_tier(name, root),
                    "text": row["body"] if row else BUILT_IN[name],
                    "source": "user" if row else "builtin",
                    "scope": row["scope"] if row else None,
                }
            )
        tiers = {
            tier: [a for a in ACTIONS if a in actions]
            for tier, actions in TIERS.items()
        }
        conn = get_db()
        limits = {
            "max_runs_per_session": run_limit(conn),
            "max_cost_usd_per_run": ceiling_usd(conn),
        }
        return jsonify({"presets": presets, "tiers": tiers, "limits": limits}), 200
    except Exception as exc:
        logging.exception("chief_presets error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
