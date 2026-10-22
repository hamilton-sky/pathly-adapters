"""POST /comms/directives — a binding directive (standing order), posted as the chief.

A directive is a ``decision`` on the project board whose ``binding`` flag is 1: every prompt of
the role it is addressed to carries it, whatever its status, until it is superseded (ticket 11,
``db/queries/comms_directives.get_binding_decisions``). This is the only route that sets the
flag. ``/comms/post`` ignores a ``binding`` field, and ``/comms/edit`` refuses a binding row, so
a directive is replaced with ``/comms/supersede``, never rewritten.

Caller: a live run whose role is ``chief``, and nobody else. A request with no run token is
refused even when it carries the server secret (what Studio sends today): until the UI token
(RRP-2b) the server cannot tell Studio from any local process that reads the secret file, and a
standing order is the strongest write on the board. The chief gate (``chief_gate``) has already
checked, for a chief token, that the session's tier may ``decide``, that ``project_root`` is the
session's own project and that the body holds only the keys ``chief_field_calls`` lists.
"""

from __future__ import annotations

import logging
import re

from flask import Blueprint, jsonify, request

from ...run_identity import caller_identity, is_chief_run
from ...sse import _broadcast_comms
from ._helpers import read_json_body

bp = Blueprint("comms_directives", __name__)

# `*` (every role) or a role name; matched exactly against a prompt's role, so no upper case
# and no padding. `fullmatch`, not `$`, which would also accept a trailing newline.
_ROLE = re.compile(r"[a-z][a-z0-9_-]{0,39}")
# 8 KiB of UTF-8: the standing-orders block has no other cap, and one oversized order would
# break the argv of every spawn.
MAX_TEXT_BYTES = 8 * 1024
# C0 and C1 controls except tab and newline. A NUL in a standing order would make every spawn
# of the role fail (``subprocess`` refuses an argument with an embedded null byte).
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _text_refusal(text: object) -> str | None:
    """Why ``text`` cannot be a directive, or None."""
    if not isinstance(text, str) or not text.strip():
        return "Field 'text' must be a non-empty string"
    if _CONTROL.search(text):
        return "Field 'text' must not contain control characters except newline and tab"
    try:
        size = len(text.strip().encode("utf-8"))
    except UnicodeEncodeError:
        return "Field 'text' must be valid Unicode"
    if size > MAX_TEXT_BYTES:
        return f"Field 'text' must be at most {MAX_TEXT_BYTES} bytes"
    return None


@bp.route("/comms/directives", methods=["POST"])
def comms_directives():
    """Post a binding directive: 201 ``{id}``.

    403 for anything but a live chief run; 400 for a body that is not an object, a blank
    ``project_root``, a ``to_agent`` that is not ``*`` or a lowercase role name of at most 40
    characters, or a ``text`` that is blank, over 8 KiB in UTF-8, holds a control character
    other than newline and tab, or cannot be encoded.

    The caller is looked up once and the row is stamped with that same identity: a second
    lookup could answer "nobody" once the session had closed in between, and the row would be
    stored with ``author_source`` ``none``.
    """
    try:
        identity = caller_identity(request)
        if not is_chief_run(identity):
            return jsonify({"error": "only a chief may post a directive"}), 403

        data = read_json_body()
        if not data:
            return jsonify({"error": "Missing or invalid JSON body"}), 400
        project_root = data.get("project_root")
        if not isinstance(project_root, str) or not project_root.strip():
            return (
                jsonify({"error": "Field 'project_root' must be a non-empty string"}),
                400,
            )
        to_agent = data.get("to_agent")
        if not isinstance(to_agent, str) or not (
            to_agent == "*" or _ROLE.fullmatch(to_agent)
        ):
            return (
                jsonify(
                    {
                        "error": "Field 'to_agent' must be '*' or a role name: a lowercase "
                        "letter, then lowercase letters, digits, '_' or '-', at most 40 in all"
                    }
                ),
                400,
            )
        text = data.get("text")
        refusal = _text_refusal(text)
        if refusal is not None:
            return jsonify({"error": refusal}), 400

        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_directives import post_directive
        from pathly_orchestrator.fsm_compose import resolve_board_scope
        from pathly_orchestrator.runner.provenance import stamp

        scope = resolve_board_scope("project", project_root, "")
        message_id = post_directive(
            get_db(), scope, to_agent, text.strip(), **stamp(identity)
        )
        # The same update comms_post sends for a new row.
        _broadcast_comms(
            scope,
            {
                "type": "COMMS_UPDATE",
                "message_id": message_id,
                "feature": "project",
                "board": "project",
                "scope": scope,
                "msg_type": "decision",
                "run_id": None,
            },
        )
        return jsonify({"id": message_id}), 201
    except Exception as exc:
        logging.exception("comms_directives error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
