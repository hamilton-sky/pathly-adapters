# User Stories — skill-composition-kit

## US-1: Swap SkillComposition panel with the redesigned kit

**As a** developer
**I want** the Skill Composition panel replaced with the SkillCompositionKit components
**So that** Studio shows the dark-first, dense, token/cost-aware design with Preview/Config tabs and an Abilities tab

### Acceptance Criteria

- AC-1: `studio/src/renderer/src/components/SkillCompositionKit/` exists with all source files from `pathly/SkillCompositionKit/`
- AC-2: `integration.ts` at its new location correctly resolves `../../services/skillComposition` and `../../store/projectStore`
- AC-3: `App.tsx` imports `SkillComposition` from `./components/SkillCompositionKit` (the barrel `index.ts`)
- AC-4: The old `studio/src/renderer/src/components/SkillComposition/` folder is deleted
- AC-5: `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits with 0 errors

---

## US-2: Panel renders correctly in running app

**As a** user opening the Skill Composition panel
**I want** the new panel to load, show a skill list in the sidebar, and switch to fragment config/preview
**So that** I can manage fragment overrides with the improved UI

### Acceptance Criteria

- AC-6: The panel renders without a runtime error when the FSM server is running
- AC-7: Selecting a skill loads the FragmentPanel (Config + Preview tabs visible)
- AC-8: The panel handles an unreachable server gracefully (shows error message, no crash)
