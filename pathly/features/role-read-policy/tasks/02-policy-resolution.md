# Resolve the read policy for a role and feature from settings, then built-in defaults

Type: task
Status: resolved
Blocked by: 01
Test first: yes

Add `resolve_read_policy(conn, role, feature) -> ReadPolicy` to `runner/read_policy.py`
(SPEC.md § C1, "Resolution order"). Order: the per-role `board_scope` row → the per-feature row
→ `BUILTIN_DEFAULTS[role]` → everything allowed. Read the stored rows through the existing
`db/queries/app_settings.py::get_board_scope` path so tier resolution is unchanged; only the two
new keys `exclude_types` and `exclude_authors` are read from the stored value in addition.

A stored row that has no `exclude_*` keys keeps today's behaviour for that role: it does **not**
fall through to the built-in wall. That is what keeps existing per-role rows reading exactly what
they read now. An unknown role with no stored row gets the allow-all policy. `role=None` (no
caller identity) returns `BUILTIN_DEFAULTS["anonymous"]`.

`get_board_scope`'s docstring says on purpose that there is no per-role default
(`app_settings.py`); do not change that function. The built-in step lives only in
`resolve_read_policy`, so callers that use `get_board_scope` for tiers see no change.

## Not in this ticket

- Using the resolved policy in a query: a later plan.
- The Studio settings UI for the new keys: a later plan (RRP-7).

## Done when

- `python -m pytest tests/comms_board/test_read_policy_resolve.py -q` passes and covers: per-role
  row beats the built-in default; a per-role row without `exclude_*` keys reads as allow-all for
  content (back-compat); per-feature row used when no per-role row; built-in default for
  `reviewer` when nothing is stored; allow-all for an unknown role; `anonymous` for `None`.
- The existing board-scope tests still pass unchanged.

```check
$ python -m pytest tests/comms_board/test_read_policy_resolve.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/comms_board/test_board_context_scope.py tests/comms_board/test_board_context_settings.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C1 "Resolution order", § F question 1
- `src/pathly_orchestrator/db/queries/app_settings.py` (`get_board_scope`, read only)
- Ticket 01's Answer

## Answer

**Built**: `resolve_read_policy(conn, role, feature, project_root="")` in `src/pathly_orchestrator/runner/read_policy.py`; `tests/comms_board/test_read_policy_resolve.py` (committed first as a failing test, ImportError at collection); regenerated `tests/INDEX.md`, `tests/comms_board/INDEX.md`.

**Proof**:
- `python -m pytest tests/comms_board/test_read_policy_resolve.py -q -p no:cacheprovider` -> 12 passed, exit 0 (per-role beats built-in, row without exclude_* is allow-all for content, per-feature fallback, reviewer built-in, unknown role allow-all, None -> anonymous, `anonymous` as a role key, malformed row falls through, copies not shared lists).
- `python -m pytest tests/comms_board/test_board_context_scope.py tests/comms_board/test_board_context_settings.py tests/comms_board/test_read_policy.py -q` -> 61 passed.
- Build ok; Test 902 passed, 2 skipped; Lint (black, file size, mirror reads, test index, lint-imports) all exit 0.

**Decisions**:
- Added an optional `project_root=""` argument: the settings keys embed it and the ticket's signature had no way to pass it. `""` matches what `runner/board_scope.py` does.
- Tiers still come from `get_board_scope` (unchanged); a small `_stored_exclusions` walks the same two keys with the same malformed-falls-through rule to read only `exclude_types`/`exclude_authors`. Non-list values are ignored.
- A stored row sets exclude keys only if present in it; it never falls to the built-in wall. Built-in and `None` results are fresh copies. Built-in results carry no tier keys; the unknown-role allow-all carries the three tiers as True.
- `role=None` returns the anonymous built-in without reading any stored row.

**Shortcuts taken**: none.

**For later tickets**: `read_policy.py` now imports `..db.queries.app_settings` (relative import, allowed by the layer rule). Ticket 01's check "imports nothing from `pathly_orchestrator`" matches only absolute `pathly_orchestrator...` imports, so it still prints 0, but the module is no longer stdlib-only; ticket 02 requires the function to live there. Any caller must pass `project_root` to see stored rows.
