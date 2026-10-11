"""Who is asking: resolve the caller from the ``X-Pathly-Run-Token`` header (SPEC § C4).

The identity comes only from a live run token minted at spawn. Body fields (``role``,
``run_id``, ``from``) are never read, so a caller cannot claim to be someone else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("pathly.http")

RUN_TOKEN_HEADER = "X-Pathly-Run-Token"


@dataclass(frozen=True)
class CallerIdentity:
    """``kind`` is ``run`` (live token) or ``anonymous``; ``ui`` is reserved for RRP-2b."""

    kind: Literal["run", "anonymous", "ui"]
    run_id: str | None = None
    role: str | None = None
    feature: str | None = None
    project_root: str | None = None
    board: str | None = None
    scope: str | None = None


def caller_identity(request) -> CallerIdentity:
    """Identity of ``request``'s caller; anonymous when the token is absent, unknown or revoked."""
    token = (request.headers.get(RUN_TOKEN_HEADER) or "").strip()
    if not token:
        return CallerIdentity(kind="anonymous")

    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token

    row = resolve_run_token(get_db(), token)
    if row is None:
        logger.info(
            "unknown or revoked run token from %s", request.remote_addr or "unknown"
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
