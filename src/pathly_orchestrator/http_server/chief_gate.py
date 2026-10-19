"""The chief gate: a ``before_request`` hook that refuses what a chief token may not do.

It acts only on a request whose ``X-Pathly-Run-Token`` belongs to a token row with role
``chief``; every other caller (a builder token, an unknown token, no token) passes untouched.
A chief whose token is revoked or whose session is closed gets 401, never the anonymous
treatment ``caller_identity`` would give it, because anonymous loopback callers can do everything.

For a live chief, the call is classed by ``chief_routes.action_for`` and refused with 403 unless
the session's tier holds that action, names only its own project in the fields its route reads
(``chief_fields``, applied by ``chief_project``), on ``/comms/post`` posts as the chief, and sends
only the keys its route lists (``chief_keys``). Each check runs over every reading of the body a
route may get (``_bodies``). Registered in
``app.py`` right after ``_log_request``, so the secret check and the rate limit run first. Flask
matches the URL rule before any hook runs, so a path no route matches (``url_rule`` is None)
passes here and Flask answers 404 or 405.
"""

from __future__ import annotations

from .chief_keys import key_refusal
from .chief_project import project_refusal
from .chief_routes import POSTS_AS_CHIEF, action_for
from .run_identity import RUN_TOKEN_HEADER


def _refuse(tier: str, action: str | None, allowed: list[str], error: str):
    from flask import jsonify

    body = {"error": error, "action": action, "tier": tier, "allowed": allowed}
    return jsonify(body), 403


def _human_escalation_check(conn):
    def check(message_id: object) -> bool:
        if not isinstance(message_id, str) or not message_id:
            return False
        row = conn.execute(
            "SELECT type, to_agent FROM comms_messages WHERE id=?", (message_id,)
        ).fetchone()
        return (
            row is not None
            and row["type"] == "escalation"
            and str(row["to_agent"] or "").strip().lower() == "human"
        )

    return check


def _asks_for_overrides(body: dict) -> bool:
    """A non-empty ``prompt_override`` or ``stage_overrides``: verbatim text for spawned agents."""
    return bool(body.get("prompt_override")) or bool(body.get("stage_overrides"))


def _bodies() -> list[dict]:
    """Every JSON object a route may read from this request's body; ``[{}]`` when none.

    The comms routes read the body with ``read_json_body`` (UTF-8, then cp1252, whatever the
    content type). ``/runs``, ``/runner/*``, ``/code/query`` and the run-control verbs read it
    with ``get_json``, which hands the raw bytes to ``json.loads``: a BOM, UTF-16 and UTF-32 are
    all understood there and none of them is by the first reader. A body only one reader
    understands must still be checked, so every check runs over each result. The second parse
    forces the content type and does not cache, so what a route reads is unchanged.
    """
    from flask import request

    from .blueprints.comms._helpers import read_json_body

    found: list[dict] = []
    for parsed in (
        read_json_body({}),
        request.get_json(silent=True, force=True, cache=False),
    ):
        if isinstance(parsed, dict) and parsed and parsed not in found:
            found.append(parsed)
    return found or [{}]


def _refusal(rule, method: str, session: dict, conn, body: dict):
    """The 403 for one reading of the body, or None when the gate lets it through."""
    from flask import request

    from pathly_orchestrator.supervisor.chief_tiers import actions_for

    tier = str(session.get("tier") or "")
    allowed = sorted(actions_for(tier))
    action = action_for(
        rule.rule, method, request.view_args or {}, body, _human_escalation_check(conn)
    )
    if action is None:
        return _refuse(tier, None, allowed, "the chief may not call this route")
    if action not in allowed:
        return _refuse(tier, action, allowed, f"a {tier} chief may not {action}")
    if _asks_for_overrides(body) and "run" not in allowed:
        return _refuse(
            tier,
            "run",
            allowed,
            "prompt_override and stage_overrides need the run action",
        )
    other = project_refusal(
        rule.rule, method, session, body, request.args, request.view_args or {}
    )
    if other is not None:
        return _refuse(tier, action, allowed, other)
    if rule.rule in POSTS_AS_CHIEF and body.get("from") != "chief":
        return _refuse(tier, action, allowed, "a chief posts as 'chief'")
    unlisted = key_refusal(rule.rule, method, request.args if method == "GET" else body)
    if unlisted is not None:
        return _refuse(tier, action, allowed, unlisted)
    return None


def chief_gate():
    """Refuse a chief token's call its tier or project does not allow; None lets it through."""
    from flask import jsonify, request

    token = (request.headers.get(RUN_TOKEN_HEADER) or "").strip()
    if not token:
        return None

    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries import chief as sessions
    from pathly_orchestrator.db.queries.run_tokens import lookup_run_token

    conn = get_db()
    row = lookup_run_token(conn, token)
    if row is None or row.get("role") != "chief":
        return None
    session = None
    if row.get("revoked_at") is None:
        session = sessions.get_session(conn, row.get("run_id"))
    if session is None or session.get("closed_at") is not None:
        return jsonify({"error": "chief session closed"}), 401

    rule = request.url_rule
    if rule is None:
        return None

    method = "GET" if request.method == "HEAD" else request.method
    for body in [{}] if method == "GET" else _bodies():
        refused = _refusal(rule, method, session, conn, body)
        if refused is not None:
            return refused
    return None
