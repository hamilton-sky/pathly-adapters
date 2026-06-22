"""Chat endpoint."""

from __future__ import annotations

from flask import Blueprint, request

from pathly_orchestrator.chat_agent import handle_chat

bp = Blueprint("chat", __name__)


@bp.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        from flask import Response as _Resp

        resp = _Resp()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp
    return handle_chat(request)
