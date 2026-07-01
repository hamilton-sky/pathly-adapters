# PO Notes — pathly-entity-model

_Last updated: 2026-06-29_

## Who Is This For

Pathly platform engineers and anyone running board-driven multi-agent workflows — in
particular, users who decompose **project goals** (not just feature-tier goals) via the
Command Center. The immediate pain point is the confirmed production bug where
project-goal consultation runs loop forever on `PO_DISCUSSING`, making project-level
orchestration unusable. Secondary users: all downstream agents who rely on artifacts
appearing on the board automatically.

## Definition of Success

1. **Bug fixed:** a project goal decomposed via consultation or team mode advances past
   `PO_DISCUSSING` — the forever-loop is eliminated. (Measurable: drive one real
   consultation decompose end-to-end and confirm FSM advances.)
2. **Structural guarantee:** every artifact written by any agent (DAG task OR single/taskless
   run) appears on the board — not advisory, not dependent on the agent remembering to POST.
3. **Clean entity model:** `scope` (board addressing tier) and `slug` (filesystem identity)
   are separated at every call site; no code conflates them.
4. **Planner artifact parity:** the planner produces a named artifact (`DAG_PLAN.md`,
   `IMPLEMENTATION_PLAN.md`) in every mode, including the current artifact-less light path.
5. **Sidebar completeness:** Command Center left rail shows features, goals, lessons, and
   explorations — not just features.

## Out of Scope

- Renaming `pathly/plans/` → `pathly/features/` (pure blast radius, zero behavioral gain).
- Kind-partitioning lessons / explorations / debugs into per-slug folders (forces a migration,
  no navigation value).
- Making board POST mandatory or blocking in agent hot path (violates the fragment doctrine;
  the reconciler handles eventual-consistency).
- A second per-folder manifest file (`ENTITY.json`) — `STATE.json` + `slug` column +
  `ARTIFACTS.jsonl` already give durable identity.
- Adding `artifact-register` to `composition.yaml defaults:` (oversprays into non-pipeline
  skills like `planning/evaluate`).

## Constraints

- **Phased delivery:** each phase must be independently shippable and backward-compatible with
  live features. Phase 0 (guard only) can ship in days; Phase 1 (bug fix) gates Phase 2.
- **Atomic landing for `planning/dag-sketch`:** skill file + manifest entry +
  `composition.yaml` entry + `_decompose_planner` edit must land in ONE commit; partial
  deploy causes the planner to call a non-existent skill and error.
- **RESERVED set must extend in Phase 1:** Studio must add `goals, lessons, explorations,
  debugs, pipeline-walkthrough` to the RESERVED set before the `pathly/goals/` folder
  exists, or goals surface as phantom features in the sidebar.
- **Watcher depth invariant:** all storage paths must be exactly `pathly/<domain>/<slug>/`
  (two components under `pathly`) to keep `_agent_done_watcher`'s
  `project_root = feature_dir.parent.parent.parent` computation correct.
- **SOLID file-size limit:** 400 lines per file; any touched file approaching this must be
  split before new code is added.
- **Adapter sync required** for any `core/` changes: `pathly-setup claude --apply --repair`
  + `python -m build`.
- **No master push** without explicit user request.

## Open Questions

1. **Goal storage location:** `pathly/goals/<slug>/` (recommended — keeps feature contract
   pure, enables sidebar grouping by parent folder) vs. goals under `pathly/plans/<slug>/`
   (simpler discovery, mixes kinds). _Working assumption: separate `pathly/goals/`._

2. **Single-agent / taskless runs:** require a declared role (inherits named artifact +
   contract) vs. keep free-form board-post. _Working assumption: role is optional — if set,
   the agent gets the artifact contract; otherwise free-form posting is fine._

3. **`_safe_topic` rollout:** WARN-then-RAISE over two releases vs. RAISE immediately (the
   only runs hitting it are already looping forever). _Working assumption: RAISE immediately._

4. **Lessons in sidebar:** single "Lessons" collection node (keeps flat `LESSONS.md`) vs.
   promote each lesson to its own card. _Working assumption: single collection node._
