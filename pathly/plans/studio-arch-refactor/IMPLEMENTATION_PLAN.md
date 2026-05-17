# studio-arch-refactor — Implementation Plan

## Overview

Four internal refactors to Pathly Studio's renderer layer. No new UI features, no Python changes. Conv 1 introduces the service layer and custom hooks; Conv 2 splits the store and tightens the type system.

## Prerequisites
- `pathly-studio` feature Convs 1–4 are DONE
- `npm run typecheck` passes with zero errors before starting (record any baseline failures)

---

## Phase 1 — Create pathlyApi.ts service layer   ← Conversation: 1

**File:** `studio/src/renderer/src/services/pathlyApi.ts`
**Done when:** module exports one typed function for every `window.pathly.*` call; `grep -r "window\.pathly" studio/src/renderer/src/components/` returns zero matches; `npm run typecheck` passes.

### 1.1 — Create services/ directory and pathlyApi.ts

Export one function per preload bridge call:

```ts
export const readFile        = (path: string): Promise<string>                         => window.pathly.fs.read(path)
export const writeFile       = (path: string, content: string): Promise<void>          => window.pathly.fs.write(path, content)
export const listDir         = (dir: string): Promise<string[]>                        => window.pathly.fs.list(dir)
export const listDirs        = (dir: string): Promise<string[]>                        => window.pathly.fs.listDirs(dir)
export const pickFolder      = (): Promise<string | null>                              => window.pathly.fs.pickFolder()
export const publish         = (cwd: string): Promise<number | null>                   => window.pathly.shell.publish(cwd)
export const onPublishOutput = (cb: (line: string) => void): (() => void)             => window.pathly.shell.onOutput(cb)
export const openWindow      = (url: string): void                                     => window.pathly.shell.openWindow(url)
export const mcpPing         = (): Promise<boolean>                                    => window.pathly.mcp.ping()
export const watchStart      = (projectPath: string, topic: string): Promise<void>    => window.pathly.watch.start(projectPath, topic)
export const onWatchEvent    = (cb: (data: { path: string; content: string }) => void): (() => void) => window.pathly.watch.onEvent(cb)
```

Add wrappers for any additional calls found by grep. Unsubscribe wrappers (`onPublishOutput`, `onWatchEvent`) must return the cleanup function.

**Purpose:** single seam — every component imports from `pathlyApi`, never from the preload bridge.

### 1.2 — Update all 9 component callers

**Files:** `Sidebar.tsx`, `Monitor/index.tsx`, `Editor/index.tsx`, `TopBar.tsx`, `HomeScreen.tsx`, `FlowEditor/index.tsx`, `FlowWizard.tsx`, `PlanBoard.tsx`, `NewItemDialog.tsx`
**Done when:** `grep -r "window\.pathly" studio/src/renderer/src/components/` returns zero output.

Replace each `window.pathly.fs.read(...)` → `readFile(...)`, etc. Add import from `../../services/pathlyApi` (adjust relative depth per file). Do not change any logic — one-for-one substitution only.

**Purpose:** enforces the abstraction — no component touches the bridge directly.

---

## Phase 2 — Extract Sidebar custom hooks   ← Conversation: 1

### 2.1 — Create useProjectFiles hook

**File:** `studio/src/renderer/src/hooks/useProjectFiles.ts`
**Done when:** hook reads `projectPath` from store, loads all four section types, returns `{ sections, loadItems }`.

```ts
export function useProjectFiles(): {
  sections: Record<string, SectionState>
  loadItems: () => Promise<void>
}
```

Extract the `loadItems` / `useEffect` logic currently in `Sidebar.tsx`. Use `listDir` and `listDirs` from `pathlyApi`. Wrap `loadItems` in `useCallback`.

### 2.2 — Create usePlanConversations hook

**File:** `studio/src/renderer/src/hooks/usePlanConversations.ts`
**Done when:** hook reads `PROGRESS.md` for `activeTopic` and returns `{ planConvs: ConvRow[] }`.

```ts
export function usePlanConversations(): { planConvs: ConvRow[] }
```

Extract `loadPlan` + `parseProgressMd` currently in `Sidebar.tsx`. Use `readFile` from `pathlyApi`. Read `projectPath` and `activeTopic` from the store.

### 2.3 — Refactor Sidebar to rendering-only

**File:** `studio/src/renderer/src/components/Sidebar.tsx`
**Done when:** component body calls `useProjectFiles()` and `usePlanConversations()` at top; zero `async function` declarations; all JSX unchanged.

Remove: `loadItemsRef`, `useEffect` data-loading blocks, `parseProgressMd`, `loadItems`, `loadPlan`.
Keep: all JSX, all event handlers, all existing prop/state wiring.

---

## Phase 3 — Split Zustand store into slices   ← Conversation: 2

### 3.1 — Create uiStore slice

**File:** `studio/src/renderer/src/store/uiStore.ts`
**Done when:** Zustand `create` holds only UI fields; exported as `useUiStore()`.

Fields: `sidebarCollapsed`, `activePanel`, `dirtyItems` + setters. Persist `sidebarCollapsed`.

### 3.2 — Create projectStore slice

**File:** `studio/src/renderer/src/store/projectStore.ts`
**Done when:** Zustand `create` holds project + monitor + publish fields; exported as `useProjectStore()`.

Fields: `projectPath`, `projects`, `activeTopic`, `selectedItem`, `fsmState`, `events`, `monitorSource`, `publishing`, `publishLog` + all setters. Persist `projects`.

### 3.3 — Update store barrel

**File:** `studio/src/renderer/src/store/index.ts`
**Done when:** `useStore()` returns merged object from both slices; no import changes needed in any component.

```ts
import { useUiStore } from './uiStore'
import { useProjectStore } from './projectStore'
export function useStore() {
  return { ...useUiStore(), ...useProjectStore() }
}
```

**Purpose:** backwards-compatible merge — all existing `useStore()` call sites keep working.

---

## Phase 4 — Discriminated frontmatter types   ← Conversation: 2

### 4.1 — Add discriminated interfaces to types/index.ts

**File:** `studio/src/renderer/src/types/index.ts`
**Done when:** three interfaces exported; `FrontmatterValues` is a union; no index signature present.

```ts
export interface SkillFrontmatter    { type: 'skill';    name?: string; description?: string; adapters?: string[]; tools?: string[] }
export interface AgentFrontmatter    { type: 'agent';    name?: string; description?: string; adapters?: string[]; model?: string }
export interface TemplateFrontmatter { type: 'template'; name?: string; category?: string }
export type FrontmatterValues = SkillFrontmatter | AgentFrontmatter | TemplateFrontmatter
```

### 4.2 — Update ConfigForm to use union type

**File:** `studio/src/renderer/src/components/Editor/ConfigForm.tsx`
**Done when:** `Props.values` typed as `FrontmatterValues` from `types/index.ts`; adapter section guarded by `values.type === 'skill' || values.type === 'agent'`; no `any` casts; inline type definition removed.

```tsx
{(values.type === 'skill' || values.type === 'agent') && (
  <AdapterCheckboxes adapters={values.adapters ?? []} ... />
)}
```

**Verify:** `cd studio && npm run typecheck` — zero errors.

## Key Decisions

- **Merged `useStore()` barrel** keeps all 30+ existing call sites working with zero import changes — the right trade-off for a pure refactor.
- **One-for-one pathlyApi wrappers** — no logic changes, just name indirection — keeps this diff reviewable.
- **`FrontmatterValues` moved to `types/index.ts`** — `ConfigForm.tsx` is a UI component and should not own a domain type used across the renderer.
