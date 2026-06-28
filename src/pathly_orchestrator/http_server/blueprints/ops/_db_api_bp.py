"""Shared Blueprint, constants, and helpers for the DB API routes."""

from __future__ import annotations

import logging
import os

from flask import Blueprint, request

bp = Blueprint("db_api", __name__)

logger = logging.getLogger("pathly.http")

_ALLOWED_KEYWORDS = {
    "select",
    "with",
    "from",
    "where",
    "join",
    "group",
    "order",
    "limit",
    "having",
    "union",
    "intersect",
    "except",
    "explain",
}
_FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "create",
    "alter",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "reindex",
}


def _get_db():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def _project_root_param() -> str:
    raw = request.args.get("project_root", "") or os.environ.get(
        "PATHLY_PROJECT_ROOT", ""
    )
    return raw.replace("\\", "/")
