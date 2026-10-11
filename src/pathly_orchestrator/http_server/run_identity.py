"""Resolve who is calling from the spawn-issued X-Pathly-Run-Token header (SPEC C4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

_log = logging.getLogger(__name__)

TOKEN_HEADER = "X-Pathly-Run-Token"


@dataclass(frozen=True)
class CallerIdentity:
    # "ui" is reserved for RRP-2b and is never returned yet.
    kind: Literal["run", "ui", "anonymous"]
    run_id: str | None = None
    role: str | None = None
    feature: str | None = None
    project_root: str | None = None
    board: str | None = None
    scope: str | None = None


def caller_identity(request) -> CallerIdentity:
    """Identity from the run token header only; body fields are never read."""
    token = request.headers.get(TOKEN_HEADER, "")
    if not token:
        return CallerIdentity(kind="anonymous")
    from ..db import get_db
    from ..db.queries.run_tokens import resolve_run_token

    row = resolve_run_token(get_db(), token)
    if row is None:
        _log.info(
            "unknown or revoked run token from %s",
            getattr(request, "remote_addr", None),
        )
        return CallerIdentity(kind="anonymous")
    return CallerIdentity(
        kind="run",
        run_id=row.get("run_id"),
        role=row.get("role"),
        feature=row.get("feature"),
        project_root=row.get("project_root"),
        board=row.get("board"),
        scope=row.get("scope"),
    )
