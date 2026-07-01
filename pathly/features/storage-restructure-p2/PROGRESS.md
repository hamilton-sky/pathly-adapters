# storage-restructure Phase 2 — Progress

Feature-centric layout dogfood: this feature lives at `pathly/features/storage-restructure-p2/`
(the very layout Phase 2 delivers). Its board (goal + Task DAG) is DB-backed under
`scope=storage-restructure-p2`.

| Task | Status | Description |
|---|---|---|
| T1 | TODO | Feature-aware resolver — add `features/<feature>/goals/<slug>` candidate to `_resolve_storage_path` |
| T2 | TODO | Route `goal_decomposer` 3 write sites (planner/plan/consultation) to `features/<feature>/goals/<slug>` |
| T3 | TODO | Stand up `pathly/project/` + `~/.pathly/` scope homes |
| T4 | TODO | Preserve legacy probe — existing `pathly/goals/<slug>` still resolves |
| T5 | TODO | Tests — nested goal-path resolution + back-compat in `test_fsm_ops` |

Board: goal `998dea8e` on `scope=storage-restructure-p2`. Design + phase plan:
`pathly/features/storage-restructure/plans/SPEC.md`.
