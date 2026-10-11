# Add the run_tokens table and the queries to mint, resolve and revoke a run token

Type: task
Status: open
Blocked by: —
Test first: yes

A run token is the server-issued identity of one spawn (SPEC.md § C4). Add:

- `src/pathly_orchestrator/db/migrations_provenance.py` with
  `add_run_tokens(conn)`: `CREATE TABLE IF NOT EXISTS run_tokens(token_hash TEXT PRIMARY KEY,
  run_id TEXT NOT NULL, role TEXT, feature TEXT, project_root TEXT, board TEXT, scope TEXT,
  created_at REAL NOT NULL, revoked_at REAL)` plus an index on `run_id`. Call it from
  `db/migrations_incremental.py::_add_additive_migrations` (one line). Do not touch
  `db/migrations.py`.
- `src/pathly_orchestrator/db/queries/run_tokens.py`:
  - `mint_run_token(conn, run_id, role, feature, project_root, board, scope) -> str`: a
    `secrets.token_urlsafe(32)` value; stores only `sha256(token)`; returns the raw token.
  - `resolve_run_token(conn, token) -> dict | None`: the row for `sha256(token)` when it exists and
    is not revoked; `None` otherwise (including an empty or missing token).
  - `revoke_run_tokens(conn, run_id) -> int`: sets `revoked_at` on that run's tokens.

Writes go through the same write lock the other `db/queries` modules use.

## Not in this ticket

- Minting at spawn: ticket 04. Reading the header on requests: ticket 06.

## Done when

- `python -m pytest tests/db/test_run_tokens.py -q` passes and covers: mint returns a token that
  resolves to its run, role, feature, board and scope; the table holds no column equal to the raw
  token; a revoked token resolves to `None`; an unknown and an empty token resolve to `None`;
  running the migration twice is harmless.
- `db/migrations.py` is unchanged.

```check
$ python -m pytest tests/db/test_run_tokens.py -q -p no:cacheprovider
exit 0
prints passed
$ python scripts/check_file_size.py
exit 0
```

## Reference

- SPEC.md § C4 (spawn-issued token)
- `src/pathly_orchestrator/db/migrations_incremental.py`, `db/queries/run_history.py` (pattern to
  follow for an additive table and its queries)

## Answer

**Built**: `src/pathly_orchestrator/db/migrations_provenance.py` (`add_run_tokens`), one call line added at the end of `db/migrations_incremental.py::_add_additive_migrations`, `src/pathly_orchestrator/db/queries/run_tokens.py` (`mint_run_token`, `resolve_run_token`, `revoke_run_tokens`), `tests/db/test_run_tokens.py` (committed first, failing on ImportError), regenerated `tests/INDEX.md` and `tests/db/INDEX.md`.

**Proof**:
- `python -m pytest tests/db/test_run_tokens.py -q -p no:cacheprovider` -> 5 passed (mint resolves to run/role/feature/board/scope; no stored column equals the raw token; revoked -> None; unknown, empty, None -> None; migration twice harmless).
- `git diff --stat -- src/pathly_orchestrator/db/migrations.py` -> empty.
- `python scripts/check_file_size.py` -> exit 0.
- Commands.md Test (comms_board, db, runner_supervisor, http_api) -> 907 passed, 2 skipped. Lint pieces all pass (black, file size, mirror reads, test index, lint-imports).

**Decisions**: `resolve_run_token` returns a plain dict of all columns (includes `token_hash`, `created_at`, `revoked_at`); `revoke_run_tokens` only counts still-live tokens, so a second call returns 0. Tokens are hashed with sha256 hexdigest.

**Shortcuts taken**: none.

**For later tickets**: import `mint_run_token`/`resolve_run_token`/`revoke_run_tokens` from `pathly_orchestrator.db.queries.run_tokens`. The revoke is not yet called anywhere; ticket 04 or 06 decides when a run's tokens are revoked.

## Review findings (round 1, floor guard)

floor guard: the diff weakens the bar instead of meeting it
suppress: tests/db/test_run_tokens.py: assert resolve_run_token(conn, None) is None  # type: ignore[arg-type]
if a finding is intended, the ticket needs a line like: Floor: allow <category>
