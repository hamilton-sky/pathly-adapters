# Run POST /db/query read-only

Type: task
Status: resolved
Blocked by: —
Test first: yes

`ops/db_api_admin.py::db_query` only checks the first word of the SQL against
`_ALLOWED_KEYWORDS` / `_FORBIDDEN_KEYWORDS`, then runs it on the shared connection. A statement
that starts with `WITH` and ends in `INSERT`, `UPDATE` or `DELETE` passes the check and writes:
enough to insert a `run_tokens` row (minting a token) or rewrite an `author_*` stamp.

Make the statement unable to write: on the request thread's connection (`_get_db()`, which is
thread-local and already has sqlite-vec loaded) set `PRAGMA query_only = ON` just before
`execute`, and set it back `OFF` in a `finally`, so no later request on that thread inherits it.
The keyword check stays as the first filter. Under `query_only`, a write attempt (including one
behind `WITH`) raises `sqlite3.OperationalError` ("attempt to write a readonly database"), which
the route's existing `except sqlite3.Error` turns into a 400 with the SQLite message. `execute`
runs exactly one statement and raises `sqlite3.ProgrammingError` (also a `sqlite3.Error`, so also a
400) when the SQL holds more than one. That means the caller cannot turn the pragma back off
inside its own SQL. Keep it that way: never use `executescript`. The sources and the measurements
on Python 3.11, 3.12 and 3.13 are in map.md § Decisions so far (docs: SQLite `query_only`, Python
`sqlite3`).

Living docs: if `src/pathly_orchestrator/CLAUDE.md` describes `/db/query` as SELECT-only by
keyword, say it now runs under `query_only`.

## Not in this ticket

- Restricting what `/db/query` may read (it still sees every table): the chief gate refuses it
  for chief tokens in ticket 08; the UI token is RRP-2b.

## Done when

- `python -m pytest tests/http_api/test_db_query_read_only.py -q -p no:cacheprovider` passes and
  covers: `WITH x AS (SELECT 1) INSERT INTO run_tokens ...`, the same with `UPDATE comms_messages
  SET author_role = ...` and with `DELETE` each return 400 and leave the row counts unchanged;
  `SELECT 1; PRAGMA query_only = OFF` returns 400, and a `WITH ... INSERT` sent after it is still
  refused; a plain `SELECT` still returns rows; after a refused write, a normal write on the same
  thread (for example `post_message`) still succeeds.

```check
$ python -m pytest tests/http_api/test_db_query_read_only.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Decisions ("`/db/query` read-only")
- map.md § Decisions so far (docs: SQLite `PRAGMA query_only`, Python `sqlite3` `Cursor.execute`)
- `src/pathly_orchestrator/http_server/blueprints/ops/db_api_admin.py`, `_db_api_bp.py`
- `src/pathly_orchestrator/db/connection.py::get_db` (thread-local connection; read-only here)

## Answer

Work started at `ea037dff13236b117f4295bce8a0a4d58d5af45a`. Test-only commit: `26242de`
(`test(chief-agent): 02 failing test`).

**Built**

- `tests/http_api/test_db_query_read_only.py` (new, 7 tests), committed alone first, plus the two
  regenerated `tests/INDEX.md` and `tests/http_api/INDEX.md`.
- `src/pathly_orchestrator/http_server/blueprints/ops/db_api_admin.py::db_query`: after the keyword
  check, `PRAGMA query_only = ON` on `_get_db()`'s connection, the `execute(sql).fetchmany(500)`
  inside a `try`, and `PRAGMA query_only = OFF` in its `finally`. The docstring now says so. The
  existing `except sqlite3.Error` still turns the refusal into a 400 with SQLite's message.
- `CHANGELOG.md` (Unreleased, role-read-policy paragraph): the known limit "`POST /db/query` still
  accepts a `WITH ... INSERT`" is no longer true, so it is replaced by a sentence saying the route
  runs under `query_only` (ticket 01 edited the same file for its change).

**Proof** (all run fresh after the last edit)

- `python -m pytest tests/http_api/test_db_query_read_only.py -q -p no:cacheprovider` printed
  `7 passed in 2.11s`, exit 0. At commit `26242de` (test only) the same command gave `5 failed, 2
  passed`: the failures were `assert 200 == 400` (the `WITH` writes went through), and the two that
  passed were the plain `SELECT` and the pragma-state check, as expected.
- What the tests cover: `WITH x AS (SELECT 1) INSERT INTO run_tokens ...`, the same with `UPDATE
  comms_messages SET author_role = 'chief' ...` and with `DELETE` each return 400 with "readonly" in
  the message and leave `run_tokens`/`comms_messages` counts and every `(id, author_role,
  author_source)` unchanged; `SELECT 1; PRAGMA query_only = OFF` returns 400 and the `WITH ... INSERT`
  sent after it is still 400; a plain `SELECT` returns `[{"text": "seed row"}]`; `PRAGMA query_only`
  reads 0 after a select, a refused write, a refused two-statement call and a `no such table` error;
  `post_message` on the same thread succeeds after a refused write.
- Mutation check: replacing the `finally` body with `pass` made `test_pragma_is_off_again_after_every_outcome`
  and `test_normal_write_on_the_same_thread_works_after_a_refused_one` fail (`attempt to write a
  readonly database` from `post_message`). Reverted; the file is as committed above.
- Same statements run directly on `sqlite3` under `query_only`, with `python3.11`, `3.12` and `3.13`
  (`-I`): both `WITH` writes and the `WITH ... DELETE` raise `OperationalError`, the two-statement
  call raises `ProgrammingError`, and the table keeps its row, on 3.11.17, 3.12.3 and 3.13.16 with
  SQLite 3.45.1. The pytest file itself ran only on 3.12.3 (the venv's interpreter).
- Test command from `commands.md` (`tests/comms_board tests/db tests/runner_supervisor tests/http_api`):
  `1201 passed, 2 skipped in 298.21s`, exit 0. The 2 skips are not in the new file.
- Lint chain from `commands.md`: exit 0 (black, mypy `no issues found in 313 source files`,
  `check_file_size` `none new, none grown`, mirror reads OK, `gen_test_index --check` up to date,
  `lint-imports` `1 kept, 0 broken`, bandit, `check_adapters`, `check_entry_points`).
  Smoke: exit 0. Build (`python -m build --wheel`): exit 0.

**Decisions**

- `PRAGMA query_only = ON` is set inside the `try`, so the `finally` resets it whatever happens
  (including an error in the `ON` statement).
- No change to `_ALLOWED_KEYWORDS` / `_FORBIDDEN_KEYWORDS`: they stay the first filter, as the
  ticket says.
- `src/pathly_orchestrator/CLAUDE.md` does not mention `/db/query` at all (grep of the repo outside
  `pathly/features/` found only the code, Studio's caller `studio/src/main/ipc/db.ts`, the
  CHANGELOG line and an old research note), so it needed no change. The old research note
  `pathly/.research/PRODUCTION_READINESS_FINDINGS.md` is a record and was left alone.

**Shortcuts taken**: none. Known limit, not a shortcut: the statement can still read every table
(ticket 08 refuses `/db/query` for chief tokens). Another: a runaway `SELECT` still has no cost
limit (the research note's LOW finding), unchanged.

**For later tickets**

- The Flask test client serves a request on the calling thread, so route and test share the
  thread-local `get_db()` connection. That makes "the pragma leaked to the next request" directly
  testable (ticket 13's acceptance can assert `PRAGMA query_only` is 0 after a refused call).
- Ticket 13's acceptance and its docs pass can cite `/db/query` as already read-only; the spec's
  "Migration and compatibility" line for `/db/query` is now true.
