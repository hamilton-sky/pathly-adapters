"""Shared constants and helpers of the directive tests (chief-agent 12).

``_post`` sends a directive as a chief opened by ``chief_human_support.open_session`` (so the
token is the real one), ``_send`` sends any body with any headers, and ``_rows`` / ``_row`` read
the stored messages. Imported by bare name: ``tests/comms_board`` is on ``sys.path`` for the
test files that sit in it. The fixtures the tests use (``client``, ``project``, ``chief_root``,
the autouse watcher cleanup) come from ``chief_human_support``; the autouse ``_recency_path``
below is imported by name into each test file.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.run_tokens import mint_run_token

ROUTE = "/comms/directives"
TEXT = "No new dependencies without asking the human first."
TOKEN = "X-Pathly-Run-Token"
GONE = object()  # a field the request leaves out
EDIT_REFUSED = "binding directives are superseded, not edited"


@pytest.fixture(autouse=True)
def _recency_path(monkeypatch):
    """No embedding model: ``retrieve_board_context`` falls back to recency."""
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(emb, "embed", lambda *a, **k: None)


def _send(client, body, token=None, **headers):
    if token:
        headers[TOKEN] = token
    return client.post(ROUTE, json=body, headers=headers)


def _post(client, opened, **fields):
    body = {"project_root": opened.project, "to_agent": "*", "text": TEXT, **fields}
    body = {k: v for k, v in body.items() if v is not GONE}
    return _send(client, body, opened.run_token)


def _rows():
    return get_db().execute("SELECT * FROM comms_messages").fetchall()


def _row(message_id):
    return (
        get_db()
        .execute("SELECT * FROM comms_messages WHERE id=?", (message_id,))
        .fetchone()
    )


def _token_of(role, project):
    return mint_run_token(
        get_db(), f"run-{role}", role, "demo", project, "project", project
    )


def _gated(resp):
    return resp.status_code == 403 and "allowed" in (resp.get_json() or {})
