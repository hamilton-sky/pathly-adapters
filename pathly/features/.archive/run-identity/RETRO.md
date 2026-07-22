# RETRO — run-identity

**Shipped:** 2026-07-22 · branch `dogfood/run-identity`, commit `66fd8eb6` · goal `460f8f5b` (6/6 tasks) · in-session build

## Outcome

Identity is now ISSUED at spawn — `run_id` (primary) + `board_scope` + slug land as
first-class columns on `fsm_events`, `agent_invocations`, and `run_history` — instead of
being re-derived from storage location by every consumer. `/db/rollup` and the goal detail
show a goal run's cost under BOTH its slug and its parent feature; legacy NULL rows keep
the exact old behavior. 19 new tests; suite 1438/5; black + mirror gate clean.

## What went well

- **One derivation, no drift**: extracting `resolve_board_scope` from `build_prompt` and
  reusing it in the supervisor stamp paths means the prompt's `<feature>` and the stamped
  column can never disagree — the entire bug class had been *two* derivations diverging.
- **The grounding step earned its keep**: a real-DB query (task 4) confirmed 41/96
  `run_history` rows keyed by full topic paths before designing the shim; and testing
  surfaced a latent split-key bug (backslash `project_root` in `run_history`) that the
  same `_norm` chokepoint now closes.
- Extracting the synthesis closure to a module function made the COALESCE guarantees
  directly testable (both never-overwrite directions).

## Deviations (flagged on the board as they happened)

- 6 compose snapshots changed, not the predicted 7 — `team/retro` doesn't compose
  `completion-report`; it references `log-agent-done` by name only.
- Tasks shared full-suite gates in pairs (2+3, 4+5+6) to save two ~12-min suite runs;
  each task's targeted tests ran individually first.
- Task 6 was claimed before 4/5 completed on the board (in-session sequential build);
  completes were ordered correctly.

## Lesson candidate

When a table serves as an identity map, make the write chokepoint normalize + COALESCE
(issue-once) at the QUERY-HELPER level, not at call sites — the third caller you didn't
know about is the one that splits the key.
