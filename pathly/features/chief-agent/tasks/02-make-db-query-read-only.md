# Run POST /db/query read-only

Type: task
Status: open
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
