# studio-arch-refactor — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature is

Four targeted refactors to Pathly Studio — no user-visible behaviour changes, no Python changes:

1. **Service layer** — wrap all `window.pathly.*` calls in `pathlyApi.ts` so components never call the preload bridge directly
2. **Custom hooks** — extract file-loading and plan-loading out of `Sidebar.tsx` into `useProjectFiles()` / `usePlanConversations()`
3. **Store decomposition** — split single Zustand store into `uiStore` + `projectStore` slices; keep `useStore()` barrel
4. **Discriminated frontmatter types** — move `FrontmatterValues` from `ConfigForm.tsx` to `types/index.ts` as a proper discriminated union

**Prerequisite:** `pathly-studio` feature (Convs 1–4) must be DONE before starting.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | no | — |
| `EDGE_CASES.md` | no | — |
| `HAPPY_FLOW.md` | no | — |
| `FLOW_DIAGRAM.md` | no | — |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/src/renderer/src/services/pathlyApi.ts` | Conv 1 | CREATE — typed wrappers for all `window.pathly.*` calls |
| `studio/src/renderer/src/hooks/useProjectFiles.ts` | Conv 1 | CREATE — file-loading logic extracted from Sidebar |
| `studio/src/renderer/src/hooks/usePlanConversations.ts` | Conv 1 | CREATE — plan-parsing logic extracted from Sidebar |
| `studio/src/renderer/src/components/Sidebar.tsx` | Conv 1 | MODIFY — use hooks, remove async data-loading |
| `studio/src/renderer/src/components/Monitor/index.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/Editor/index.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/TopBar.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/HomeScreen.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/FlowEditor/index.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/FlowWizard.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/PlanBoard.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/components/NewItemDialog.tsx` | Conv 1 | MODIFY — use pathlyApi instead of window.pathly.* |
| `studio/src/renderer/src/store/uiStore.ts` | Conv 2 | CREATE — sidebarCollapsed, activePanel, dirtyItems |
| `studio/src/renderer/src/store/projectStore.ts` | Conv 2 | CREATE — projectPath, projects, activeTopic, fsmState, events, etc. |
| `studio/src/renderer/src/store/index.ts` | Conv 2 | MODIFY — re-export barrel: useStore() merges both slices |
| `studio/src/renderer/src/types/index.ts` | Conv 2 | MODIFY — add SkillFrontmatter, AgentFrontmatter, TemplateFrontmatter union |
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | Conv 2 | MODIFY — remove inline FrontmatterValues, use discriminated union from types |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Service layer + hooks | S1, S2 | TODO | `pathlyApi.ts`, `useProjectFiles.ts`, `usePlanConversations.ts`, `Sidebar.tsx`, 8 callers |
| 2 | Store split + types | S3, S4 | TODO | `uiStore.ts`, `projectStore.ts`, `store/index.ts`, `types/index.ts`, `ConfigForm.tsx` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/studio-arch-refactor/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
