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

**Built**: `src/pathly_orchestrator/runner/read_policy.py` (ReadPolicy, BUILTIN_DEFAULTS, NEVER_WITHHELD_TYPES, row_allowed, policy_predicate); `tests/comms_board/test_read_policy.py` (21 tests); regenerated `tests/INDEX.md` and `tests/comms_board/INDEX.md`.

**Proof**: `pytest tests/comms_board/test_read_policy.py` -> 21 passed (rules plus a matrix of every type x role x source x own/other/none run, for each of 4 built-ins and caller run set/None, predicate ids == row_allowed ids). Import check printed `internal imports: 0`. Test-only commit made first and failed on import. Test command (4 domains): 890 passed, 2 skipped. compileall, check_file_size, gen_test_index --check, lint-imports all OK.

**Decisions**: ReadPolicy uses the functional TypedDict form since `global` is a keyword. `anonymous` = type union (discovery, status, nudge, warning) with author `builder`. A None caller_run_id grants no own-post exemption. The predicate wraps columns in COALESCE so NULLs never make a row vanish.

**Shortcuts taken**: none.

**For later tickets**: `black --check src/ tests/` already fails on 4 files before this ticket (code_context_codeintel.py, test_code_context_codeintel.py, blueprints/code/query.py, code_context.py), so the Lint command fails on a clean tree; not mine. Predicate param order: excluded types, then caller run id (if any), then authors.
