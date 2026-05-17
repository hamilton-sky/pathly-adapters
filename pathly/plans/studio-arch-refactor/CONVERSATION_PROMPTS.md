# studio-arch-refactor — Conversation Guide

Split into 2 conversations. Each leaves the codebase typechecking cleanly.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Service layer + hooks (Phases 1–2)

**Stories delivered:** S1, S2

**Prompt to paste:**
```
Read plans/studio-arch-refactor/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-arch-refactor Conversation 1 (Phases 1–2) from plans/studio-arch-refactor/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path listed in FEATURE_INDEX.md exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- CREATE `studio/src/renderer/src/services/pathlyApi.ts` — typed wrappers for all window.pathly.* calls
- CREATE `studio/src/renderer/src/hooks/useProjectFiles.ts` — file-loading hook
- CREATE `studio/src/renderer/src/hooks/usePlanConversations.ts` — plan-parsing hook
- MODIFY `studio/src/renderer/src/components/Sidebar.tsx` — use hooks, remove async data-loading
- MODIFY `studio/src/renderer/src/components/Monitor/index.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/Editor/index.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/TopBar.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/HomeScreen.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/FlowEditor/index.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/FlowWizard.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/PlanBoard.tsx` — use pathlyApi
- MODIFY `studio/src/renderer/src/components/NewItemDialog.tsx` — use pathlyApi

Scope:
- Phase 1.1: Create services/ directory and pathlyApi.ts with one typed export per window.pathly.* call
- Phase 1.2: Replace all window.pathly.* calls in the 9 component files with the pathlyApi equivalents (one-for-one, no logic changes)
- Phase 2.1: Create useProjectFiles() hook extracting loadItems logic from Sidebar.tsx
- Phase 2.2: Create usePlanConversations() hook extracting loadPlan + parseProgressMd from Sidebar.tsx
- Phase 2.3: Refactor Sidebar.tsx to call the two hooks at the top; remove all async declarations and data-loading useEffects

Architectural rules:
- Phase 1.2 is one-for-one substitution only — do not change any logic
- onPublishOutput and onWatchEvent wrappers must return the unsubscribe function unchanged
- useProjectFiles must wrap loadItems in useCallback to keep it stable
- Sidebar JSX and event handlers must remain identical after Phase 2.3

Do NOT touch store files, types/index.ts, or ConfigForm.tsx — those are Conv 2.

Verify after all phases:
  grep -r "window\.pathly" studio/src/renderer/src/components/   ← must return zero matches
  cd studio && npm run typecheck                                   ← must pass with zero errors

After done, update plans/studio-arch-refactor/PROGRESS.md phases 1.1–2.3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Zero `window.pathly.*` calls remain in components; Sidebar is rendering-only; typecheck passes.
**Files touched:** `services/pathlyApi.ts`, `hooks/useProjectFiles.ts`, `hooks/usePlanConversations.ts`, `Sidebar.tsx`, 8 caller components.

---

## Conversation 2: Store split + types (Phases 3–4)

**Stories delivered:** S3, S4

**Prompt to paste:**
```
Read plans/studio-arch-refactor/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement studio-arch-refactor Conversation 2 (Phases 3–4) from plans/studio-arch-refactor/IMPLEMENTATION_PLAN.md.

Conversation 1 is DONE. The service layer and hooks are in place.

**Before editing anything:** glob/read the live repo to confirm every file path listed in FEATURE_INDEX.md exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- CREATE `studio/src/renderer/src/store/uiStore.ts` — UI state slice
- CREATE `studio/src/renderer/src/store/projectStore.ts` — project/monitor/publish state slice
- MODIFY `studio/src/renderer/src/store/index.ts` — useStore() barrel merging both slices
- MODIFY `studio/src/renderer/src/types/index.ts` — add SkillFrontmatter, AgentFrontmatter, TemplateFrontmatter, FrontmatterValues union
- MODIFY `studio/src/renderer/src/components/Editor/ConfigForm.tsx` — import FrontmatterValues from types, use type narrowing

Scope:
- Phase 3.1: Create uiStore.ts with sidebarCollapsed (persisted), activePanel, dirtyItems and their setters
- Phase 3.2: Create projectStore.ts with projectPath, projects (persisted), activeTopic, selectedItem, fsmState, events, monitorSource, publishing, publishLog and all setters
- Phase 3.3: Update store/index.ts so useStore() returns { ...useUiStore(), ...useProjectStore() } — do NOT change any component imports
- Phase 4.1: Add three discriminated interfaces and FrontmatterValues union to types/index.ts; remove any existing index-signature type
- Phase 4.2: Update ConfigForm.tsx to import FrontmatterValues from types/index.ts; guard adapter section with values.type === 'skill' || values.type === 'agent'; remove inline type definition; zero any casts

Architectural rules:
- useStore() barrel must remain backwards-compatible — no component import paths change
- sidebarCollapsed and projects must use Zustand persist middleware; all other fields are ephemeral
- ConfigForm must not own the FrontmatterValues type after this conversation

Do NOT touch pathlyApi.ts, hooks/, or Sidebar.tsx — those are Conv 1 (already done).

Verify after all phases:
  cd studio && npm run typecheck   ← must pass with zero errors

After done, update plans/studio-arch-refactor/PROGRESS.md phases 3.1–4.2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Store split into two slices; `useStore()` barrel unchanged from callers' perspective; `FrontmatterValues` is a discriminated union; typecheck passes.
**Files touched:** `store/uiStore.ts`, `store/projectStore.ts`, `store/index.ts`, `types/index.ts`, `Editor/ConfigForm.tsx`.
