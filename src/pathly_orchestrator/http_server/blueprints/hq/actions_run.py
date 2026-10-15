"""HQ operator proposals → confirm cards → execution (local-operator 02, 05).

``POST /hq/actions/check``  the model's proposals → cards (title, risk,
                            fingerprint); proposals for actions that are not
                            enabled AND available are dropped.
``POST /hq/actions/run``    the Run click: resolve again, compare the
                            fingerprint (changed → ``stale``), execute through
                            the real endpoint (``_action_exec``), audit.
                            A Studio-run action (diagrams) returns
                            ``approved`` with the resolved target instead.
``POST /hq/actions/report`` Studio reports a Studio-run action's result → audit.

Nothing here runs without the click: ``check`` reads only.
"""

from __future__ import annotations

import logging
import uuid

from flask import Blueprint, jsonify, request

bp = Blueprint("hq_actions_run", __name__)

MAX_PROPOSALS = 8  # the most cards one reply can carry


def _board_and_root(body: dict) -> tuple[str, str | None]:
    board = str(body.get("board") or "").strip()
    root = str(body.get("project_root") or "").strip() or None
    return board, root


def _card(name: str, target, clean: dict) -> dict:
    from pathly_orchestrator.hq_actions import BY_NAME

    action = BY_NAME[name]
    card = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "label": action.label,
        "risk": list(action.risk),
        "runs_on": action.runs_on,
        "args": clean,
        "title": target.title or action.label,
        "status": "proposed" if target.ok else "invalid",
        "fingerprint": target.fingerprint,
    }
    if not target.ok:
        card["summary"] = f"Can't propose: {target.reason}"
    return card


@bp.route("/hq/actions/check", methods=["POST"])
def hq_actions_check():
    """Body ``{board, project_root?, enabled_actions, proposals: [{name, args}]}``.

    200 ``{cards: [...], dropped: [{name, reason}]}``. A card is ``proposed``
    (Run/Cancel) or ``invalid`` (a one-line record: bad args or a target that
    doesn't exist / isn't in a state the action applies to). At most
    MAX_PROPOSALS cards; the rest are dropped.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.hq_actions import (
            TooManyActions,
            effective_actions,
            validate_args,
        )

        from ._action_targets import Target, resolve
        from ._helpers import available_actions

        body = request.get_json(silent=True) or {}
        board, root = _board_and_root(body)
        proposals = body.get("proposals")
        if not board or not isinstance(proposals, list):
            return jsonify({"error": "'board' and 'proposals' are required"}), 400
        conn = get_db()
        try:
            enabled = set(
                effective_actions(body.get("enabled_actions"), available_actions(conn))
            )
        except TooManyActions as exc:
            return jsonify({"error": str(exc)}), 400

        cards: list[dict] = []
        dropped: list[dict] = []
        for p in proposals:
            name = p.get("name") if isinstance(p, dict) else None
            if not isinstance(name, str) or name not in enabled:
                dropped.append({"name": str(name), "reason": "action not enabled"})
                continue
            if len(cards) >= MAX_PROPOSALS:
                dropped.append({"name": name, "reason": "too many proposals"})
                continue
            clean, err = validate_args(name, p.get("args"))
            target = (
                Target(False, reason=err or "bad arguments")
                if clean is None
                else resolve(conn, name, clean, board, root)
            )
            cards.append(_card(name, target, clean or {}))
        return jsonify({"cards": cards, "dropped": dropped}), 200
    except Exception as exc:
        logging.exception("hq actions check error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/hq/actions/run", methods=["POST"])
def hq_actions_run():
    """Body ``{board, project_root?, name, args, fingerprint}`` — the Run click.

    200 with ``status``: ``done`` / ``failed`` (server-run; audited) ·
    ``approved`` + ``target`` (Studio-run; Studio executes then reports) ·
    ``stale`` (the board changed since the card was shown; nothing ran) ·
    ``unavailable`` (Settings no longer allows it; nothing ran). Each with a
    one-line ``summary`` for the card.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.hq_actions import BY_NAME, validate_args

        from ._action_audit import record
        from ._action_exec import execute
        from ._action_targets import resolve
        from ._helpers import available_actions

        body = request.get_json(silent=True) or {}
        board, root = _board_and_root(body)
        name = body.get("name")
        if not board or not isinstance(name, str) or name not in BY_NAME:
            return jsonify({"error": "'board' and a catalog 'name' are required"}), 400
        conn = get_db()
        if name not in available_actions(conn):
            summary = "Not run: this action is turned off in Settings"
            return jsonify({"status": "unavailable", "summary": summary}), 200
        clean, err = validate_args(name, body.get("args"))
        if clean is None:
            return jsonify({"status": "stale", "summary": f"Not run: {err}"}), 200
        target = resolve(conn, name, clean, board, root)
        if not target.ok or target.fingerprint != str(body.get("fingerprint") or ""):
            why = target.reason if not target.ok else "the board changed"
            return jsonify({"status": "stale", "summary": f"Not run: {why}"}), 200
        if BY_NAME[name].runs_on == "studio":
            return (
                jsonify({"status": "approved", "target": target.args, "summary": ""}),
                200,
            )
        outcome = execute(name, target.args, target.title, board, root)
        record(conn, board, name, target.args, outcome.ok, outcome.summary)
        status = "done" if outcome.ok else "failed"
        return jsonify({"status": status, "summary": outcome.summary}), 200
    except Exception as exc:
        logging.exception("hq actions run error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@bp.route("/hq/actions/report", methods=["POST"])
def hq_actions_report():
    """Body ``{board, name, target, ok, summary}`` — a Studio-run action's
    result (diagrams), recorded in the audit log. 400 for a server-run action:
    those are audited by ``/hq/actions/run`` itself."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.hq_actions import BY_NAME

        from ._action_audit import record

        body = request.get_json(silent=True) or {}
        board, _root = _board_and_root(body)
        name = body.get("name")
        if not board or name not in BY_NAME or BY_NAME[name].runs_on != "studio":
            return (
                jsonify({"error": "'board' and a Studio-run action are required"}),
                400,
            )
        target = body.get("target") if isinstance(body.get("target"), dict) else {}
        shown = {
            k: v
            for k, v in target.items()
            if k in ("artifact_id", "style", "diagram_id")
        }
        ok = bool(body.get("ok"))
        summary = str(body.get("summary") or ("Done" if ok else "Failed"))[:200]
        message_id = record(get_db(), board, name, shown, ok, summary)
        return jsonify({"ok": message_id is not None, "message_id": message_id}), 200
    except Exception as exc:
        logging.exception("hq actions report error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
