# Add author_role, author_run_id and author_source to comms_messages and backfill existing rows as legacy

Type: convert
Status: open
Blocked by: 03
Test first: yes

Add the provenance columns from SPEC.md § C1 to `comms_messages` in
`db/migrations_provenance.py` (`add_comms_provenance(conn)`, called from
`migrations_incremental._add_additive_migrations`): `author_role TEXT`, `author_run_id TEXT`,
`author_source TEXT` with values `token | system | legacy | none`.

Backfill, once, every row whose `author_source` is NULL:

- `from_agent` in `{supervisor, system}` → `author_role="system"`, `author_source="legacy"`;
- else if the row's `run_id` joins an `agent_invocations` row → that row's `agent_role`,
  `author_source="legacy"`;
- else → `author_role=from_agent`, `author_source="legacy"`.

`author_run_id` stays NULL for backfilled rows: the old `run_id` came from the request body and is
not provenance. Safe to run twice: a second run touches no row (the NULL filter), and a row
written after the migration by ticket 09 already has its source. Anything that does not match a
rule above still gets `legacy` with `from_agent`; nothing is left NULL.

Add to `migrations_provenance.py`, which ticket 03 created.

## Not in this ticket

- Stamping new writes: ticket 09.
- Reading the columns in queries: a later plan.

## Done when

- `python -m pytest tests/db/test_provenance_backfill.py -q` passes and covers: on a DB seeded
  with pre-upgrade rows, an explorer discovery whose `run_id` joins an explorer invocation becomes
  `legacy`/`explorer`; a `supervisor` status becomes `legacy`/`system`; a builder discovery with no
  invocation becomes `legacy`/`builder`; every row has a non-NULL `author_source`; running the
  migration a second time changes no row.

```check
$ python -m pytest tests/db/test_provenance_backfill.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C1 "Rows written before the upgrade"
- `src/pathly_orchestrator/db/migrations_incremental.py`; `agent_invocations` schema in
  `db/migrations.py` (read only)

## Answer
