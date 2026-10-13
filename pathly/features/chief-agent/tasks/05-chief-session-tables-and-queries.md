# Add the chief session tables and their queries

Type: task
Status: open
Blocked by: —
Test first: yes

The chief needs three small tables and one token lookup that sees revoked rows.

Add `src/pathly_orchestrator/db/migrations_chief.py::add_chief_tables(conn)` (idempotent
`CREATE TABLE IF NOT EXISTS`, like `migrations_provenance.add_run_tokens`) and call it at the end
of `migrations_incremental._add_additive_migrations`, next to `add_run_tokens(conn)`:

- `chief_sessions(run_id TEXT PRIMARY KEY, project_root TEXT NOT NULL, preset TEXT, tier TEXT NOT
  NULL, engine TEXT NOT NULL, tab_id TEXT, hook_secret_hash TEXT, settings_dir TEXT, opened_at
  REAL NOT NULL, closed_at REAL, close_reason TEXT)`, indexed on `project_root`.
- `chief_human_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, project_root
  TEXT, kind TEXT NOT NULL, text TEXT NOT NULL, ts REAL NOT NULL)`, indexed on `run_id`.
- `chief_citations(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, message_id
  INTEGER NOT NULL UNIQUE, route TEXT NOT NULL, target TEXT, ts REAL NOT NULL)`. `UNIQUE` makes
  each human message citable once (ticket 10).

Add `src/pathly_orchestrator/db/queries/chief.py`, every function taking `conn` first and writing
under `_get_write_lock`:

- `create_session(conn, *, run_id, project_root, preset, tier, engine, tab_id, hook_secret_hash,
  settings_dir)`; `get_session(conn, run_id)`; `open_session_for_project(conn, project_root)`
  (the one with `closed_at IS NULL`, or None).
- `close_session(conn, run_id, reason) -> bool`: sets `closed_at` and `close_reason` once and
  revokes the run's tokens with `run_tokens.revoke_run_tokens`; returns False when it was already
  closed.
- `close_stale_sessions(conn) -> list[str]`: closes every open session (reason `server restart`)
  and returns their run ids.
- `add_human_message(conn, run_id, project_root, text) -> dict`: the first message of a session is
  stored with `kind="style_prompt"`, every later one `kind="human"`; returns `{id, kind, ts}`.
- `get_human_message(conn, message_id) -> dict | None`.
- `record_citation(conn, run_id, message_id, route, target) -> bool`: False, and nothing written,
  when the message was already cited (catch the `sqlite3.IntegrityError`).

Add `run_tokens.lookup_run_token(conn, token) -> dict | None`: the row for a token's hash whether
or not it is revoked (`resolve_run_token` keeps returning live rows only). The gate uses it to tell
a revoked chief token from an unknown one.

Static SQL only (no f-strings, no `+`); `bandit` runs in Lint.

## Not in this ticket

- Who calls these: tickets 06 to 10.
- The `binding` column on `comms_messages`: ticket 11.

## Done when

- `python -m pytest tests/db/test_chief_tables.py -q -p no:cacheprovider` passes and covers: the
  migration runs twice without error; create, get and `open_session_for_project` round trip;
  `close_session` sets `closed_at`, revokes the minted token (`resolve_run_token` returns None)
  and returns False the second time; `close_stale_sessions` closes two open sessions and leaves a
  closed one alone; the first human message of a session is `style_prompt` and the second
  `human`; `record_citation` returns True once and False for a second citation of the same
  message; `lookup_run_token` returns a revoked row with `revoked_at` set and None for an unknown
  token.
- `bandit -q -r src/pathly_orchestrator/db -ll` exits 0.

```check
$ python -m pytest tests/db/test_chief_tables.py -q -p no:cacheprovider
exit 0
prints passed
$ bandit -q -r src/pathly_orchestrator/db -ll
exit 0
```

## Reference

- spec.md § Interfaces (tables)
- `src/pathly_orchestrator/db/migrations_provenance.py`, `db/migrations_incremental.py`
- `src/pathly_orchestrator/db/queries/run_tokens.py` (`_hash`, `revoke_run_tokens`)
- `src/pathly_orchestrator/db/connection.py::_get_write_lock`

## Answer
