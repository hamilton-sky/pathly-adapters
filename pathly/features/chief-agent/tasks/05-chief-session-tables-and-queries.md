# Add the chief session tables and their queries

Type: task
Status: resolved
Blocked by: —
Test first: yes

The chief needs three small tables and one token lookup that sees revoked rows.

Add `src/pathly_orchestrator/db/migrations_chief.py::add_chief_tables(conn)` (idempotent
`CREATE TABLE IF NOT EXISTS`, like `migrations_provenance.add_run_tokens`) and call it at the end
of `migrations_incremental._add_additive_migrations`, next to `add_run_tokens(conn)`:

- `chief_sessions(run_id TEXT PRIMARY KEY, project_root TEXT NOT NULL, preset TEXT, tier TEXT NOT
  NULL, engine TEXT NOT NULL, tab_id TEXT, cli_session_id TEXT, hook_secret_hash TEXT,
  settings_dir TEXT, opened_at REAL NOT NULL, closed_at REAL, close_reason TEXT)`, indexed on
  `project_root`. `cli_session_id` is the claude session id the server chose for the chief
  (ticket 06 passes it as `--session-id`; NULL for codex): ticket 09 checks hook posts against
  it, and round two finds the chief's transcript by it to bill the session.
- `chief_human_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, project_root
  TEXT, kind TEXT NOT NULL, text TEXT NOT NULL, ts REAL NOT NULL)`, indexed on `run_id`.
- `chief_citations(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, message_id
  INTEGER NOT NULL UNIQUE, route TEXT NOT NULL, target TEXT, ts REAL NOT NULL)`. `UNIQUE` makes
  each human message citable once (ticket 10).

Add `src/pathly_orchestrator/db/queries/chief.py`, every function taking `conn` first and writing
under `_get_write_lock`:

- `create_session(conn, *, run_id, project_root, preset, tier, engine, tab_id, cli_session_id,
  hook_secret_hash, settings_dir)`; `get_session(conn, run_id)`; `open_session_for_project(conn, project_root)`
  (the one with `closed_at IS NULL`, or None).
- `close_session(conn, run_id, reason) -> bool`: sets `closed_at` and `close_reason` once and
  revokes the run's tokens with `run_tokens.revoke_run_tokens`; returns False when it was already
  closed.
- `close_stale_sessions(conn) -> list[str]`: closes every open session (reason `server restart`)
  and returns their run ids.
- `add_human_message(conn, run_id, project_root, text, *, relayed=False) -> dict`: the first
  message of a session is stored with `kind="style_prompt"`, every later one `kind="human"`, or
  `kind="relayed"` when `relayed` is true (a prompt ticket 09 can tell came from another session;
  ticket 10 never accepts it as a citation); returns `{id, kind, ts}`.
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
  closed one alone; `cli_session_id` round trips and may be NULL; the first human message of a
  session is `style_prompt`, the second `human`, and one added with `relayed=True` is `relayed`;
  `record_citation` returns True once and False for a second citation of the same
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

**Built**

- `src/pathly_orchestrator/db/migrations_chief.py` (new): `add_chief_tables(conn)` creates
  `chief_sessions` (index on `project_root`), `chief_human_messages` (index on `run_id`) and
  `chief_citations` (`message_id INTEGER NOT NULL UNIQUE`), all `IF NOT EXISTS`, one commit.
- `src/pathly_orchestrator/db/migrations_incremental.py`: imports it and calls
  `add_chief_tables(conn)` as the last statement of `_add_additive_migrations`, after
  `add_run_tokens` and `add_comms_provenance`.
- `src/pathly_orchestrator/db/queries/chief.py` (new): `create_session`, `get_session`,
  `open_session_for_project`, `close_session`, `close_stale_sessions`, `add_human_message`,
  `get_human_message`, `record_citation`. Every one takes `conn` first, static SQL only, writes
  under `_get_write_lock`.
- `src/pathly_orchestrator/db/queries/run_tokens.py`: added `lookup_run_token(conn, token)`;
  `resolve_run_token` is untouched.
- `tests/db/test_chief_tables.py` (new, 14 tests, committed alone first as `a346872`);
  `tests/INDEX.md` and `tests/db/INDEX.md` regenerated.
- `src/pathly_orchestrator/CLAUDE.md`: the package tree gets a line each for `migrations_chief.py`
  and `queries/chief.py`, `run_tokens.py`'s line names `lookup_run_token`, and
  `migrations_provenance.py`'s "called last from" became "called from" (it is no longer last).

**Proof** (each run fresh after the last edit to the code it covers)

- Test first: at `a346872` `python -m pytest tests/db/test_chief_tables.py -q -p no:cacheprovider`
  failed at collection with `ModuleNotFoundError: No module named
  'pathly_orchestrator.db.migrations_chief'`, the right reason.
- `python -m pytest tests/db/test_chief_tables.py -q -p no:cacheprovider` -> `14 passed in 4.26s`,
  exit 0. It covers the migration run twice with a row kept; create, get and
  `open_session_for_project` round trip (and None for an unknown run or another project);
  `close_session` setting `closed_at` and `close_reason`, `resolve_run_token` returning None for
  the minted token while another run's token stays live, and False the second time with the first
  `closed_at` and reason unchanged; `close_stale_sessions` closing two open sessions (reason
  `server restart`, token revoked) and leaving a closed one untouched, then returning `[]`;
  `cli_session_id` round trip and NULL; first message `style_prompt`, second `human`, a third added
  with `relayed=True` is `relayed`, counted per session; `record_citation` True then False with one
  row stored and the schema's UNIQUE checked directly; `lookup_run_token` returning a revoked row
  with `revoked_at` set, a live row with `revoked_at` None, and None for unknown, empty and None.
- `bandit -q -r src/pathly_orchestrator/db -ll` -> exit 0 (it prints only existing
  "nosec encountered" warnings for other files).
- Lint chain from `commands.md` -> exit 0 (black 577 files unchanged; mypy "no issues found in 317
  source files"; file size "none new, none grown"; `gen_test_index.py --check` up to date;
  lint-imports "1 kept, 0 broken"; whole-`src/` bandit; adapters and entry points OK).
- Smoke -> exit 0. Build `python -m build --wheel` -> exit 0, built
  `pathly_adapters-2.24.1-py3-none-any.whl`.
- Test command from `commands.md` (`tests/comms_board tests/db tests/runner_supervisor
  tests/http_api`) -> `1264 passed, 2 skipped in 251.46s`, exit 0 (the 2 skips are not mine).

**Decisions**

- `add_human_message`: the first message of a session is `style_prompt` even when `relayed=True`;
  `relayed` only labels later messages. This is the literal reading of the ticket ("the first
  message ... `style_prompt`, every later one `human`, or `relayed` when `relayed` is true"). A
  style prompt is not citable, so ignoring the flag on the first message can only make a message
  less citable, never more. The kind is decided and the row inserted under one hold of the write
  lock, so two concurrent first messages cannot both be `style_prompt` inside the server process.
- `close_session` revokes the run's tokens first, then marks the session closed, both under the
  write lock. A failure in between leaves an open session with a dead token (which
  `close_stale_sessions` closes at the next start), never a closed session with a live one. It
  returns False without revoking anything when the run id is unknown or the session was already
  closed, so it cannot revoke the tokens of a run that is not a chief session.
- `close_stale_sessions` goes through `close_session` for each open row, so a stale session's
  tokens are revoked too, and the returned ids are only the ones this call closed.
- `create_session` returns None; a caller that needs the row calls `get_session`. No uniqueness of
  one open session per project is enforced in the schema: that is the 409 of tickets 06 and 07.
- `lookup_run_token` repeats the two-line row-to-dict step of `resolve_run_token` rather than
  extracting a shared helper, because the ticket does not ask for a change to `resolve_run_token`.
- I touched `src/pathly_orchestrator/CLAUDE.md` although the ticket lists no doc: the root
  `CLAUDE.md` documentation-sync rule requires the matching living doc in the same change, and
  ticket 04 did the same.

**Shortcuts taken**

- `record_citation` treats any `sqlite3.IntegrityError` as "already cited", as the ticket says. A
  NOT NULL violation (a `None` route or message id) would also read as False. The callers (ticket
  10) pass a validated message id and a route constant, so it cannot happen there; it would be
  worth narrowing to the UNIQUE message if a caller ever passes unchecked values.
- No foreign keys: `chief_human_messages.run_id` and `chief_citations.run_id` are not tied to
  `chief_sessions` in the schema, as the ticket's column list has none. A message for an unknown
  run is stored; ticket 09 refuses those before it calls `add_human_message`.

**For later tickets**

- Ticket 15 adds `chief_sessions.runs_started INTEGER NOT NULL DEFAULT 0` (spec § Interfaces); it
  is not in this ticket's table, so 15 needs its own additive `ALTER` guarded the way
  `_add_additive_migrations` guards its other columns, and a `create_session` that still works
  without it.
- Ticket 08: the gate can call `lookup_run_token(conn, token)`; a row with `revoked_at` set is a
  revoked token (answer 401 `chief session closed`), None is an unknown one. Check `role == "chief"`
  on the row yourself.
- Ticket 10: `record_citation` is the single-use check; read the cited text with
  `get_human_message` and refuse any row whose `kind` is not `human` (`style_prompt` and `relayed`
  are never citable), and check its `run_id` is the caller's session.
- `add_human_message` returns only `{id, kind, ts}`; the full row, including `text`, comes from
  `get_human_message`.
