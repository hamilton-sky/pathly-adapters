"""role-read-policy: server-issued run tokens (stored hashed, resolved, revoked)."""

from __future__ import annotations

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.migrations_provenance import add_run_tokens
from pathly_orchestrator.db.queries.run_tokens import (
    mint_run_token,
    resolve_run_token,
    revoke_run_tokens,
)


def _mint(conn, run_id="run-1"):
    return mint_run_token(conn, run_id, "builder", "feat", "/proj", "feat", "feature")


def test_mint_resolves_to_its_run() -> None:
    conn = get_db()
    tok = _mint(conn)
    row = resolve_run_token(conn, tok)
    assert row is not None
    assert row["run_id"] == "run-1"
    assert row["role"] == "builder"
    assert row["feature"] == "feat"
    assert row["board"] == "feat"
    assert row["scope"] == "feature"


def test_raw_token_is_not_stored() -> None:
    conn = get_db()
    tok = _mint(conn)
    for row in conn.execute("SELECT * FROM run_tokens").fetchall():
        assert tok not in [v for v in tuple(row)]


def test_revoked_token_resolves_to_none() -> None:
    conn = get_db()
    tok = _mint(conn, "run-2")
    other = _mint(conn, "run-3")
    assert revoke_run_tokens(conn, "run-2") == 1
    assert resolve_run_token(conn, tok) is None
    assert resolve_run_token(conn, other) is not None


def test_unknown_and_empty_token_resolve_to_none() -> None:
    conn = get_db()
    _mint(conn)
    assert resolve_run_token(conn, "nope") is None
    assert resolve_run_token(conn, "") is None
    assert resolve_run_token(conn, None) is None


def test_migration_twice_is_harmless() -> None:
    conn = get_db()
    tok = _mint(conn)
    add_run_tokens(conn)
    add_run_tokens(conn)
    assert resolve_run_token(conn, tok) is not None
