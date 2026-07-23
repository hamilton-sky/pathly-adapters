# Flow Diagram — skill-composition-kit

## Component Wiring (after swap)

```
App.tsx
  └─ import { SkillComposition } from './components/SkillCompositionKit'
       └─ index.ts  (barrel)
            └─ SkillComposition/SkillComposition.tsx
                 ├─ useProjectPath()          ← integration.ts → store/projectStore
                 ├─ useSkillCompositionCatalog(root)
                 │    └─ fetchSkillComposition  ← integration.ts → services/skillComposition
                 ├─ SkillSidebar/             (skill list + collapse rail)
                 └─ FragmentPanel/
                      ├─ useFragmentToggles   ← saveSkillCompositionOverride / resetSkillComposition
                      ├─ useComposedPreview   ← previewComposedSkill
                      ├─ CompositionSummary/  (token bar)
                      ├─ ConfigView/
                      │    ├─ FragmentTable/  (table layout)
                      │    └─ FragmentSplit/  (split layout)
                      └─ PreviewView/
                           ├─ FragmentListPanel/  (Fragments/Abilities/System tabs)
                           ├─ ComposedPromptView/
                           └─ InspectDrawer/
```

## Build Flow

```
Phase 1: COPY
  pathly/SkillCompositionKit/  ─────────────────────────────►  components/SkillCompositionKit/
  (source, unchanged)                                           (destination, new folder)
         │
         └─ integration.ts paths verified: ../../services/ ✓
                                           ../../store/    ✓

Phase 2: REWIRE
  App.tsx line 19
  BEFORE: ./components/SkillComposition/SkillComposition
  AFTER:  ./components/SkillCompositionKit
         │
         └─ components/SkillComposition/  ───────────────────► [DELETED]

Phase 3: TYPECHECK
  tsc --noEmit -p studio/tsconfig.web.json
  0 errors  ──────────────────────────────────────────────────► DONE
  N errors  ──────────────────────────────────────────────────► fix in SkillCompositionKit/
                                                                 or integration.ts, re-run
```
