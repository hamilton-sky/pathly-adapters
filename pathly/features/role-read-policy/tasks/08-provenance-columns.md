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

**Built**: `src/pathly_orchestrator/db/migrations_provenance.py` gained `add_comms_provenance(conn)`; `db/migrations_incremental.py` imports it and calls it as the last line of `_add_additive_migrations` (two one-line edits); `tests/db/test_provenance_backfill.py` (committed first as `40c5f37f`, failing on `ImportError: cannot import name 'add_comms_provenance'`); regenerated `tests/INDEX.md` and `tests/db/INDEX.md`. `db/migrations.py` is untouched.

**Proof** (each run fresh after the last edit):
- `python -m pytest tests/db/test_provenance_backfill.py -q -p no:cacheprovider` -> `9 passed`, exit 0. It covers: explorer discovery whose `run_id` joins an explorer invocation -> `("explorer", None, "legacy")`; a `from_agent=explorer` row whose `run_id` joins a *builder* invocation -> `builder` (role comes from the invocation, not `from_agent`); `supervisor` and `system` rows (even one whose `run_id` joins an invocation) -> `("system", None, "legacy")`; builder discovery with no invocation, with an unknown `run_id`, and with an invocation that has a NULL role -> `("builder", None, "legacy")`; a `human` row -> `("human", None, "legacy")`; all 8 seeded rows have `author_source='legacy'`, a role, and `author_run_id IS NULL`; a second `add_comms_provenance` leaves every row identical and `conn.total_changes` unchanged; a row already stamped `token` is left alone; `_add_additive_migrations` runs the backfill; the three columns are added to a table that lacks them (in-memory pre-upgrade schema), twice without error.
- Test-first: the test-only commit `40c5f37f` fails at collection with the `ImportError` above, before any production code.
- Commands.md Build `python -m compileall -q src/pathly_orchestrator` -> exit 0. Smoke import -> exit 0.
- Commands.md Test (`tests/comms_board tests/db tests/runner_supervisor tests/http_api tests/consistency/test_fragments_run_token.py -q -x -p no:cacheprovider`) -> `976 passed, 2 skipped`, exit 0. Also `tests/fsm_flows/test_gates.py` (it calls `_add_additive_migrations` on a full in-memory schema) -> 31 passed.
- Commands.md Lint pieces: `black --check src/ tests/` -> 477 files unchanged; `check_file_size.py` -> OK, none new, none grown; `check_no_mirror_reads.py` -> OK; `gen_test_index.py --check` -> up to date; `lint-imports` -> 1 kept, 0 broken.

**Decisions**:
- The columns are added by checking `PRAGMA table_info(comms_messages)` first and only altering for a missing one, not by catching `OperationalError` around each `ALTER`, so a real failure is not swallowed.
- Three `UPDATE`s in the spec's order, each filtered on `author_source IS NULL`, one `commit` at the end: (1) `from_agent IN ('supervisor','system')` -> `system`; (2) rows whose non-empty `run_id` joins an `agent_invocations` row with a non-empty `agent_role` -> that role; (3) everything left -> `from_agent`. All three set `legacy`. Rule 1 runs first, so a `supervisor` row whose `run_id` joins an invocation is still `system`.
- An invocation whose `agent_role` is NULL or empty is not counted as a join (the row falls to rule 3 and keeps `from_agent`), so a legacy row never ends up with a NULL role. A NULL or empty `comms_messages.run_id` never joins.
- If several invocations share one `run_id` the newest (`ORDER BY ai.id DESC LIMIT 1`) wins; the spec does not say which.
- No explicit write lock: the migration runs from `_run_migrations` under the DB init path, like `add_run_tokens` and the other additive migrations.

**Shortcuts taken**: the join to `agent_invocations` is a correlated subquery on an unindexed `run_id`, so the first backfill costs messages-with-run_id times invocations. It runs once per DB (every later run matches no row), and `agent_invocations` is small next to a board, so I did not add an index to a table this ticket does not own. It stops being fine if one DB holds hundreds of thousands of both; an `agent_invocations(run_id)` index would fix that.

**For later tickets**:
- Ticket 09: until it lands, rows written after this migration keep `author_source` NULL, and the next server start backfills them as `legacy`. That is the intended gap, not a bug. Once 09 stamps every write (token / system / none), the NULL filter makes the backfill a no-op for them, but any write path 09 misses will be silently relabelled `legacy` on the next start, which is the one place a missed path would hide. 09's test should assert that every `comms_messages` insert path sets `author_source`.
- `author_run_id` is NULL for every legacy row, so the policy's "run's own posts" rule (SPEC C1) never matches history; that is by design.

## Review findings (round 1, quality review)

QUALITY
1. major src/pathly_orchestrator/db/migrations_provenance.py: The backfill's second UPDATE correlates `comms_messages.run_id` against `agent_invocations.run_id` twice per candidate row (the `EXISTS` and the `ORDER BY ai.id DESC LIMIT 1` subselect). `agent_invocations` has no index on `run_id` (its only index is the unique `idx_agent_invocations_source` on `(project_root, feature, source_seq)`), so the backfill scans `agent_invocations` once per message with a run_id, which is quadratic. It runs inside `get_db()` -> `_run_migrations` -> `_add_additive_migrations`, so it blocks every process's first DB open after upgrade. Measured on synthetic tables where every message joins an invocation: 5k x 5k took 1.1 s, 20k x 20k took 19 s, 50k x 50k took 128 s; with `CREATE INDEX idx_ai_run ON agent_invocations(run_id)` 20k x 20k took 0.05 s and 50k x 50k took 0.12 s. Fix: `CREATE INDEX IF NOT EXISTS idx_agent_invocations_run_id ON agent_invocations(run_id)` at the top of `add_comms_provenance`, before the UPDATEs, and add a test that fails if the backfill goes quadratic (assert `EXPLAIN QUERY PLAN` uses an index on `agent_invocations`, or time a 5k x 5k seed).
2. minor src/pathly_orchestrator/db/migrations_provenance.py: the `PRAGMA table_info` check followed by `ALTER TABLE` is not race-safe. The sibling loop in `_add_additive_migrations` catches `sqlite3.OperationalError` for "duplicate column". If two processes open a pre-upgrade DB at the same moment, the second raises "duplicate column name" out of `get_db()`. Wrap each `ALTER` in `try/except sqlite3.OperationalError` as the sibling loop does.
3. minor src/pathly_orchestrator/db/migrations_provenance.py: the NULL filter runs on every startup, so any row with a NULL `author_source` is relabelled `legacy`, including rows from write paths ticket 09 does not stamp; after 09 they would be mislabelled `legacy` instead of `none`, hiding the gap. Ticket 09 must stamp every writer or give unstamped rows `none` explicitly. The three `WHERE author_source IS NULL` UPDATEs scan `comms_messages` on every start (cheap at normal sizes).
4. minor src/pathly_orchestrator/CLAUDE.md: the `db/` package map does not mention `migrations_provenance.py` or the new `comms_messages` provenance columns. The root CLAUDE.md doc-sync rule asks for the living doc to be updated in the same change.

REVIEW: FAIL
