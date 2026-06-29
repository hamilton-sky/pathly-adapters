# Feature Index — pathly-entity-model

_Last updated: 2026-06-29_

## What this is

A four-phase structural repair to the Pathly entity model that fixes a confirmed production bug
(project-goal consultation looping forever), enforces clean separation of `scope` (board addressing
tier) vs `slug` (filesystem identity), guarantees every pipeline artifact lands on the board, and
extends the Command Center sidebar to show goals, lessons, and explorations alongside features.

The root cause of the production bug: every call site passes `topic = scope` into the FSM.
For features, scope equals the slug, so the path resolves correctly. For project goals, scope
is an absolute path; pathlib discards left operands when the right operand is absolute, collapsing
the storage path to the project root. The PO_NOTES gate never matches, and the FSM re-spawns the
PO forever.

## The 4 phases

| Phase | Name | Gates | Key deliverable |
|---|---|---|---|
| 0 | Guard | none (ships independently) | `_safe_topic` WARN + nullable `slug` column + UNIQUE index |
| 1 | Bug fix | Phase 0 | slug routing at ALL collapse sites + Studio RESERVED-set extension + `_safe_topic` RAISE |
| 2 | Artifact contract | Phase 1 passing | Atomic: manifest + fragment + dag-sketch skill + reconciler |
| 3 | Sidebar | Phase 1 (renderer-only) | `CardSidebar` grouped collapsible sections behind flag |

## Key constraints to remember

- **RESERVED-set extension is Phase 1**, not Phase 3. Phase 1 creates `pathly/goals/` on disk;
  without the extension, `goals` surfaces as a phantom feature in the sidebar.
- **Phase 2 is atomic**: exactly 7 artifacts must land in ONE commit (partial deploy causes planner
  to call a non-existent skill and crash).
- **`_safe_topic` RAISES immediately** (not WARN) — this is the user's decision per board message.
  No WARN soak. Phase 0 ships it as RAISE.
- **Watcher depth invariant:** all storage paths are exactly `pathly/<domain>/<slug>/` — two
  components under `pathly`. `terminal.py:86` `parent.parent.parent` MUST NOT change.
- **SOLID 400-line limit:** `terminal.py` (407 lines) must be split BEFORE adding new code.
  `goal_executor.py` (347 lines) and `board_run.py` (335 lines) must use `_helpers.py` extraction
  rather than growing the files.
- **`plans/ → features/` rename is Out-of-Scope** (PO_NOTES #1).
- **No master push** without explicit user request.

## Files changed — summary by phase

### Phase 0
- `src/pathly_orchestrator/fsm_ops.py` (`:68` — add `_safe_topic` + RAISE + `goals/` probe)
- `src/pathly_orchestrator/runner/argv.py` (`:13` — defense-in-depth `_safe_topic`)
- `src/pathly_orchestrator/db/migrations.py` (add nullable `slug` column + UNIQUE index to `comms_messages`)
- `tests/test_fsm_ops.py` (new: absolute-path and normal-slug cases)

### Phase 1
- `src/pathly_orchestrator/supervisor/slug.py` (NEW — `ensure_goal_slug`)
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` (`:246` `_decompose_consultation` + `:239` reset call)
- `src/pathly_orchestrator/supervisor/goal_executor.py` (`:52` `_reset_fsm_state_for_flow`; `:223` `_run_loop`; `:317` + `:321` `_run_team` — both sites)
- `src/pathly_orchestrator/supervisor/board_run.py` (`:147` add `slug` param; `:247` extend `where_line` probe)
- `src/pathly_orchestrator/supervisor/terminal.py` (split file first; then thread `storage_path` at `:39`, `:269`, `:307`; PRESERVE `:86`)
- `src/pathly_orchestrator/supervisor/orchestrator.py` (`:336` slug routing)
- `src/pathly_orchestrator/supervisor/registry.py` (`:148-149` slug-aware `feature_dir`)
- `src/pathly_orchestrator/supervisor/_helpers.py` (extract helpers from near-limit files)
- `studio/src/renderer/src/store/commsStore.ts` (`:140` extend RESERVED set)
- `tests/test_goal_slug.py` (new: `ensure_goal_slug` idempotency + concurrency)
- Integration: one real consultation decompose end-to-end

### Phase 2 (atomic — one commit)
- `src/pathly_data/core/skills/artifact-manifest.yaml` (NEW)
- `src/pathly_data/core/skills/fragments/artifact-register.md` (NEW)
- `src/pathly_data/core/skills/planning/dag-sketch.md` (NEW)
- `src/pathly_data/core/skills/composition.yaml` (new `planning/dag-sketch` entry + per-skill attachments)
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` (`:113` `_decompose_planner` — `skill="" → "planning/dag-sketch"`)
- `src/pathly_orchestrator/db/queries/comms_artifacts.py` (add `ensure_attached`)
- `src/pathly_orchestrator/http_server/blueprints/fsm.py` (thread `board`/`scope` into `/complete_stage`)
- 4-adapter sync output (via `pathly-setup claude --apply --repair` + `python -m build`)
- `tests/test_compose.py` (regenerated snapshots)
- `tests/test_artifact_reconcile.py` (new: JSONL path + manifest-stat fallback)

### Phase 3
- `studio/src/renderer/src/store/commsStore.ts` (`loadFeatures → loadCards`; `cards` slice; derived `features` getter)
- `studio/src/renderer/src/types.ts` (`CardKind`; `Card` superset; `Feature = Card & {kind:'feature'}`)
- `studio/src/renderer/src/components/CommandCenter/CardSidebar/` (NEW folder + component + CSS module)
- `studio/src/renderer/src/components/CommandCenter/CommandCenter.tsx` (wire `CardSidebar` behind flag)

## Acceptance summary (binary)

- Phase 0: `pytest tests/test_fsm_ops.py` passes; `_safe_topic` raises on an absolute path.
- Phase 1: One real consultation decompose for a project goal advances past `PO_DISCUSSING`.
- Phase 2: `pytest tests/test_artifact_reconcile.py` passes; `ARTIFACTS.jsonl` + board row created.
- Phase 3: Sidebar shows Features, Goals, Lessons, Explorations sections; TypeScript compiles clean.
