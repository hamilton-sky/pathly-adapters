# Happy Flow — pathly-entity-model

_Last updated: 2026-06-29_

Each conversation's golden path. This is a build reference — concrete steps the builder
executes in sequence, not a narrative summary.

---

## Conv 0 — Phase 0: Guard

**Starting state:** clean working tree; `comms_messages` has no `slug` column; `_safe_topic`
does not exist.

**Reads first:**
- `src/pathly_orchestrator/fsm_ops.py` (lines 60–80 around `_resolve_storage_path`)
- `src/pathly_orchestrator/runner/argv.py` (lines 1–30 around `_storage_path`)
- `src/pathly_orchestrator/db/migrations.py` (full file — locate the incremental migration pattern)

**Writes (in order):**

1. `src/pathly_orchestrator/fsm_ops.py` — add `_safe_topic` function near the top of the file;
   add `_safe_topic(topic)` call at line 68 (top of `_resolve_storage_path`).
2. `src/pathly_orchestrator/runner/argv.py` — add `_safe_topic(topic)` call inside
   `_storage_path` (defense-in-depth; import from `fsm_ops`).
3. `src/pathly_orchestrator/db/migrations.py` — append two statements in the incremental
   migration block:
   - `ALTER TABLE comms_messages ADD COLUMN slug TEXT` wrapped in try/except for
     `OperationalError` with "duplicate column" in message.
   - `CREATE UNIQUE INDEX IF NOT EXISTS idx_comms_messages_slug ON comms_messages(slug) WHERE slug IS NOT NULL`
4. `tests/test_fsm_ops.py` — write 8 test cases (5 raise-cases + 1 valid-slug case +
   1 slug-column-exists case + 1 duplicate-slug raises case). See IMPLEMENTATION_PLAN.md
   test requirements for exact names.

**Runs to verify:**
```
pytest tests/test_fsm_ops.py -v
pytest tests/ -q   # regression check — no existing test may break
```

**Done when:**
- All 8 tests in `test_fsm_ops.py` pass.
- `_safe_topic` is importable: `python -c "from pathly_orchestrator.fsm_ops import _safe_topic; print('ok')"`.
- DB migration is idempotent: run the migration twice in the test, second run does not raise.
- Full test suite passes.

---

## Conv 1 — Phase 1: Bug Fix

**Starting state:** Phase 0 complete; `_safe_topic` exists and raises; `slug` column in DB.
**Pre-condition check:** run `pytest tests/test_fsm_ops.py -v` before touching any file.

**Reads first:**
- `src/pathly_orchestrator/supervisor/terminal.py` (full file — count lines; locate `:39`,
  `:86`, `:269`, `:307`)
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` (lines 230–260)
- `src/pathly_orchestrator/supervisor/goal_executor.py` (lines 20–70, 215–235, 310–335)
- `src/pathly_orchestrator/supervisor/board_run.py` (lines 140–160, 240–260)
- `src/pathly_orchestrator/supervisor/registry.py` (lines 140–155)
- `src/pathly_orchestrator/supervisor/orchestrator.py` (lines 330–340)
- `studio/src/renderer/src/store/commsStore.ts` (lines 130–150)

**Writes (in order — strictly sequential; each step must pass its own test before proceeding):**

1. **Split `terminal.py` first** (must pass tests before any other change):
   - Create `src/pathly_orchestrator/supervisor/terminal_write.py` — move summary-write and
     path-reconstruction logic (`:39`, `:269`, `:307`).
   - Keep `_agent_done_watcher` (`:86`, with `parent.parent.parent`) in `terminal.py`.
   - Add re-exports to `terminal.py` so existing imports resolve.
   - Verify: `pytest tests/ -q` passes. No file exceeds 400 lines.

2. **Create `supervisor/slug.py`** with `ensure_goal_slug` and `_slugify`. See reference
   implementation in IMPLEMENTATION_PLAN.md.

3. **Update all 10+ collapse sites** (one file at a time; grep for `topic=scope` after each
   file to track progress):
   - `goal_decomposer.py:239` (reset call)
   - `goal_decomposer.py:246` (`_decompose_consultation`)
   - `goal_executor.py:52`
   - `goal_executor.py:223`
   - `goal_executor.py:317`
   - `goal_executor.py:321`
   - `orchestrator.py:336`
   - `board_run.py:147` (add `slug` param to `start_board_run`)
   - `board_run.py:247`
   - `registry.py:148-149`
   - `terminal.py:39, 269, 307` — thread `storage_path` from caller (already in split file)

4. **Add `goals/<slug>` probe branch** to `_resolve_storage_path` in `fsm_ops.py` (after
   the existing `plans/<slug>` probe; same depth invariant).

5. **Extend the RESERVED set** in `studio/src/renderer/src/store/commsStore.ts:140`:
   ```typescript
   const RESERVED = new Set([
     'plans', '.archive', 'goals', 'lessons',
     'explorations', 'debugs', 'pipeline-walkthrough'
   ])
   ```

6. **Write tests:**
   - `tests/test_goal_slug.py` — idempotency + concurrency cases (see IMPLEMENTATION_PLAN.md).
   - `tests/test_goal_slug.py::test_project_goal_consultation_end_to_end` — ONE REAL
     consultation decompose for a project goal (no mocked FSM transitions).

**Runs to verify (in order):**
```
grep -r "topic=scope" src/pathly_orchestrator/supervisor/   # must return zero matches
pytest tests/test_goal_slug.py -v
pytest tests/ -q
npx tsc --noEmit -p studio/tsconfig.web.json
```
Then run a real consultation decompose manually and confirm `pathly/goals/<slug>/PO_NOTES.md`
exists after the run.

**Done when:**
- Grep for `topic=scope` returns zero in supervisor source.
- `pathly/goals/<slug>/PO_NOTES.md` exists after a real project-goal run.
- No file in supervisor package exceeds 400 lines.
- RESERVED set contains all 7 entries.
- TypeScript compiles clean.
- Full test suite passes.

---

## Conv 2 — Phase 2: Artifact Contract

**Starting state:** Phase 1 tests passing; `slug` column active; `goals/` probe in FSM.
**Pre-condition check:** run `pytest tests/test_goal_slug.py -v` and confirm pass before
writing any Phase 2 file.

**Reads first:**
- `src/pathly_data/core/skills/composition.yaml` (lines 1–50, then lines 110–170)
- `src/pathly_orchestrator/db/queries/comms_artifacts.py` (full file)
- `src/pathly_orchestrator/http_server/blueprints/fsm.py` (`/complete_stage` route)
- `src/pathly_orchestrator/supervisor/goal_decomposer.py` (lines 110–155)

**Branch first:** all 7 files go on a local branch; commit atomically at the end.

**Writes (all must exist before committing — do not commit partial sets):**

1. `src/pathly_data/core/skills/artifact-manifest.yaml` — 9 role entries + 1 override.
   Shape: see IMPLEMENTATION_PLAN.md §artifact-manifest.yaml shape.

2. `src/pathly_data/core/skills/fragments/artifact-register.md` — instruction fragment:
   write named artifact to `<out_path>`, append one JSONL line, advisory board POST.

3. `src/pathly_data/core/skills/planning/dag-sketch.md` — skill body: decompose into 3-7
   tasks, write `DAG_PLAN.md` with `## Tasks` table, post each task.

4. `src/pathly_data/core/skills/composition.yaml` — add `planning/dag-sketch` entry with
   `fragments: [artifact-register]`; add `artifact-register` per-skill to the 7 pipeline
   roles listed in IMPLEMENTATION_PLAN.md §composition.yaml rules. Do NOT touch `defaults:`.

5. `src/pathly_orchestrator/supervisor/goal_decomposer.py` — edit `_decompose_planner`:
   `skill="" → skill="planning/dag-sketch"`; delete "Do NOT create plan files" instruction.

6. `src/pathly_orchestrator/db/queries/comms_artifacts.py` — add `ensure_attached` function
   after existing `insert_artifact`. See IMPLEMENTATION_PLAN.md §ensure_attached contract.
   Wire into `complete_stage` (thread `board`/`scope`) and supervisor post-PTY path.

7. **Run adapter sync** (this produces the 4-adapter output files):
   ```
   pathly-setup claude --apply --repair
   python -m build
   ```

**Runs to verify (before committing):**
```
python -m build   # must pass; validate_composition must not error
pytest tests/test_artifact_reconcile.py -v
pytest tests/test_compose.py -v
```

**Commit atomically:**
```
git add src/pathly_data/core/skills/artifact-manifest.yaml \
        src/pathly_data/core/skills/fragments/artifact-register.md \
        src/pathly_data/core/skills/planning/dag-sketch.md \
        src/pathly_data/core/skills/composition.yaml \
        src/pathly_orchestrator/supervisor/goal_decomposer.py \
        src/pathly_orchestrator/db/queries/comms_artifacts.py \
        <adapter-sync-output-files>
git diff --staged   # verify exactly the 7 core files + adapter outputs are staged
git commit -m "feat(artifact-contract): atomic Phase 2 — manifest + register + dag-sketch + reconciler"
```

**Verify commit:**
```
git show --stat HEAD
```

**Done when:**
- `git show --stat HEAD` shows all 7 artifacts in one commit.
- `python -m build` succeeds on a clean checkout.
- `pytest tests/test_artifact_reconcile.py` passes.
- `pytest tests/test_compose.py` passes with regenerated snapshots.
- After a light-mode decompose, `goals/<slug>/DAG_PLAN.md` exists with `## Tasks` section.
- `ensure_attached` inserts exactly one row for duplicate calls.

---

## Conv 3 — Phase 3: Sidebar

**Starting state:** Phase 1 RESERVED set extended; renderer-only work; no Python changes.
**Parallel-safe:** this conversation may overlap Phase 2 because it touches different files.

**Reads first:**
- `studio/src/renderer/src/store/commsStore.ts` (full file)
- `studio/src/renderer/src/types.ts` (full file)
- `studio/src/renderer/src/components/CommandCenter/CommandCenter.tsx` (full file)
- `studio/src/renderer/src/components/CommandCenter/FeatureSidebar/` (all files — understand
  the existing sidebar contract before replacing it)
- `studio/src/renderer/src/styles/` (skim tokens — override any DESIGN.md token that
  conflicts with existing Studio tokens)

**Writes (in order):**

1. `studio/src/renderer/src/types.ts` — add `CardKind`, `Card` superset, keep
   `Feature = Card & {kind:'feature'}`. Ensure existing usages of `Feature` still compile.

2. `studio/src/renderer/src/store/commsStore.ts`:
   - Add `cards: Card[]` property to the store state.
   - Change `loadFeatures` → `loadCards`; `loadCards` must scan all four card kinds.
   - Replace `set({features})` with `set({cards})`; add `get features()` getter that returns
     `this.cards.filter(c => c.kind === 'feature')`.
   - Extend RESERVED set (already done in Phase 1; confirm it is present).
   - Any component reading `store.features` must still compile — the getter preserves the API.

3. **Create `CardSidebar/` folder:**
   - `studio/src/renderer/src/components/CommandCenter/CardSidebar/CardSidebar.tsx` — grouped
     collapsible sections; `data-kind` attribute; dot clusters in collapsed rail; Decompose/Run
     buttons on goal cards; lesson click opens MarkdownEditor. See IMPLEMENTATION_PLAN.md
     §CardSidebar design contract for all constraints.
   - `studio/src/renderer/src/components/CommandCenter/CardSidebar/CardSidebar.module.css` —
     CSS Modules; `data-kind` selectors; `min-width: 0` on flex children; no `overflow: hidden`
     on sidebar container.

4. `studio/src/renderer/src/components/CommandCenter/CommandCenter.tsx` — wire `CardSidebar`
   behind a feature flag (boolean in store or `localStorage` key); keep `FeatureSidebar` as
   fallback when flag is `false`.

**Runs to verify:**
```
npx tsc --noEmit -p studio/tsconfig.web.json
```
Confirm in the renderer:
- Features section renders correctly.
- Goals section absent when no goals exist on disk.
- `FeatureSidebar` still mounts when flag is `false`.
- Collapsed rail (48px) shows dot clusters for non-empty sections.

**Done when:**
- `CardSidebar` component exists and renders all four card kinds correctly.
- Empty groups are not rendered.
- Collapsed rail shows dot clusters.
- `store.features` getter returns only `kind === 'feature'` cards.
- `FeatureSidebar` still compiles as a fallback.
- TypeScript compiles clean: `tsc --noEmit` with `tsconfig.web.json`.
- Goal cards show Decompose and Run buttons.
- Lesson card click opens the `.md` file in the MarkdownEditor panel.
