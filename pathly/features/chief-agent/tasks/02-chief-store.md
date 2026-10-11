# Add the chief thread, inbox and session tables with their queries

Type: task
Status: open
Blocked by: —
Test first: yes

Add `src/pathly_orchestrator/db/migrations_chief.py` (`add_chief_tables(conn)`, called from
`migrations_incremental._add_additive_migrations`) and `db/queries/chief.py`:

- `chief_thread(id TEXT PK, project_root TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN
  ('human','chief','system')), text TEXT NOT NULL, ts REAL NOT NULL, run_id TEXT)` with an index on
  `(project_root, ts)`. Queries: `append_thread`, `get_thread(project_root, limit, before_ts)`,
  `get_thread_message(id)`.
- `chief_inbox(id TEXT PK, project_root TEXT NOT NULL, kind TEXT NOT NULL, ref_id TEXT, payload
  TEXT, ts REAL NOT NULL, consumed_at REAL)`. Queries: `enqueue`, `take_batch(project_root)`
  (marks the returned rows consumed in the same transaction, so two callers never get the same
  row), `pending_count(project_root)`.
- `chief_session(project_root TEXT PK, session_id TEXT, updated_at REAL)`. Queries:
  `get_session`, `set_session`, `clear_session`.

Writes use the same write lock as the other `db/queries` modules.

## Not in this ticket

- HTTP routes: ticket 03. Who enqueues: ticket 05.

## Done when

- `python -m pytest tests/db/test_chief_store.py -q` passes and covers: thread append and read in
  order with paging; `role` outside the set is refused; `take_batch` returns each row once even
  when called twice concurrently (two threads); session set, read and clear; the migration is
  safe to run twice.

```check
$ python -m pytest tests/db/test_chief_store.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- `src/pathly_orchestrator/db/migrations_incremental.py`, `db/queries/run_tokens.py` (pattern from
  role-read-policy)

## Answer
