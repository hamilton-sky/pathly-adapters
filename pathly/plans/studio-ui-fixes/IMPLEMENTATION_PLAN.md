# studio-ui-fixes — Implementation Plan

## Pre-flight

Before Conv 1 starts, run `cd studio && npm run typecheck` and record any pre-existing errors as a known baseline. Do not attribute pre-existing failures to this feature.

---

## Phase 1.1 — Extend FsmEvent type   ← Conversation: 1

**File:** `studio/src/renderer/src/types/index.ts`

**Change:** Make `ts` optional (`ts?: string`); add optional fields `from?: string`, `to?: string`, `reason?: string` to the `FsmEvent` interface.

**Done when:** `FsmEvent` compiles with all 5 fields optional and `npm run typecheck` passes.

**Purpose:** Real EVENTS.jsonl uses `from`/`to`/`reason` — the type must model what actually exists on disk.

**Depends on:** Nothing.

**Enables:** Phases 1.2 and 1.3 can use the extended type without `any` casts.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 1.2 — Fix EVENTS.jsonl parser in Monitor   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/index.tsx`

**Change:**
- Remove `.slice(-50)` from the file-watch EVENTS parser (it can silently drop earlier events)
- Remove the same limit from the initial `readFile` parser
- Both parsers already push all fields via `JSON.parse` — just keep them typed as `FsmEvent`

**Done when:** Monitor loads all events from EVENTS.jsonl without truncating; `npm run typecheck` passes.

**Purpose:** The 50-event cap could hide the initial `FSM_START` and early `STATE_TRANSITION` entries.

**Depends on:** Phase 1.1.

**Enables:** Phase 1.3 has the full event list to display.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 1.3 — Fix EventLog timestamp and detail rendering   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/EventLog.tsx`

**Changes:**
- Update `formatTime(ts?: string): string` — guard for missing/undefined `ts`: return `'—'` instead of crashing; keep the existing `new Date(ts).toTimeString().slice(0, 8)` logic for valid timestamps
- Add helper `eventDetail(ev: FsmEvent): string` that returns `${ev.from} → ${ev.to}` when both present, `ev.reason` when only reason present, `ev.detail ?? ''` as final fallback
- Replace `{ev.detail}` in the render with `{eventDetail(ev)}`

**Done when:** The event log renders all rows without "Invalid" timestamps and shows "STORMING → PLANNING" style text for STATE_TRANSITION events.

**Purpose:** Direct fix for the two visible display bugs.

**Depends on:** Phase 1.1 (extended type).

**Enables:** S1 fully delivered.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 2.1 — Add pipelineStates to project store   ← Conversation: 2

**File:** `studio/src/renderer/src/store/projectStore.ts`

**Change:** Add `pipelineStates: string[]` (default `[]`) to `ProjectState` interface and the initial state object; add `setPipelineStates: (s: string[]) => void` action.

**Done when:** `useStore().pipelineStates` and `useStore().setPipelineStates` are available; `npm run typecheck` passes.

**Purpose:** FsmView needs a stable store slice to read the pipeline order from — not a local hook.

**Depends on:** Nothing.

**Enables:** Phases 2.2 and 2.3.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 2.2 — Load pipeline from flow YAML in Monitor   ← Conversation: 2

**File:** `studio/src/renderer/src/components/Monitor/index.tsx`

**Change:** After `setFsmState(parsed)`, read the flow YAML:
```
readFile(`${projectPath}/src/pathly_data/core/flows/${parsed.flow}.flow.yaml`)
  .then(yaml => {
    const match = yaml.match(/states:\s*\n((?:\s+-\s+\S+\n?)+)/)
    if (match) {
      const states = match[1].trim().split('\n').map(l => l.replace(/^\s+-\s+/, '').trim())
      setPipelineStates(states)
    }
  })
  .catch(() => {/* flow YAML missing — FsmView will use fallback */})
```
Also call `setPipelineStates([])` when `activeTopic` is null/cleared to reset state.

**Done when:** `pipelineStates` in the store is populated with the flow's state list when a topic is selected.

**Purpose:** Pipeline states come from the actual flow definition, not a hardcoded list.

**Depends on:** Phase 2.1.

**Enables:** Phase 2.3.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 2.3 — FsmView uses dynamic pipeline states   ← Conversation: 2

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx`

**Change:** Remove the `const PIPELINE = [...]` constant. Instead:
```ts
const pipelineStates = useStore((s) => s.pipelineStates)
const PIPELINE = pipelineStates.length > 0
  ? pipelineStates
  : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']
```
No other logic changes needed — the rest of the component already uses `PIPELINE` correctly.

**Done when:** Pipeline bar shows correct states for any flow; shows minimal fallback set when no flow loaded; `npm run typecheck` passes.

**Purpose:** Makes the pipeline bar correct for all flows, not just the one it was hardcoded for.

**Depends on:** Phases 2.1, 2.2.

**Enables:** S2 fully delivered.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 3.1 — Add 'debug' and 'explore' to PathlyItemType   ← Conversation: 3

**File:** `studio/src/renderer/src/types/index.ts`

**Change:** Add `'debug' | 'explore'` to `PathlyItemType` union.

**Done when:** Type compiles; `npm run typecheck` passes.

**Purpose:** Sidebar item click routing and editor integration need typed item types.

**Depends on:** Nothing. Do NOT touch Monitor files yet.

**Enables:** Phases 3.2 and 3.3.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 3.2 — useProjectFiles loads debugs and explorations   ← Conversation: 3

**File:** `studio/src/renderer/src/hooks/useProjectFiles.ts`

**Change:**
- Add to the `SECTIONS` constant:
  ```ts
  { label: 'Debugs',       type: 'debug'    as const, dir: 'pathly/debugs'       },
  { label: 'Explorations', type: 'explore'  as const, dir: 'pathly/explorations' },
  ```
- Add to `INITIAL_SECTIONS`: `Debugs: { items: [], open: false }`, `Explorations: { items: [], open: false }`
- In `loadItems`, treat `'debug'` and `'explore'` the same as `'template'` (use `listDirs` to get subfolders, then `listDir` per subfolder for files). Keep `type` on each item as `'debug'` or `'explore'` accordingly.

**Done when:** `sections.Debugs` and `sections.Explorations` are populated with subdir structure; `npm run typecheck` passes.

**Purpose:** Drives the sidebar sections with live data from the filesystem.

**Depends on:** Phase 3.1.

**Enables:** Phase 3.3.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 3.3 — Sidebar renders DEBUGS and EXPLORATIONS   ← Conversation: 3

**File:** `studio/src/renderer/src/components/Sidebar.tsx`

**Changes:**
- Add to `SECTIONS`:
  ```ts
  { label: 'Debugs',       type: 'debug'    as const, dir: 'pathly/debugs'       },
  { label: 'Explorations', type: 'explore'  as const, dir: 'pathly/explorations' },
  ```
- In the `SECTIONS.map` render loop, add `section.type === 'debug' || section.type === 'explore'` to the branch that handles `section.type === 'template'` (subdir rendering). No other changes needed — the subdir UI path already handles the rendering correctly.
- In `handleItemClick`, the existing `item.type === 'flow' ? 'flow' : 'editor'` fallback already routes debug/explore items to the editor — no changes needed there.

**Done when:** DEBUGS and EXPLORATIONS sections appear in the sidebar and expand to show files; clicking opens the editor; `npm run typecheck` passes.

**Purpose:** Makes debug/explore artifacts first-class in the UI.

**Depends on:** Phase 3.2.

**Enables:** S4 delivered.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 3.4 — Fix usePlanConversations parser   ← Conversation: 3

**File:** `studio/src/renderer/src/hooks/usePlanConversations.ts`

**Change:** Replace the current table-agnostic parser with one that:
1. Finds the `## Conversation Breakdown` heading
2. Parses only the table immediately following it
3. Stops at the next `##` heading
4. Reads columns as: `[0]=Conv number, [1]=Phases (title), [2]=Stories, [3]=Status` — NOT the last column (Verify)

The title shown in the sidebar should be the Phases value (e.g., `1–2`), not the Verify command.

**Done when:** Sidebar PLAN section shows `Conv 1 — 1–2 TODO` and `Conv 2 — 3–4 TODO`, not grep commands or Phase Detail rows; `npm run typecheck` passes.

**Purpose:** Eliminates the parser over-matching that produces duplicate rows and command-text statuses.

**Depends on:** Nothing (independent of 3.1–3.3). Do NOT modify PlanBoard yet.

**Enables:** Phase 3.5.

**Verify:** `cd studio && npm run typecheck` → zero errors.

---

## Phase 3.5 — Fix PlanBoard parser and event display   ← Conversation: 3

**File:** `studio/src/renderer/src/components/PlanBoard.tsx`

**Changes:**
- Apply the same `parseProgressMd` fix from Phase 3.4 (replace the local copy of the function)
- Replace per-conversation event filtering (`events.filter(e => e.conversation === conv.num)`) with a flat "Recent events" section at the bottom of the board, showing all events from EVENTS.jsonl — real events have no `conversation` field so per-conv filtering always returns 0
- Keep conversation cards (they still show status from PROGRESS.md correctly)

**Done when:** Plan board shows clean conversation titles and a flat event list; `npm run typecheck` passes.

**Purpose:** Eliminates empty "0 events" cards and dead code filtering.

**Depends on:** Phase 3.4.

**Enables:** S3 fully delivered.

**Verify:** `cd studio && npm run typecheck` → zero errors.
