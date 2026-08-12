# Edge Cases — skill-composition-kit

## Phase 1

- **Partial copy fails mid-way:** If the copy is interrupted, some kit files land in the destination but not all. Mitigation: delete the partial `components/SkillCompositionKit/` and retry.
- **CSS modules not copied:** Some glob patterns exclude `.module.css`. Verify each component subfolder has its matching `.module.css` file after the copy.
- **Duplicate `hooks/` path:** The old `SkillComposition/hooks/` and the kit's `hooks/` are at different depths — there is no collision risk once the old folder is deleted in Phase 2.

## Phase 2

- **Another file imports from `components/SkillComposition/`:** The grep step in Phase 2 must catch this. If found, update that import before deleting the old folder. The known consumers are: only `App.tsx` (the other references are `Sidebar.tsx` + `BottomNav.tsx` + `IconStrip.tsx` which reference the panel by its string ID `'skill-composition'`, not a TS import).
- **`App.tsx` import typo:** If `./components/SkillCompositionKit` is misspelled (e.g. `SkillCompositionkit`), Phase 3 will surface a TypeScript error. Fix the import.
- **Old `SkillComposition/` folder not deleted:** Leaving it causes no runtime error, but it adds dead code. Phase 2 must delete it.

## Phase 3

- **`ComposedSection` type mismatch:** The kit re-exports `ComposedSection` from `integration.ts`, which re-exports it from `services/skillComposition`. If the type shape differs, TypeScript surfaces the mismatch. Fix by aligning the type in `integration.ts`.
- **`JSX.Element` vs `React.ReactElement`:** Some kit components may return `JSX.Element`; the renderer's TypeScript config may prefer `React.ReactElement`. Add `import React from 'react'` if the global JSX namespace is not available.
- **Strict-mode `undefined` on optional chains:** The kit uses `catalog?.skills ?? {}` which is safe; if the tsconfig has strict null checks enabled, verify all optional usages compile.
- **data/ placeholder files import non-existent types:** The kit's `data/fragmentMeta.ts`, `data/abilities.ts`, and `data/systemPrompt.ts` are stand-ins. They must compile without runtime deps — they contain only static data, so no import errors expected.
