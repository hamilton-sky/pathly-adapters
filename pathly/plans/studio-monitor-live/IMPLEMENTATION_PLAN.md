# studio-monitor-live — Implementation Plan

## Overview

Upgrades the Pathly Studio Monitor panel from its current working-but-minimal state to the full UX spec resolved in MONITOR_DESIGN_SPEC.md. The changes are renderer-only: three Monitor components (FsmView, Monitor index), PlanBoard, VisualView banner, and minor store additions. No backend or IPC changes beyond store fields. Monitor and canvas are mutually exclusive panels (`activePanel` in uiStore) — the plan works within this constraint.

## Layer Architecture

```
Store (uiStore/projectStore)   →   Monitor components          →   Visual output
activePanel, activeFlowSessions    FsmView (rail + trace)          Connected rail, sliding dot
monitorSource, activeMonitorTab    Monitor/index (tabs, SSE)       Tab bar, live badge
                                   PlanBoard (cards)               Pulsing cards, cost rows
                                   VisualView banner               Running-flow banner
```

## Conversation Map

| Conv | Phases | Focus |
|------|--------|-------|
| 1 | 1, 2, 3 | FSM rail visual upgrade, execution trace, SSE badge |
| 2 | 4, 5, 6, 7 | Monitor tabs + SSE re-key, running banner, plan card enhancements, last-used flow |

## Phases

### Phase 1: Upgrade FsmView to connected rail with CSS dot   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: replace box-list layout with a horizontal connected rail (thin 1px line, state dots, sliding active dot via CSS transform).
**File:** `studio/src/renderer/src/theme.ts` — VERIFY/MODIFY: confirm `runtime` token exists (`#22D3EE`); add it if missing before any other phase uses it.

**Done when:** Pipeline section shows dots connected by a line; active dot slides (CSS `transition: transform 150ms ease-out`); loop-back re-positions correctly; `cycle N` / `conv N` label correct per flow type.

**Delivers stories:** S1

**Depends on:** Existing FsmView + pipelineStates from store.

**Enables:** Phase 2 (trace below), Phase 3 (badge uses same `t.runtime`).

**Details:**

Rail layout:
```
  ●─────────────●────────────◯──────────◯
PLANNING     BUILDING    REVIEWING    DONE
                ↑ cyan dot (active)
```

- Container: `display: flex; align-items: center; position: relative;`
- Rail line: absolutely positioned 1px horizontal line, `bgSurface1` color
- State dot: 10px circle. Completed: green fill. Active: cyan fill + `pathly-pulse` class. Future: muted outline.
- Active dot marker: separate absolutely-positioned cyan circle, moves via `transform: translateX`. Position = `(activeIdx / (PIPELINE.length - 1)) * railWidthPx`. Use `useRef` on the rail container + `ResizeObserver` (or `useLayoutEffect`) to compute rail width. One `requestAnimationFrame` on mount to avoid paint-before-transition.
- State labels: 11px muted text below each dot, uppercase.
- `cycle N` vs `conv N`: if `fsmState.flow === 'debug' || fsmState.flow === 'explore'` → `cycle N`; else `conv N`. For unknown/custom flow names, default to `conv N`. Conv number from `fsmState.conv ?? fsmState.current_conversation`.
- Remove existing "System active — STATE" status line entirely.
- `activeIdx = PIPELINE.indexOf(fsmState.current ?? '')` — single-index lookup. Loop-back is automatic.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 2: Add execution trace below the rail   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: add execution trace section below the rail.
**File:** `studio/src/renderer/src/components/Monitor/utils.ts` — CREATE: `formatRelativeTime(ts: string): string` helper.

**Done when:** Trace shows each STATE_TRANSITION as a row; BUILDING visited twice shows two rows; active row has pulsing `●`; failed rows show `✗`; `formatRelativeTime` works correctly.

**Delivers stories:** S2

**Depends on:** Phase 1.

**Details:**

`formatRelativeTime(ts)`: `now` if <60s ago, `Xm ago` if <60min, `Xh ago` otherwise.

Trace derives from `events` (store), filtering `type === 'STATE_TRANSITION'`. Build `VisitRow[]`:
```ts
interface VisitRow {
  state: string
  visitIndex: number   // nth visit to this state (for de-dupe display)
  ts?: string
  agent?: string
  status: 'done' | 'active' | 'failed'
}
```

**Failure detection — use `pipelineStates` order, not state names:**
After a STATE_TRANSITION event, look at the next STATE_TRANSITION's `to` field. If `PIPELINE.indexOf(nextTo) < PIPELINE.indexOf(thisTo)` — i.e., the pipeline moved backward — mark `thisTo`'s visit as `'failed'`. This works for any flow topology without hardcoding state names.

**Agent per row:** find the first `AGENT_SPAWNED` event with `ts > stateTransition.ts`. If none found, show `—`. Eventual-consistency is acceptable (may lag one frame).

**EVENTS.jsonl / SSE race:** the initial `readFile` load can arrive after SSE has appended live events, overwriting them. This is a pre-existing bug. Do NOT try to fix it in this phase — just ensure the trace doesn't crash on reorder (sort rows by `ts` before rendering).

Row layout (12px monospace):
```
  ✓  PLANNING    conv 1    planner    2h ago
  ●  BUILDING    conv 2    builder    now
```

Empty state: `<span style={{ color: t.textMuted }}>Waiting for flow activity.</span>`

**Verify:** `cd studio; npm run typecheck`

---

### Phase 3: SSE live source badge in Monitor header   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: surface `monitorSource` in `HeaderBar`; handle all states including `null`.

**Done when:** Header shows `● live` (sse), `○ polling` (chokidar), or `—` (null/unavailable). No old `Source: SSE live` text remains.

**Delivers stories:** S3

**Depends on:** `monitorSource` in projectStore (type: `'mcp' | 'chokidar' | 'sse' | null`).

**Details:**

In `HeaderBar`, read `monitorSource` via `useStore()`. Render flush-right:
```tsx
const badgeText = monitorSource === 'sse'
  ? '● live'
  : monitorSource === 'chokidar'
    ? '○ polling'
    : '—'
const badgeColor = monitorSource === 'sse' ? t.runtime : t.textMuted
```

Remove any existing `Source:` text from the header. Size 11px. Use `t.runtime` (confirmed/added in Phase 1).

**Verify:** `cd studio; npm run typecheck`

---

### Phase 4: Multi-flow store + Monitor tabs + SSE re-key   ← Conversation: 2

**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY: add `activeFlowSessions`, `activeMonitorTab`, and setters.
**File:** `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: add tab bar + re-key SSE subscription when active tab changes.

**Done when:** When ≥2 Studio-launched sessions are tracked, a tab bar appears; switching tabs changes the SSE subscription topic; `◐` shown for paused sessions; no tab bar for 0 or 1 session.

**Delivers stories:** S4

**Depends on:** Conversation 1 complete.

**Details:**

Store additions to `uiStore.ts`:
```ts
interface FlowSession {
  flowKey: string          // e.g. "team.flow.yaml"
  topic: string            // e.g. "studio-monitor-live"
  isRunning: boolean
  isPaused: boolean        // waiting for artifact
  isCli: false             // always false until Post-MVP — no CLI discovery yet
}
activeFlowSessions: Record<string, FlowSession>   // key = topic
activeMonitorTab: string | null                    // key into activeFlowSessions
setActiveFlowSessions: (s: Record<string, FlowSession>) => void
setActiveMonitorTab: (tab: string | null) => void
```

**Producer for `activeFlowSessions`** — Studio-session only (CLI discovery is Post-MVP):
In `Monitor/index.tsx`'s existing `useEffect` (keyed on `activeTopic`), after STATE.json is parsed and `fsmState` is set, update `activeFlowSessions` to include the current topic as a session:
```ts
setActiveFlowSessions(prev => ({
  ...prev,
  [activeTopic]: {
    flowKey: `${parsedState.flow ?? 'team'}.flow.yaml`,
    topic: activeTopic,
    isRunning: parsedState.current !== 'IDLE' && parsedState.current !== 'DONE',
    isPaused: false,   // no pause signal yet
    isCli: false
  }
}))
```
Remove session from map when topic changes (cleanup in useEffect return).

**Tab bar** — show when `Object.keys(activeFlowSessions).length >= 2`:
```tsx
{sessions.length >= 2 && (
  <div style={tabBarStyle}>
    {visibleSessions.map(s => (
      <button key={s.topic} onClick={() => setActiveMonitorTab(s.topic)} ...>
        {s.flowKey}
        {s.isRunning && <span style={{ color: t.runtime }}>●</span>}
        {s.isPaused && <span style={{ color: t.textMuted }}>◐</span>}
      </button>
    ))}
    {overflow.length > 0 && <OverflowMenu sessions={overflow} />}
  </div>
)}
```
Cap visible tabs at 4; extras in `...` overflow dropdown.

**SSE re-key** — this is non-trivial. The existing `useEffect` in Monitor/index.tsx (line 117) keys on `[activeTopic, projectPath, ...]`. When `activeMonitorTab` changes, the displayed topic must change too. Refactor: derive `effectiveTopic = activeMonitorTab ?? activeTopic` and use it as the SSE subscription key AND the `params` for `EventSource`. Add `activeMonitorTab` to the `useEffect` dependency array. The cleanup (`es.close()`, `removeListener()`) already runs on dep change, so SSE re-keys automatically.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 5: Running-flow entry banner on canvas   ← Conversation: 2

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` — MODIFY: add dismissible running-flow banner.

**Done when:** Banner appears when one flow is running; "View in Monitor →" calls `setActivePanel('monitor')`; auto-dismisses after 8s; resets on new run; absent when multiple flows active.

**Delivers stories:** S5

**Depends on:** `Z` constants in `FlowEditor/zIndex.ts` (Phase 7b of studio-visual-flow-builder). Confirm file exists before implementing.

**Details:**

`isRunning`: `fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'`
`isMultiFlow`: `Object.keys(activeFlowSessions).length >= 2`

Show banner only when `isRunning && !isMultiFlow`.
When `isMultiFlow && isRunning`: call `setActivePanel('monitor')` automatically on mount (once per session open).

Banner local state:
```ts
const [dismissed, setDismissed] = useState(false)
const prevRunningRef = useRef(false)

// Reset dismissed when a new run starts (IDLE/DONE → running)
useEffect(() => {
  if (isRunning && !prevRunningRef.current) setDismissed(false)
  prevRunningRef.current = !!isRunning
}, [isRunning])

// Reset dismissed when topic changes
useEffect(() => { setDismissed(false) }, [activeTopic])

// Auto-dismiss
useEffect(() => {
  if (!isRunning || dismissed) return
  const id = setTimeout(() => setDismissed(true), 8000)
  return () => clearTimeout(id)
}, [isRunning, dismissed])
```

"View in Monitor →" button calls `setActivePanel('monitor')` from uiStore (NOT a new `bottomPanel` field — use the existing `activePanel` mechanism).

Banner position: absolutely positioned at top of VisualView container. z-index: `Z.toast - 1` from `FlowEditor/zIndex.ts`.

Banner text: `{flowName} is running <span style={{color: t.runtime}}>●</span> {convLabel} / {fsmState.current}`

**Verify:** `cd studio; npm run typecheck`

---

### Phase 6: Plan conversation card enhancements   ← Conversation: 2

**File:** `studio/src/renderer/src/components/PlanBoard.tsx` — MODIFY: pulsing active border, failure indicator, cost/token row, hover/selected states, timestamps, phase range.
**File:** `studio/src/renderer/src/types/index.ts` — MODIFY: extend `ConvRow` with `phases?: string`.
**File:** `studio/src/renderer/src/hooks/usePlanConversations.ts` — MODIFY: parse phase range from PROGRESS.md and populate `ConvRow.phases`.

**Done when:** Active card pulses cyan; failed shows red `✗`; cost row appears when data exists; hover shows `bgSurface1`; selected shows violet border; phase range shows if parsed.

**Delivers stories:** S6

**Details:**

**`ConvRow` extension** (`types/index.ts`):
```ts
interface ConvRow {
  // existing fields ...
  phases?: string   // e.g. "1–3"
}
```

**`parseProgressMd` update** (`usePlanConversations.ts`): parse phase range from the Conv breakdown table (e.g., `| 1 | 1, 2, 3 |` → `phases: "1–3"`). Add to returned `ConvRow`.

**Status determination**:
- Active: `conv.status === 'IN_PROGRESS' || 'BUILDING' || 'REVIEWING'`
- Failed: `conv.status === 'BLOCKED'`
- Done: `conv.status === 'DONE'`

**Cost per conv**: filter `events` (local state in PlanBoard) by `(e as EventEntry & { conversation?: number }).conversation === conv.num`. Sum `cost_usd`, `tokens_in`, `tokens_out` from `AGENT_DONE` entries. Confirm `conversation` field is present in EVENTS.jsonl (check one real file before implementing — if absent, omit cost row entirely rather than showing wrong data).

**Active border pulse**: inject once via the same `styleInjectedRef` pattern as FsmView (avoid double-injection). Keyframes:
```css
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: #22D3EE; }
  50% { border-left-color: transparent; }
}
.pathly-pulse-border { animation: pathly-pulse-border 1.5s ease-in-out infinite; }
```

**Hover/selected**: manage `hoveredConv` and `selectedConv` state. On hover: `backgroundColor: t.bgSurface1`. On selected: `backgroundColor: t.bgSurface1` + violet left border (replace status border).

**Card layout** (52px min-height):
```
  [icon] Conv N · Phase name          [status badge]
         agents · Phase N–M · X ago
         Xk in / Yk out · $Z          (if cost data)
```

**Verify:** `cd studio; npm run typecheck`

---

### Phase 7: Last-used flow on open + auto-open Monitor   ← Conversation: 2

**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY: persist `lastUsedFlowPath` to localStorage (or Electron `store`).
**File:** `studio/src/renderer/src/App.tsx` — MODIFY: on mount, load last-used flow and conditionally switch panel to Monitor.

**Done when:** Studio reopens to the last-used flow; if a flow is already running, Monitor panel opens automatically.

**Delivers stories:** S7

**Depends on:** Phase 4 (activeFlowSessions, fsmState available on mount).

**Details:**

`lastUsedFlowPath` in uiStore: persist to `localStorage` on change. On app mount, read it back and call the appropriate `setSelectedFlow` / open-file action.

On mount in `App.tsx`, after state hydration:
```ts
useEffect(() => {
  if (fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE') {
    setActivePanel('monitor')
  }
}, [])  // run once on mount only
```

Last-used flow: set `lastUsedFlowPath` in uiStore whenever the selected flow file changes (hook into the existing flow-open action). On mount, read from localStorage and dispatch to open it.

**First launch**: `lastUsedFlowPath` is null → canvas shows empty state (existing behavior).
**File deleted**: catch the readFile error and show empty state; clear `lastUsedFlowPath`.

**Verify:** `cd studio; npm run typecheck`

---

## Prerequisites

- `studio-visual-flow-builder` Phase 7b complete (`FlowEditor/zIndex.ts` must exist for Phase 5)
- Confirm `t.runtime` in `theme.ts` before Phase 1 (add if missing)
- Confirm `conversation` field presence in EVENTS.jsonl before Phase 6 cost filtering

## Key Decisions

- Monitor and canvas are mutually exclusive (`activePanel`). "View in Monitor →" calls `setActivePanel('monitor')` — no new `bottomPanel` field.
- Multi-flow tabs key on `effectiveTopic = activeMonitorTab ?? activeTopic` and re-key the SSE subscription.
- `activeFlowSessions` is populated by Monitor's own `useEffect` from Studio-launched sessions only. CLI discovery (pid/lock watcher) is Post-MVP.
- `isCli` defaults to `false` always; the `>_` badge is deferred until Post-MVP.
- Failure detection uses `pipelineStates` order (backward index = failed), never hardcoded state names.
- Tab bar shows only for ≥2 active sessions; single-session path stays clean.
