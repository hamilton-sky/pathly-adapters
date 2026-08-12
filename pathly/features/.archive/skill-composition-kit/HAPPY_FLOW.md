# Happy Flow — skill-composition-kit

## Phase 1

1. Builder copies `pathly/SkillCompositionKit/` to `studio/src/renderer/src/components/SkillCompositionKit/`
2. Builder opens `integration.ts` at its new location and confirms `../../services/skillComposition` and `../../store/projectStore` resolve correctly (no changes needed)
3. All 38 kit files are present at the destination

## Phase 2

1. Builder opens `App.tsx` and changes the import on line 19 to `./components/SkillCompositionKit`
2. Builder greps for any external consumers of the old `SkillComposition/` folder — finds none beyond `App.tsx` (which is already updated)
3. Builder deletes `studio/src/renderer/src/components/SkillComposition/`
4. App.tsx has exactly one reference to SkillComposition (the updated import)

## Phase 3

1. Builder runs `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
2. No errors — the kit types align with the services and store
3. Builder confirms: the panel renders when Studio is launched and the FSM server is running
