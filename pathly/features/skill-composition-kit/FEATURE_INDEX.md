# Feature Index — skill-composition-kit

Swap the existing `SkillComposition` panel with the redesigned `SkillCompositionKit`: a dark-first, dense, token/cost-aware Skill Composition panel. The kit is a drop-in replacement that reuses the same server API — only the component tree and wiring file need to change.

---

## Plan Files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | planner | all | entry point — touchpoints + conversation map |
| `USER_STORIES.md` | planner | builder, tester | acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | planner | builder | phase-by-phase build guide (each phase = one board task) |
| `HAPPY_FLOW.md` | planner | builder | ideal user journey |
| `EDGE_CASES.md` | planner | builder, reviewer | edge cases per phase |
| `PLAN_ARCHITECTURE.md` | planner | architect, builder | design decisions + constraints |
| `FLOW_DIAGRAM.md` | planner | builder | ASCII flow of component + wiring relationships |

---

## Codebase Touchpoints

| Source file | Phase | Change |
|---|---|---|
| `pathly/SkillCompositionKit/` (whole folder) | Phase 1 | **source** — copy into studio components dir |
| `studio/src/renderer/src/components/SkillCompositionKit/` | Phase 1 | **CREATE** — kit destination; all 38 files (19 components/hooks + CSS modules) |
| `studio/src/renderer/src/components/SkillCompositionKit/integration.ts` | Phase 1 | Already has correct `../../services/skillComposition` and `../../store/projectStore` paths for this location — verify and keep as-is |
| `studio/src/renderer/src/App.tsx` | Phase 2 | Change import line 19: `./components/SkillComposition/SkillComposition` → `./components/SkillCompositionKit` |
| `studio/src/renderer/src/components/SkillComposition/` (whole folder) | Phase 2 | **DELETE** — replaced by SkillCompositionKit |

---

## Conversation Map

| Phase | Conv # | Scope | Done when |
|---|---|---|---|
| Copy kit folder to studio components | 1 | `studio/src/renderer/src/components/SkillCompositionKit/` | Folder exists at destination with all files; `integration.ts` import paths confirmed correct |
| Swap App.tsx import + remove old folder | 2 | `studio/src/renderer/src/App.tsx` + old `SkillComposition/` | App.tsx points to SkillCompositionKit; old folder deleted |
| TypeScript check + fix | 3 | any failing files | `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0 |

---

## Optional Plan Files

| File | Included? |
|---|---|
| HAPPY_FLOW.md | yes |
| EDGE_CASES.md | yes |
| PLAN_ARCHITECTURE.md | yes |
| FLOW_DIAGRAM.md | yes |
