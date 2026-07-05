# storage-restructure Phase 2 — Progress

Feature-centric layout dogfood: this feature lives at `pathly/features/storage-restructure-p2/`
(the very layout Phase 2 delivers). Its board (goal + Task DAG) is DB-backed under
`scope=storage-restructure-p2` and is **authoritative** — this table was re-synced from it +
the code on **2026-07-02** (the previous all-TODO table was stale).

| Task | Status | Description |
|---|---|---|
| T1 | ✅ DONE | Feature-aware resolver — `_resolve_storage_path` (fsm_ops.py:69-84) probes `pathly/features/<topic>` then `pathly/<topic>`; a nested `features/<f>/goals/<slug>` topic resolves via the second candidate. |
| T2 | ✅ DONE | `goal_decomposer` 3 write sites route to the nested dir via `_goal_storage_dir`/`_goal_topic` (planner :156, plan :230, consultation :306). |
| T3 | ✅ DEFERRED (by design) | project/global scope homes. Helper collapses **project AND global** to `pathly/project/goals/<slug>`; the SPEC's global → `~/.pathly/` home is **not** stood up. **Decision (2026-07-03): keep the deferral** — global goals are rare and the collapse is harmless. Documented in `pathly/features/storage-restructure/SPEC.md` (T3 note); board task `136db628` closed with that reason. Stand up `~/.pathly/` only on concrete need. |
| T4 | ✅ DONE (via T6) | Legacy flat `pathly/goals/<slug>` probe was removed from the resolver (fsm_ops.py:81-82) once features+goals nest by scope. The straggler in `goal_executor._run_loop` is fixed under T6. |
| T5 | ✅ DONE | Tests — `test_resolve_storage_path_*` (test_fsm_ops.py:778-805) + `test_build_prompt_uses_parent_board_scope_for_goal` (:676-698). Full suite green. |
| T6 | ✅ DONE (2026-07-03) | Loop-executor storage path reconciled: `goal_executor._run_loop` now uses `_goal_storage_dir(project_root, board, scope, slug)` (imported from `goal_decomposer`) instead of flat `pathly/goals/<slug>`; stale `supervisor/state.py:99` comment fixed; consistency test `test_dispatch_loop_creates_nested_goal_dir` (test_comms_goals_run.py) asserts the loop dir nests under `features/<f>/goals/<slug>` and never creates flat `pathly/goals/`. |

## Remaining work

All P2 tasks are resolved (2026-07-03). T3 kept deferred by design (documented in the SPEC,
board task closed); T6 fixed and covered by a consistency test. The loop-executor goal dir now
matches the decompose/team goal dir for the same goal.

This work landed together with the broader **storage-path consolidation** (production-readiness
T2/T3): a single feature-dir resolver (`_resolve_storage_path`, now flow-less-capable) is the
one home, ~15 hardcoded `pathly/plans/` sites across telemetry / health / streams / runner-event
/ supervisor / otel / feedback-watcher / registry were routed through it (or widened to
`features/ ∪ plans/`), and a layout-invariant safety-net test
(`tests/test_storage_layout_invariant.py`) pins every subsystem to the same flat home.

Board: goal `998dea8e` on `scope=storage-restructure-p2`. Design: `pathly/features/storage-restructure/SPEC.md`.
