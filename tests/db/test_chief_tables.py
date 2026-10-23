"""chief-agent: the chief session tables, their queries and the revoked-token lookup."""

from __future__ import annotations

import sqlite3

import pytest

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.migrations_chief import add_chief_tables
from pathly_orchestrator.db.queries import chief
from pathly_orchestrator.db.queries.run_tokens import (
    lookup_run_token,
    mint_run_token,
    resolve_run_token,
    revoke_run_tokens,
)

PROJECT = "/work/proj"


def _open(conn, run_id="chief-1", project_root=PROJECT, cli_session_id="sess-1"):
    chief.create_session(
        conn,
        run_id=run_id,
        project_root=project_root,
        preset="status",
        tier="status",
        engine="claude",
        tab_id="tab-" + run_id,
        cli_session_id=cli_session_id,
        hook_secret_hash="hash-" + run_id,
        settings_dir="/tmp/settings-" + run_id,
    )


def _mint(conn, run_id="chief-1", project_root=PROJECT):
    return mint_run_token(conn, run_id, "chief", None, project_root, "project", None)


def test_migration_runs_twice_and_keeps_rows() -> None:
    conn = get_db()
    _open(conn)
    add_chief_tables(conn)
    add_chief_tables(conn)
    assert chief.get_session(conn, "chief-1") is not None


def test_create_get_and_open_session_round_trip() -> None:
    conn = get_db()
    _open(conn)
    row = chief.get_session(conn, "chief-1")
    assert row is not None
    assert row["run_id"] == "chief-1"
    assert row["project_root"] == PROJECT
    assert row["preset"] == "status"
    assert row["tier"] == "status"
    assert row["engine"] == "claude"
    assert row["tab_id"] == "tab-chief-1"
    assert row["cli_session_id"] == "sess-1"
    assert row["hook_secret_hash"] == "hash-chief-1"
    assert row["settings_dir"] == "/tmp/settings-chief-1"
    assert row["opened_at"] > 0
    assert row["closed_at"] is None
    assert row["close_reason"] is None
    open_row = chief.open_session_for_project(conn, PROJECT)
    assert open_row is not None
    assert open_row["run_id"] == "chief-1"


def test_unknown_session_and_other_project_are_none() -> None:
    conn = get_db()
    _open(conn)
    assert chief.get_session(conn, "nope") is None
    assert chief.open_session_for_project(conn, "/work/other") is None


def test_cli_session_id_may_be_null() -> None:
    conn = get_db()
    _open(conn, run_id="codex-1", cli_session_id=None)
    row = chief.get_session(conn, "codex-1")
    assert row is not None
    assert row["cli_session_id"] is None


def test_close_session_sets_fields_revokes_token_and_is_once_only() -> None:
    conn = get_db()
    _open(conn)
    token = _mint(conn)
    other = _mint(conn, run_id="chief-2")
    assert resolve_run_token(conn, token) is not None
    assert chief.close_session(conn, "chief-1", "tab closed") is True
    row = chief.get_session(conn, "chief-1")
    assert row["closed_at"] is not None
    assert row["close_reason"] == "tab closed"
    assert resolve_run_token(conn, token) is None
    assert resolve_run_token(conn, other) is not None
    assert chief.open_session_for_project(conn, PROJECT) is None
    closed_at = row["closed_at"]
    assert chief.close_session(conn, "chief-1", "again") is False
    again = chief.get_session(conn, "chief-1")
    assert again["closed_at"] == closed_at
    assert again["close_reason"] == "tab closed"


def test_close_unknown_session_is_false() -> None:
    conn = get_db()
    token = _mint(conn, run_id="not-a-chief")
    assert chief.close_session(conn, "not-a-chief", "x") is False
    assert resolve_run_token(conn, token) is not None


def test_close_stale_sessions_closes_open_ones_and_leaves_closed_alone() -> None:
    conn = get_db()
    _open(conn, run_id="a", project_root="/p/a")
    _open(conn, run_id="b", project_root="/p/b")
    _open(conn, run_id="c", project_root="/p/c")
    token_a = _mint(conn, run_id="a", project_root="/p/a")
    assert chief.close_session(conn, "c", "user closed") is True
    closed_c = chief.get_session(conn, "c")
    assert sorted(chief.close_stale_sessions(conn)) == ["a", "b"]
    for run_id in ("a", "b"):
        row = chief.get_session(conn, run_id)
        assert row["closed_at"] is not None
        assert row["close_reason"] == "server restart"
    assert resolve_run_token(conn, token_a) is None
    still_c = chief.get_session(conn, "c")
    assert still_c["closed_at"] == closed_c["closed_at"]
    assert still_c["close_reason"] == "user closed"
    assert chief.close_stale_sessions(conn) == []


def test_first_message_is_style_prompt_then_human_then_relayed() -> None:
    conn = get_db()
    _open(conn)
    first = chief.add_human_message(conn, "chief-1", PROJECT, "you are the chief")
    second = chief.add_human_message(conn, "chief-1", PROJECT, "what is running?")
    third = chief.add_human_message(
        conn, "chief-1", PROJECT, "from another session", relayed=True
    )
    assert first["kind"] == "style_prompt"
    assert second["kind"] == "human"
    assert third["kind"] == "relayed"
    assert set(first) == {"id", "kind", "ts"}
    assert first["ts"] > 0
    assert len({first["id"], second["id"], third["id"]}) == 3
    stored = chief.get_human_message(conn, second["id"])
    assert stored["run_id"] == "chief-1"
    assert stored["project_root"] == PROJECT
    assert stored["kind"] == "human"
    assert stored["text"] == "what is running?"
    assert stored["ts"] == second["ts"]


def test_first_message_is_counted_per_session() -> None:
    conn = get_db()
    _open(conn, run_id="one", project_root="/p/one")
    _open(conn, run_id="two", project_root="/p/two")
    chief.add_human_message(conn, "one", "/p/one", "style one")
    other = chief.add_human_message(conn, "two", "/p/two", "style two")
    assert other["kind"] == "style_prompt"


def test_unknown_message_is_none() -> None:
    conn = get_db()
    assert chief.get_human_message(conn, 12345) is None


def test_record_citation_once_per_message() -> None:
    conn = get_db()
    _open(conn)
    chief.add_human_message(conn, "chief-1", PROJECT, "style")
    msg = chief.add_human_message(conn, "chief-1", PROJECT, "yes, go ahead")
    assert (
        chief.record_citation(conn, "chief-1", msg["id"], "/comms/answer", "q-1")
        is True
    )
    assert (
        chief.record_citation(conn, "chief-1", msg["id"], "/comms/answer", "q-2")
        is False
    )
    rows = conn.execute(
        "SELECT run_id, message_id, route, target, ts FROM chief_citations"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["target"] == "q-1"
    assert rows[0]["ts"] > 0


def test_message_id_unique_in_the_schema() -> None:
    conn = get_db()
    conn.execute(
        "INSERT INTO chief_citations (run_id, message_id, route, target, ts)"
        " VALUES ('r', 1, '/x', NULL, 1.0)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO chief_citations (run_id, message_id, route, target, ts)"
            " VALUES ('r', 1, '/y', NULL, 2.0)"
        )
    conn.rollback()


def test_lookup_run_token_sees_revoked_rows() -> None:
    conn = get_db()
    token = _mint(conn)
    live = lookup_run_token(conn, token)
    assert live is not None
    assert live["run_id"] == "chief-1"
    assert live["role"] == "chief"
    assert live["revoked_at"] is None
    assert revoke_run_tokens(conn, "chief-1") == 1
    assert resolve_run_token(conn, token) is None
    revoked = lookup_run_token(conn, token)
    assert revoked is not None
    assert revoked["run_id"] == "chief-1"
    assert revoked["revoked_at"] is not None


def test_lookup_run_token_unknown_empty_and_missing_are_none() -> None:
    conn = get_db()
    assert lookup_run_token(conn, "not-a-real-token") is None
    assert lookup_run_token(conn, "") is None
    assert lookup_run_token(conn, None) is None
