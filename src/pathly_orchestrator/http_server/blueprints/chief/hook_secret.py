"""POST /chief/hook-secret — hand a claude chief's hook secret to Studio, once.

No file holds the secret (``supervisor/chief_secret_claim``). Studio's main process claims it
after the chief's ``TERMINAL_SPAWN`` and starts the chief's claude with it in the environment
(``PATHLY_CHIEF_HOOK_SECRET``), where the ``UserPromptSubmit`` hook reads it. Only a tokenless
caller may claim: any caller that sends a live run token is refused (403), and an agent's
``pathly api`` sends its own. The chief gate refuses the route to a chief token too (it is not in
``chief_routes.ROUTE_ACTIONS``). A tokenless same-user process can still claim first; then
Studio's claim is the second one, which closes the chief, so the first claimer's secret works
for no open session. The secret is never logged.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from .session import _kill_tab, _refuse_agent

bp = Blueprint("chief_hook_secret", __name__)


@bp.route("/chief/hook-secret", methods=["POST"])
def chief_hook_secret():
    """Claim a chief's hook secret: 200 ``{hook_secret}`` the first time.

    400 for a body that is not a JSON object, 403 for a caller with a live run token, 404 for an
    unknown or closed session or one with no secret (a codex chief has no hook), and 409 for a
    second claim, which closes the session and asks the spawn host to kill its tab.
    """
    try:
        refused = _refuse_agent("claiming a hook secret")
        if refused is not None:
            return refused
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "A JSON object body is required"}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries import chief as sessions
        from pathly_orchestrator.supervisor import chief_secret_claim

        run_id = body.get("run_id")
        session = (
            sessions.get_session(get_db(), run_id) if isinstance(run_id, str) else None
        )
        if (
            session is None
            or session.get("closed_at") is not None
            or not session.get("hook_secret_hash")
        ):
            return jsonify({"error": "no open chief session with a hook secret"}), 404
        secret = chief_secret_claim.claim(run_id)
        if secret is None:
            _kill_tab(session)
            return (
                jsonify(
                    {
                        "error": "the hook secret was already claimed; the chief is closed",
                        "run_id": run_id,
                    }
                ),
                409,
            )
        resp = jsonify({"hook_secret": secret})
        resp.headers["Cache-Control"] = "no-store"
        return resp, 200
    except Exception as exc:
        logging.exception("chief_hook_secret error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
