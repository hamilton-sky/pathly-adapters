# Implementation Plan — skill-composition-kit

Swap the existing `components/SkillComposition/` panel with the redesigned `pathly/SkillCompositionKit/`. Three phases: copy, rewire, typecheck.

---

## Phase 1 — Copy kit folder to studio components

**File:** `studio/src/renderer/src/components/SkillCompositionKit/` (whole directory)

**Purpose:** Get the kit source into the studio component tree so TypeScript can see it.

**Depends on:** `pathly/SkillCompositionKit/` exists (it does — verified)

**Enables:** Phase 2 (App.tsx import update) and Phase 3 (typecheck)

**Steps:**
1. Copy `pathly/SkillCompositionKit/` → `studio/src/renderer/src/components/SkillCompositionKit/`
   - Use PowerShell `Copy-Item -Recurse` or equivalent (preserve all files including CSS modules)
2. Verify `integration.ts` import paths are correct for its new location:
   - `../../services/skillComposition` resolves to `studio/src/renderer/src/services/skillComposition.ts` ✓
   - `../../store/projectStore` resolves to `studio/src/renderer/src/store/projectStore.ts` ✓
   - These paths are already correct — **no changes needed**
3. Do NOT edit any other file in this phase.

**Done when:** `studio/src/renderer/src/components/SkillCompositionKit/index.ts` exists and `integration.ts` import paths are confirmed correct.

**Verify:** `ls studio/src/renderer/src/components/SkillCompositionKit/ | wc -l` returns 10+ entries (top-level files + component subfolders)

**Depends on:** nothing

**Recovery:** If the copy fails, retry. No existing files are touched in this phase — it is purely additive.

---

## Phase 2 — Swap App.tsx import + delete old folder

**File:** `studio/src/renderer/src/App.tsx`

**Purpose:** Make the running app use the new kit and clean up the old component tree.

**Depends on:** Phase 1 (kit folder in place)

**Enables:** Phase 3 (typecheck against the new import)

**Steps:**
1. Open `studio/src/renderer/src/App.tsx`
2. Change line 19:
   ```
   // Before
   import { SkillComposition } from './components/SkillComposition/SkillComposition'
   // After
   import { SkillComposition } from './components/SkillCompositionKit'
   ```
3. Delete `studio/src/renderer/src/components/SkillComposition/` (the old folder):
   - Verify no other file outside this folder imports from it first:
     `grep -r "from.*components/SkillComposition" studio/src --include="*.ts" --include="*.tsx"`
   - If no external consumers remain, delete the folder.
4. Do NOT touch any other files in this phase.

**Done when:** `App.tsx` imports from `./components/SkillCompositionKit`; `components/SkillComposition/` folder is gone.

**Verify:** `grep -n "SkillComposition" studio/src/renderer/src/App.tsx` shows only the new import path.

**Depends on:** Phase 1

**Recovery:** If any file outside `components/SkillComposition/` imports from the old folder, update that import before deleting. Use `git checkout studio/src/renderer/src/App.tsx` to revert App.tsx if needed.

---

## Phase 3 — TypeScript check + fix any errors

**File:** any files with TypeScript errors (start with the new `SkillCompositionKit/` files)

**Purpose:** Confirm the kit compiles cleanly in the studio TypeScript context.

**Depends on:** Phase 2 (App.tsx updated)

**Steps:**
1. Run from repo root:
   ```
   node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json 2>&1
   ```
2. If errors appear:
   - Errors in kit files: fix the kit source in `components/SkillCompositionKit/`
   - Errors in `App.tsx`: fix the import
   - Errors elsewhere: likely stale references to the deleted `SkillComposition/` — update them
3. Re-run typecheck until 0 errors.
4. If the fix requires out-of-scope changes (e.g. missing types in services), stop and report. Do not silently modify service files.

**Done when:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0.

**Verify:** Command above returns no output and exit code 0.

**Depends on:** Phase 2

**Recovery:** If typecheck errors are intractable, `git checkout studio/src/renderer/src/components/SkillCompositionKit/` to restore the kit files and iterate on the fix.
