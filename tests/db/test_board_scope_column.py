"""run-identity: fsm_events.board_scope column + append_event extraction."""

from __future__ import annotations

import json
from pathlib import Path

from pathly_orchestrator.db import append_event, get_db

# Isolation is handled by the _isolate_db autouse fixture in conftest.py.
_PROJECT_ROOT = "/project/run-identity"


def test_board_scope_migration_idempotent(tmp_path: Path) -> None:
    """The ALTER TABLE migration must run clean twice on an existing DB."""
    from pathly_orchestrator.db.migrations import _run_migrations

    conn = get_db()  # first migration pass already ran inside get_db()
    _run_migrations(conn)  # second pass — must be a clean no-op
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fsm_events)").fetchall()}
    assert "board_scope" in cols


def test_append_event_persists_board_scope(tmp_path: Path) -> None:
    conn = get_db()
    seq = append_event(
        conn,
        _PROJECT_ROOT,
        "g1-goal-slug",
        {
            "type": "AGENT_DONE",
            "ts": "2026-01-01T00:00:00Z",
            "summary": "done",
            "board_scope": "parent-feature",
        },
    )
    row = conn.execute(
        "SELECT board_scope, payload FROM fsm_events WHERE seq=?", (seq,)
    ).fetchone()
    assert row["board_scope"] == "parent-feature"
    # payload blob unchanged — the full dict still lands verbatim
    payload = json.loads(row["payload"])
    assert payload["board_scope"] == "parent-feature"
    assert payload["summary"] == "done"


def test_append_event_board_scope_absent_is_null(tmp_path: Path) -> None:
    conn = get_db()
    seq = append_event(
        conn, _PROJECT_ROOT, "feat-a", {"type": "AGENT_DONE", "ts": "t1"}
    )
    row = conn.execute(
        "SELECT board_scope FROM fsm_events WHERE seq=?", (seq,)
    ).fetchone()
    assert row["board_scope"] is None


def test_append_event_board_scope_placeholder_is_null(tmp_path: Path) -> None:
    """An unsubstituted <feature> placeholder must not become a junk identity."""
    conn = get_db()
    seq = append_event(
        conn,
        _PROJECT_ROOT,
        "feat-a",
        {"type": "AGENT_DONE", "ts": "t1", "board_scope": "<feature>"},
    )
    row = conn.execute(
        "SELECT board_scope, payload FROM fsm_events WHERE seq=?", (seq,)
    ).fetchone()
    assert row["board_scope"] is None
    # the raw value is still preserved in the payload for debugging
    assert json.loads(row["payload"])["board_scope"] == "<feature>"
