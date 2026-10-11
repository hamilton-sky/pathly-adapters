# Resolve the read policy for a role and feature from settings, then built-in defaults

Type: task
Status: open
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
