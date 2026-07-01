# studio-arch-refactor — User Stories

## Context

Pathly Studio has accumulated direct `window.pathly.*` calls scattered across 9 components, a monolithic Zustand store, data-loading logic mixed into `Sidebar.tsx`, and a loose `FrontmatterValues` type defined inline in `ConfigForm.tsx`. This refactor cleans up those four areas without changing any user-visible behaviour or adding new features.

## Stories

### Story S1: Typed service layer
**As a** developer, **I want** all `window.pathly.*` preload calls routed through a single `pathlyApi.ts` module, **so that** components never touch the Electron bridge directly and tests can mock the API without patching globals.

**Acceptance Criteria:**
- [ ] `studio/src/renderer/src/services/pathlyApi.ts` exports one typed function per preload call
- [ ] `grep -r "window\.pathly" studio/src/renderer/src/components/` returns zero matches
- [ ] TypeScript reports zero errors (`npm run typecheck` inside `studio/`)

**Edge Cases:**
- `onPublishOutput` and `onWatchEvent` return unsubscribe functions — wrappers must preserve this
- `shell.openWindow` (HomeScreen) must also be wrapped even if not in the prior plan

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Rendering-only Sidebar
**As a** developer, **I want** Sidebar's file-loading and plan-parsing logic in custom hooks, **so that** the component body contains no `async` declarations and is purely rendering.

**Acceptance Criteria:**
- [ ] `studio/src/renderer/src/hooks/useProjectFiles.ts` exists and exports `useProjectFiles()`
- [ ] `studio/src/renderer/src/hooks/usePlanConversations.ts` exists and exports `usePlanConversations()`
- [ ] `Sidebar.tsx` has no `async function` declarations and no direct `useEffect` data-loading blocks
- [ ] Sidebar still renders flows/skills/agents/templates and plan conversations correctly

**Edge Cases:**
- `loadItems` must remain stable across renders (useCallback) to avoid infinite effect loops
- Hook must read `projectPath` from the store, not from props

**Delivered by:** Phase 2 → Conversation 1

---

### Story S3: Focused store slices
**As a** developer, **I want** the single Zustand store split into `uiStore` and `projectStore`, **so that** UI state and project state are independently readable and writable.

**Acceptance Criteria:**
- [ ] `studio/src/renderer/src/store/uiStore.ts` exists with UI fields (`sidebarCollapsed`, `activePanel`, `dirtyItems`)
- [ ] `studio/src/renderer/src/store/projectStore.ts` exists with project/monitor/publish fields
- [ ] `useStore()` in `store/index.ts` returns a merged object — no import changes in any caller
- [ ] `npm run typecheck` passes; no runtime errors when opening a project

**Edge Cases:**
- `sidebarCollapsed` must be persisted; `projects` must be persisted — other fields are ephemeral
- `useStore()` barrel must stay backwards-compatible so no component imports change

**Delivered by:** Phase 3 → Conversation 2

---

### Story S4: Discriminated frontmatter union
**As a** developer, **I want** `FrontmatterValues` to be a discriminated union of per-type interfaces, **so that** TypeScript enforces which fields are valid for each item type.

**Acceptance Criteria:**
- [ ] `types/index.ts` exports `SkillFrontmatter`, `AgentFrontmatter`, `TemplateFrontmatter`, and `FrontmatterValues = SkillFrontmatter | AgentFrontmatter | TemplateFrontmatter`
- [ ] No index signature (`[key: string]: unknown`) remains on any frontmatter type
- [ ] `ConfigForm.tsx` imports `FrontmatterValues` from `types/index.ts` and uses type narrowing (`values.type === 'skill'`) before accessing type-specific fields
- [ ] Opening a skill shows adapter checkboxes; opening a template hides them

**Edge Cases:**
- YAML parsing may produce unknown keys — caller must strip unknowns before passing to typed interface
- Existing callers that read `values[key]` by dynamic key must be updated to use narrowed access

**Delivered by:** Phase 4 → Conversation 2
