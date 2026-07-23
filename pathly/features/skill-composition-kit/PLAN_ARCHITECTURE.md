# Plan Architecture — skill-composition-kit

## Design Decisions

### 1. Folder name: `SkillCompositionKit` (not `SkillComposition`)

The kit lands as `components/SkillCompositionKit/` — a new name — so both the old and new folders can coexist during Phase 1 without collision. Phase 2 deletes the old folder. This avoids any rename-in-place risk on Windows where chokidar holds file handles.

### 2. Single wiring point — `integration.ts`

The kit touches Pathly only through `integration.ts`. All service calls and the `useProjectPath` hook pass through there. This means:
- No kit file (other than `integration.ts`) imports from `services/` or `store/`
- After the copy, only `integration.ts` needs verification (and it already has correct paths)
- Future service refactors require a change in one file only

### 3. App.tsx imports the barrel (`index.ts`)

`App.tsx` imports `{ SkillComposition }` from `./components/SkillCompositionKit` (the `index.ts` barrel), not the deep component path. This keeps the import stable if the kit reorganizes its internals.

### 4. No changes to services or store

`services/skillComposition.ts` and `store/projectStore.ts` are unchanged. The kit reuses the same four API functions (`fetchSkillComposition`, `previewComposedSkill`, `saveSkillCompositionOverride`, `resetSkillComposition`) and the same `useProjectPath()` hook. This keeps the blast radius minimal.

### 5. Placeholder data files stay as-is

`data/fragmentMeta.ts`, `data/abilities.ts`, and `data/systemPrompt.ts` carry curated stand-in values (token counts, ability descriptions, system-prompt base). They are valid as-is and will be replaced with real library-table values in a follow-on task — out of scope for this feature.

---

## Phase Mapping

### Phase 1 — Copy

Copy is a filesystem operation. No TS compilation happens here. The only architectural constraint: the `../../` relative paths in `integration.ts` are pre-calculated for the `components/SkillCompositionKit/` destination and must not be changed.

### Phase 2 — Rewire

One-line import change in `App.tsx`. The barrel (`index.ts`) re-exports `SkillComposition` from `./SkillComposition/SkillComposition` — so the public surface is identical to the old import, and the panel ID `'skill-composition'` (a string in `Sidebar.tsx`, `BottomNav.tsx`, `IconStrip.tsx`) is unchanged.

### Phase 3 — Typecheck

The kit is self-contained TypeScript. The only external surface is `integration.ts` — if `services/skillComposition.ts` types have diverged from what the kit expects (`SkillCompositionCatalog`, `SkillCompositionEntry`, `ComposedSection`), Phase 3 will surface it. Fix in `integration.ts` (or rarely the service types) — never in the kit's internal files.
