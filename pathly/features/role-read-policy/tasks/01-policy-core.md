# Add the read-policy core: policy shape, built-in walls, SQL predicate and its pure twin

Type: task
Status: resolved
Blocked by: —
Test first: yes

Create `src/pathly_orchestrator/runner/read_policy.py`, the one place the role read wall is
defined (SPEC.md § C1, C2, C3). Nothing calls it yet.

- `ReadPolicy`: a `TypedDict` with the existing tier booleans (`feature`, `project`, `global`) and
  the two optional lists `exclude_types` and `exclude_authors`. Absent lists mean "withhold
  nothing", so an existing `board_scope` row reads exactly as today.
- `BUILTIN_DEFAULTS: dict[str, ReadPolicy]` with the rows from SPEC § C2: `reviewer`
  (`discovery, status, nudge, warning` from `builder`), `tester` (`discovery, status, nudge` from
  `builder`), `chief` (`status, nudge, discovery` from any author), and `anonymous`, the union of
  the reviewer and tester walls (SPEC § C4).
- `NEVER_WITHHELD_TYPES = frozenset({"decision", "constraint", "goal", "task", "escalation"})`.
- `row_allowed(row, policy, caller_run_id) -> bool`: a row is withheld only when its `type` is in
  `exclude_types` and (`exclude_authors` is empty, or its `author_role` is in `exclude_authors`, or
  its `author_source` is `"none"`). It is never withheld when its type is in
  `NEVER_WITHHELD_TYPES`, or when its `author_run_id` equals `caller_run_id` (own posts). The row's
  body `run_id` and `from_agent` are never read.
- `policy_predicate(policy, caller_run_id) -> tuple[str, list]`: the same rule as a SQL fragment
  over `comms_messages` columns (`type`, `author_role`, `author_source`, `author_run_id`), with `?`
  parameters, to be ANDed into a `WHERE`. An empty policy returns `("1=1", [])`.

The module imports only the standard library: it is in `runner/`, and the provenance columns it names
are added to the real table by a later ticket. Tests build rows as plain dicts and run the predicate against an in-memory SQLite
table with those columns, so they do not need the migration.

## Not in this ticket

- Resolving which policy applies to a role or feature: ticket 02.
- Calling the predicate from any query: a later plan (RRP-4, RRP-5).
- The `author_*` columns on the real table: the provenance-columns ticket.

## Done when

- `python -m pytest tests/comms_board/test_read_policy.py -q` passes and covers: type only, author
  only, type and author, empty lists, every never-withheld type kept, own-run rows kept, an
  unverified (`author_source="none"`) row of an excluded type withheld, a body `run_id` equal to
  the caller's run not exempting a row.
- The same test runs `policy_predicate` against an in-memory table seeded with a generated matrix
  of rows (every type × author_role × author_source × own/other run) for each built-in policy, and
  asserts the selected ids equal the rows `row_allowed` keeps.
- `runner/read_policy.py` imports nothing from `pathly_orchestrator`.

```check
$ python -m pytest tests/comms_board/test_read_policy.py -q -p no:cacheprovider
exit 0
prints passed
$ python -c "import ast,sys; t=ast.parse(open('src/pathly_orchestrator/runner/read_policy.py',encoding='utf-8').read()); bad=[n for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and (n.module or '').startswith('pathly_orchestrator')]; print('internal imports:', len(bad))"
prints internal imports: 0
```

## Reference

- SPEC.md § C1 (policy shape, never withheld, own posts), § C2 (defaults incl. `chief`), § C3
  (one predicate, a pure twin, they must agree), § C4 (`anonymous`)
- `src/pathly_orchestrator/db/queries/app_settings.py` (`get_board_scope`, read only here)
- `src/pathly_orchestrator/runner/board_scope.py` (read only here)

## Answer

**Built**: `src/pathly_orchestrator/runner/read_policy.py` (new; stdlib only), `tests/comms_board/test_read_policy.py` (new, committed first as a failing test), regenerated `tests/INDEX.md` and `tests/comms_board/INDEX.md`.

**Proof**:
- `python -m pytest tests/comms_board/test_read_policy.py -q -p no:cacheprovider` -> 21 passed, exit 0. Covers type only, author only, type+author, empty lists, each never-withheld type, own-run kept, `author_source="none"` withheld, body `run_id` not exempting, and the predicate vs `row_allowed` matrix (type x author_role x author_source x own/other/null run) for all four built-ins, with and without a caller run.
- The AST import check printed `internal imports: 0`.
- Test-first: the test-only commit failed at collection (module missing) before the code existed.
- Build, Test (890 passed, 2 skipped), file-size, mirror-reads, test-index and lint-imports all pass. `black --check` reports 4 files (code_context*.py, code/query.py, test_code_context_codeintel.py) that were already unformatted before this ticket; none are mine.

**Decisions**:
- `chief` has no `exclude_authors` (any author). `anonymous` = union of reviewer and tester walls: types discovery/status/nudge/warning, authors builder.
- Never-withheld types are dropped from the predicate's type list, so `exclude_types` containing `decision` has no effect.
- An empty or None `caller_run_id` means no own-run exemption; a NULL `author_run_id` never counts as own.
- `exclude_authors` empty withholds the type from any author; `author_source="none"` is withheld even when the author list is set. NULL columns are COALESCEd so `NOT (...)` never yields NULL.

**Shortcuts taken**: none.

**For later tickets**: `policy_predicate` emits unqualified column names, so a query that joins tables or aliases `comms_messages` must make the columns unambiguous. The policy has a `global` key, so it is built with the functional `TypedDict` syntax. Resolution (ticket 02) must treat `anonymous` as a built-in key.
