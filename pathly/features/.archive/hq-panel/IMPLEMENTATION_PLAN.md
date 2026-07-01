---
name: Implementation Plan
---
# HQ Panel — Implementation Plan

## Overview

Rename the Studio `ChatPanel` to **HQ** and upgrade it into a pipeline command center. The two-conversation plan delivers: (1) the structural shell — rename, `runnerStore`, `FlowControlBar` with inline confirm/reroute sub-components, and a `StageStatusStrip`; (2) the behavioral layer — SSE client wired to `runnerStore`, `PathlyMenuCard` decision mode, and live cost/session display. The Python backend (`multi-adapter-runner`) must be reachable before this plan starts.

## Layer Architecture

```
DESIGN.md (UI spec)          →  React components (HQ/)       →  HTTP / SSE contracts
       ↓                               ↓                               ↓
FEATURE_INDEX.md             runnerStore (Zustand)         /runner/* + /events/runner
(dependency map)             useHQ.ts (SSE lifecycle)       adapters.gen.ts (color chips)
```

---

## Architectural Rules (apply in every phase)

- **NO inline styles.** All styling via CSS Modules (`*.module.css`). Color values use `tokens.css` custom properties only (e.g. `var(--accent)`, `var(--green)`, `var(--yellow)`, `var(--surface-2)`).
- **One component per folder** with a paired `*.module.css`. Target ~150 lines per `.tsx` file. Extract sub-components when approaching the limit.
- **Every `<button>` must carry `type="button"`** (or `type="submit"` when inside a `<form>`).
- **ARIA on all interactive elements:** `aria-label` on icon-only buttons; `aria-live="polite"` on streaming content; `aria-disabled` mirrors the `disabled` prop; `aria-hidden="true"` on decorative chips.
- **Disabled state:** `opacity: 0.45` + `cursor: not-allowed` — never the same visual as enabled.

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** `pathly/plans/hq-panel/PROGRESS.md` — mark phase complete once pre-flight passes  
**Done when:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` exits 0 (baseline recorded); `GET http://127.0.0.1:8765/runner/start` returns any HTTP response (confirms the backend dependency is reachable — a 405 Method Not Allowed counts).  
**Delivers stories:** prerequisite for S1  
**Depends on:** `multi-adapter-runner` feature shipped and server running  
**Enables:** Phase 1 (safe to begin edits)  
**Details:**
- Run typecheck. Record any pre-existing errors as baseline — do NOT fix them now.
- Confirm the runner endpoint exists: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/runner/start`. Any response other than connection-refused counts as reachable.
- Confirm `adapters.gen.ts` exists (path TBD by glob — likely `studio/src/renderer/src/generated/adapters.gen.ts` or similar). If absent, write `OPEN: adapters.gen.ts not found` in `pathly/plans/hq-panel/feedback/HUMAN_QUESTIONS.md` and halt.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` (record baseline)

---

### Phase 1: Rename ChatPanel → HQ + update imports   ← Conversation: 1
**File:** `studio/src/renderer/src/components/ChatPanel/` → `HQ/` — RENAME folder and all files within  
**Done when:** No file under `studio/src/renderer/src/components/` is named `ChatPanel*`; all import sites reference `HQ`; typecheck exits 0.  
**Delivers stories:** S1 (rename AC)  
**Depends on:** Phase 0  
**Enables:** Phase 2 (new sub-components added to the renamed folder)  
**Details:**
- Rename the folder from `ChatPanel/` to `HQ/`.
- Rename `index.tsx` component export from `ChatPanel` to `HQ`.
- Rename `useChatPanel.tsx` → `useHQ.ts`; rename the hook function to `useHQ`.
- Rename `ChatHeader.tsx` in-place (same filename, stays in `HQ/`). Add the subtitle/tooltip element specified in `DESIGN.md` — a `<span>` with `className={styles.subtitle}` or a `title` attribute, non-empty, visible in the DOM.
- Move `PathlyMenuCard.tsx`, `MatchCard.tsx`, and all `*.module.css` files to `HQ/` — no behavior changes yet.
- Grep for all import sites of `ChatPanel` across `studio/src/renderer/src/` and update them to `HQ`.
- Check `studio/src/renderer/src/App.tsx` (or wherever the tab label is defined) and update the tab label string to `"HQ"`.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 2: runnerStore   ← Conversation: 1
**File:** `studio/src/renderer/src/store/runnerStore.ts` — CREATE  
**Done when:** `runnerStore` is importable; `store/index.ts` exports it; typecheck exits 0.  
**Delivers stories:** S1 (runnerStore AC)  
**Depends on:** Phase 1  
**Enables:** Phase 3 (FlowControlBar reads store)  
**Details:**
- Create `studio/src/renderer/src/store/runnerStore.ts` using Zustand `create`.
- State shape:
  ```ts
  type RunnerStatus = 'idle' | 'running' | 'paused' | 'blocked' | 'error'
  type SessionKind  = 'opened' | 'continued' | 'degraded' | null

  interface RunnerState {
    status:       RunnerStatus
    stage:        string | null
    adapter:      string | null   // 'claude' | 'codex' | 'copilot' | null
    cost:         number          // cumulative USD, 0 by default
    sessionKind:  SessionKind
    decisionMenu: DecisionMenuItem[] | null
    errorMessage: string | null
  }
  ```
- Actions: `setRunnerState(partial: Partial<RunnerState>)`, `resetRunner()` (back to defaults), `setDecisionMenu(items: DecisionMenuItem[] | null)`.
- Define `DecisionMenuItem` as `{ id: string; label: string }`.
- Add `runnerStore` to the root merge in `studio/src/renderer/src/store/index.ts`.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 3: FlowControlBar + StageStatusStrip   ← Conversation: 1
**File:** `studio/src/renderer/src/components/HQ/FlowControlBar/FlowControlBar.tsx` — CREATE (and paired `.module.css`)  
**File:** `studio/src/renderer/src/components/HQ/FlowControlBar/AbortConfirmStrip.tsx` — CREATE  
**File:** `studio/src/renderer/src/components/HQ/FlowControlBar/ReroutePopover.tsx` — CREATE  
**File:** `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` — CREATE (and paired `.module.css`)  
**Done when:** `FlowControlBar` and `StageStatusStrip` are rendered inside `HQ/index.tsx`; clicking Start sends the correct POST; typecheck exits 0.  
**Delivers stories:** S1 (all remaining ACs)  
**Depends on:** Phase 2  
**Enables:** Conversation 2 (SSE wires live data into these components)  
**Details:**

**FlowControlBar:**
- Reads `status` from `runnerStore`.
- Renders: Start, Pause, Resume, Advance, Reroute, Retry, Abort — each `type="button"`, each with `aria-label`.
- Disabled logic: see S1 AC. Use `disabled` attribute + CSS class that applies `opacity: 0.45; cursor: not-allowed`.
- On click, each button POSTs to the matching endpoint at `http://127.0.0.1:8765/runner/<action>`. On non-2xx, call `runnerStore.setRunnerState({ errorMessage: <text> })`.
- Abort button reveals `AbortConfirmStrip` (conditionally rendered below the bar). Does NOT POST immediately.
- Reroute button opens `ReroutePopover` (positioned below or adjacent per DESIGN.md).
- Keep under ~150 lines; extract sub-components as needed.

**AbortConfirmStrip:**
- Inline strip (not a modal) with two buttons: "Confirm abort" (`type="button"`) and "Cancel" (`type="button"`).
- "Confirm abort" POSTs to `/runner/abort` then hides the strip.
- "Cancel" hides the strip with no network call.
- `aria-label` on both buttons; strip has `role="alert"` so it is announced on appearance.

**ReroutePopover:**
- A `<div>` with `role="dialog"` and `aria-label="Reroute to adapter"`.
- Contains a `<select>` with options: `claude`, `codex`, `copilot`. Each option label matches its adapter name. Default selection: current `runnerStore.adapter`.
- Two buttons: "Reroute" (`type="button"`, POSTs `{ adapter }` to `/runner/reroute`) and "Cancel" (`type="button"`, closes popover).
- Adapter color chips beside each option use `aria-hidden="true"`.

**StageStatusStrip:**
- Reads `status`, `stage`, `adapter`, `cost`, `sessionKind`, `errorMessage` from `runnerStore`.
- Status dot: pulsing CSS animation (`@keyframes pulse`) when `status === 'running'`; static otherwise.
- Adapter chip: colored `<span aria-hidden="true">` — `var(--accent)` for claude, `var(--green)` for codex, `var(--yellow)` for copilot; hidden when `adapter` is null.
- Cost: formatted as `$${cost.toFixed(3)}`; shows `—` when cost is 0 and `status === 'idle'`.
- Session indicator: "New session" / "Continued" / "Degraded" label; absent when `sessionKind` is null.
- Error display: when `errorMessage` is non-null, renders a visible error line with `role="alert"`.
- Neutral placeholder when store is in initial state — no crash.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 4: SSE client in useHQ.ts   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/useHQ.ts` — MODIFY  
**Done when:** `EventSource` to `/events/runner` is opened on mount, closed on unmount; all six event types update `runnerStore`; typecheck exits 0.  
**Delivers stories:** S2 (SSE client AC)  
**Depends on:** Phase 3 (runnerStore exists)  
**Enables:** Phase 5 (PathlyMenuCard can read decisionMenu from store)  
**Details:**
- Mirror the existing `/events/menu` `EventSource` pattern in `pathlyContext.ts` (read that file first to match conventions).
- Open `new EventSource('http://127.0.0.1:8765/events/runner')` inside a `useEffect` with `[]` deps. Store the ref to call `.close()` on cleanup.
- Handle events (all payloads are JSON-parsed from `event.data`):
  - `STAGE_CHANGE`: `setRunnerState({ stage, adapter, status: 'running' })`
  - `DECISION_MENU`: `setRunnerState({ decisionMenu: items, status: 'blocked' })`
  - `RUNNER_STATUS`: `setRunnerState({ status })`
  - `COST_UPDATE`: `setRunnerState({ cost })` — throttle to max 1 update per 200 ms (use a `useRef` timestamp check)
  - `SESSION`: `setRunnerState({ sessionKind })`
  - `RUNNER_ERROR`: `setRunnerState({ errorMessage, status: 'error' })`
- `onerror`: call `setRunnerState({ errorMessage: 'Reconnecting…' })`; schedule a `setTimeout` (3 s) that creates a new `EventSource` (replace the ref). Cancel the timeout on cleanup to avoid memory leaks.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 5: PathlyMenuCard decision mode   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/PathlyMenuCard.tsx` — MODIFY  
**Done when:** When `runnerStore.decisionMenu` is non-null, clicking a menu item POSTs to `/runner/decision` and clears the menu; when null, original behavior is unchanged; typecheck exits 0.  
**Delivers stories:** S2 (decision menu ACs)  
**Depends on:** Phase 4  
**Enables:** Phase 6 (cost/session live wiring)  
**Details:**
- Add an optional `decisionMode?: boolean` and `decisionItems?: DecisionMenuItem[]` prop — OR read directly from `runnerStore` (prefer store read to avoid prop drilling).
- When `decisionMenu` in `runnerStore` is non-null: render decision items instead of FSM menu. Each item is a `<button type="button">` with `aria-label`. Reveal items token-by-token per DESIGN.md's typewriter-reveal rule — use a `useEffect` that appends one character per 20 ms interval to a local display string, bounded by `aria-live="polite"` on the container.
- On item click: set the clicked item's button `disabled` immediately (prevents double-click); POST `{ choice: item.id }` to `/runner/decision`; on success clear `decisionMenu` in store; on non-2xx revert `disabled` and call `setRunnerState({ errorMessage })`.
- When `decisionMenu` is null: existing `writeToTerminal` click behavior is untouched.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

### Phase 6: Live cost + session in StageStatusStrip   ← Conversation: 2
**File:** `studio/src/renderer/src/components/HQ/StageStatusStrip/StageStatusStrip.tsx` — MODIFY  
**Done when:** Cost updates live from SSE events; session indicator text matches `sessionKind`; typecheck exits 0; manual test passes (launch Studio, Start a run, verify cost ticks and stage label changes).  
**Delivers stories:** S2 (cost + session ACs)  
**Depends on:** Phase 5  
**Enables:** Feature complete — all acceptance criteria satisfied  
**Details:**
- `StageStatusStrip` already reads `runnerStore` from Phase 3; ensure it re-renders on `cost` and `sessionKind` changes (Zustand selector — select the two fields individually to avoid over-rendering).
- Cost throttle: Phase 4 handles throttle at the store-write level; no additional throttle needed here.
- Session label map: `opened` → "New session"; `continued` → "Continued"; `degraded` → "Degraded"; `null` → render nothing.
- "Degraded" label uses `var(--yellow)` text color via a CSS Module class.
**Verify:** `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`

---

## Prerequisites

- `multi-adapter-runner` backend feature is merged and `http://127.0.0.1:8765` is running before Phase 0.
- `adapters.gen.ts` file generated by the backend and present in the Studio source tree.
- Studio builds without errors before this plan begins (Phase 0 baseline typecheck).

## Key Decisions

- **Zustand `runnerStore` as single source of truth:** All runner state (status, stage, adapter, cost, decision menu) lives in one store. This avoids props drilling through the HQ component tree and keeps SSE wiring isolated to `useHQ.ts`.
- **SSE in `useHQ.ts`, not a Context:** The existing `/events/menu` pattern uses a context (`pathlyContext.ts`). Runner SSE is scoped to the HQ panel lifetime; a hook inside the panel is simpler than a top-level context for something that only HQ consumes.
- **PathlyMenuCard reads store, not props:** Avoids a breaking prop-API change. The component already lives inside HQ; store access is safe.
- **3 s flat retry for SSE:** Exponential back-off deferred. Simple flat retry is sufficient for the runner's expected use case (local server, short run durations).
- **Cost throttle at store write (Phase 4), not at render (Phase 6):** Centralizing the throttle means any future consumer of `runnerStore.cost` benefits automatically.
