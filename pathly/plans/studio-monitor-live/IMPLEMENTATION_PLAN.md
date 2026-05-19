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
**File:** `studio/src/renderer/src/theme.ts` — MODIFY: add `runtime` and `fontFamilyMono` tokens to `Theme` interface and both theme objects. Do this first — all other phases depend on these tokens.

**Done when:** `theme.ts` has `runtime` and `fontFamilyMono`. Pipeline section shows dots connected by a line; active dot slides (CSS `transition: transform ${t.transitionBase}`); `COMPLETED_GREEN` constant used (not `t.green`); `prefers-reduced-motion` disables all animations; `cycle N` / `conv N` label correct per flow type.

**Delivers stories:** S1

**Depends on:** Existing FsmView + pipelineStates from store.

**Enables:** Phase 2 (trace below), Phase 3 (badge uses same `t.runtime`), Conv 2 (all phases use new tokens).

**Details:**

> See **DESIGN.md §1–§3** for exact CSS values, color constants, and animation spec.

Token additions to `theme.ts`:
```ts
// Theme interface — add both:
runtime: string        // live/active signal color
fontFamilyMono: string // log/trace monospace font

// darkTheme:  runtime: '#22D3EE',  fontFamilyMono: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace"
// lightTheme: runtime: '#0EA5E9',  fontFamilyMono: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace"
```

Color constant at module scope in `FsmView.tsx` (do NOT use `t.green`):
```ts
const COMPLETED_GREEN = 'rgba(22, 163, 74, 0.7)'
// Intentionally not t.green (#4ade80 lime) — spec requires muted forest green
```

Rail visual:
- Rail line: `backgroundColor: t.bgSurface1` (#343452) — NOT `bgSurface0` (too faint at #252538)
- Completed dot: `COMPLETED_GREEN` fill
- Active dot: `t.runtime` fill + `pathly-pulse` class
- Future dot: `t.textMuted` stroke (#5a5d8a), transparent fill — NOT `bgSurface0` (nearly invisible)
- Sliding marker: `transform: translateX` driven by `useLayoutEffect` + `ResizeObserver` for rail width
- Transition: `t.transitionBase` (`'150ms ease-out'`) — reuse token, do NOT hardcode

`prefers-reduced-motion` — add to PULSE_CSS injection block (REQUIRED):
```css
@media (prefers-reduced-motion: reduce) {
  .pathly-pulse { animation: none; }
  .pathly-pulse-border { animation: none; }
}
/* Plus check window.matchMedia at runtime for the inline transition property */
```

Remove existing "System active — STATE" status line entirely.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 2: Add execution trace below the rail   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: add execution trace section below the rail.
**File:** `studio/src/renderer/src/components/Monitor/utils.ts` — CREATE: `formatRelativeTime(ts: string): string` helper.

**Done when:** Trace shows each STATE_TRANSITION as a row; BUILDING visited twice shows two rows; active row has pulsing `●`; failed rows show `✗`; trace container has `aria-live="polite"`; `formatRelativeTime` works correctly.

**Delivers stories:** S2

**Depends on:** Phase 1 (requires `t.fontFamilyMono` and `COMPLETED_GREEN` constant).

**Details:**

> See **DESIGN.md §4** for row color map and typography spec.

Trace container (accessibility required):
```tsx
<div role="log" aria-label="Execution trace" aria-live="polite" aria-atomic={false}>
```

Typography: `fontFamily: t.fontFamilyMono`, `fontSize: '12px'`, `lineHeight: '1.7'`, `whiteSpace: 'pre'`

Failure detection: `PIPELINE.indexOf(nextTo) < PIPELINE.indexOf(thisTo)` → failed. Never hardcode state names.

Sort `VisitRow[]` by `ts` before rendering (EC-1.1 guard — EVENTS.jsonl/SSE race; do NOT fix the race, just sort).

Row layout (12px monospace):
```
  ✓  PLANNING    conv 1    planner    2h ago
  ●  BUILDING    conv 2    builder    now
```

Empty state: `"Waiting for flow activity."` in `t.textMuted`, 13px, centered.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 3: SSE live source badge in Monitor header   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: surface `monitorSource` in `HeaderBar`; handle all states including `null`.

**Done when:** Header shows `● live` (sse), `○ polling` (chokidar), or `—` (null/unavailable). No old `Source: SSE live` text remains.

**Delivers stories:** S3

**Depends on:** `monitorSource` in projectStore (type: `'mcp' | 'chokidar' | 'sse' | null`). `t.runtime` from Phase 1.

**Details:**

In `HeaderBar`, read `monitorSource` via `useStore()`. Render flush-right:
```tsx
const badgeText = monitorSource === 'sse' ? '● live'
  : monitorSource === 'chokidar' ? '○ polling' : '—'
const badgeColor = monitorSource === 'sse' ? t.runtime : t.textMuted
```

Font size: `t.fontSizeSm` (12px) — NOT 11px (below readable floor for dark backgrounds).
Remove any existing `Source:` text from the header. Use `t.runtime` from Phase 1 (`theme.ts`).

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

**Tab bar** — show when `Object.keys(activeFlowSessions).length >= 2` (see DESIGN.md §6 for all CSS values):
```tsx
{sessions.length >= 2 && (
  <div role="tablist" aria-label="Active flows" style={{ height: 32, ...tabBarStyle }}>
    {visibleSessions.map(s => (
      <button
        key={s.topic}
        role="tab"
        aria-selected={activeMonitorTab === s.topic}
        tabIndex={activeMonitorTab === s.topic ? 0 : -1}
        onClick={() => setActiveMonitorTab(s.topic)}
        onKeyDown={handleTabKeyDown}  // Arrow keys navigate; Enter/Space select
      >
        {s.flowKey}
        {s.isRunning && <span className="pathly-pulse" aria-hidden="true" style={{ color: t.runtime, fontSize: '8px' }}>●</span>}
        {/* ◐ paused indicator: DEFERRED POST-MVP — isPaused is always false */}
      </button>
    ))}
    {overflow.length > 0 && <OverflowMenu sessions={overflow} />}
  </div>
)}
```
Cap visible tabs at 4; extras in `...` overflow dropdown.
Active tab: `borderBottom: 2px solid t.runtime`, `color: t.textPrimary`, `backgroundColor: t.bgSurface0`.
Inactive tab: `color: t.textMuted`, `borderBottom: 2px solid transparent`.
Apply `t.focusRing` on `:focus-visible`.
**DO NOT render `◐`** — `isPaused` is always `false`; the branch is deferred to Post-MVP.

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

> See **DESIGN.md §7** for exact position, spacing, and accessibility markup.

Banner position (exact values):
```
position: absolute, top: 12px, left: 50%, transform: translateX(-50%)
maxWidth: 520px, width: calc(100% - 48px), borderRadius: 6px, padding: 10px 14px
backgroundColor: t.bgSurface1, border: 1px solid t.runtime
```

Accessibility (required):
```tsx
<div role="status" aria-live="assertive" aria-label={`${flowName} is running in ${fsmState.current}`}>
  <button onClick={() => setActivePanel('monitor')} aria-label="View running flow in Monitor panel">
    View in Monitor →
  </button>
  <button onClick={() => setDismissed(true)} aria-label="Dismiss banner">✕</button>
</div>
```

Hover-to-pause auto-dismiss (required — EC-3.1): `onMouseEnter` clears the 8s timer; `onMouseLeave` restarts it.

Dismissed state resets:
- When `activeTopic` changes
- When `isRunning` transitions `false → true` (EC-3.2 — track with `prevRunningRef`)

**Verify:** `cd studio; npm run typecheck`

---

### Phase 6: Plan conversation card enhancements   ← Conversation: 2

**File:** `studio/src/renderer/src/components/PlanBoard.tsx` — MODIFY: active status colors, pulsing border, card interactivity, cost row, hover/selected states, timestamps, phase range.
**File:** `studio/src/renderer/src/types/index.ts` — MODIFY: extend `ConvRow` with `phases?: string`.
**File:** `studio/src/renderer/src/hooks/usePlanConversations.ts` — MODIFY: parse phase range from PROGRESS.md and populate `ConvRow.phases`.

**Done when:** Active card pulses cyan (color only, width stays 3px); `t.blue` replaced with `t.runtime` for active status; failed shows `t.red` + `✗`; cards are focusable `role="button"`; hover shows `bgSurface1`; selected shows violet border; cost row appears when data exists; all animations respect `prefers-reduced-motion`.

**Delivers stories:** S6

**Details:**

> See **DESIGN.md §8** for all card layout values, color constants, and interaction patterns.

**FIRST — replace `t.blue` with `t.runtime` for active status** (EC: designers flagged this as critical):
In `statusBorderColor` and `statusBgColor`: active statuses (IN_PROGRESS/REVIEWING/BUILDING) → `t.runtime`. Leave `t.blue` ONLY in EventLog `eventType` labels.

**Pulsing border — color only, width always 3px** (EC-3.4):
```css
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: #22D3EE; }
  50% { border-left-color: rgba(34,211,238,0.15); }
}
.pathly-pulse-border { animation: pathly-pulse-border 1.5s ease-in-out infinite; }
/* 1.5s: status heartbeat — intentional */
@media (prefers-reduced-motion: reduce) { .pathly-pulse-border { animation: none; } }
```
Inject once via `styleInjectedRef`. Card always has `borderLeft: '3px solid <color>'` — width never changes.

**Card interactivity** (required):
```tsx
<div role="button" tabIndex={0} aria-pressed={selectedConv === conv.num}
  onClick={() => setSelectedConv(conv.num)}
  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedConv(conv.num) }}
  style={{ cursor: 'pointer' }}
>
```
Apply `t.focusRing` on `:focus-visible`.

**Hover/selected**: `hoveredConv` + `selectedConv` local state. Hover: `backgroundColor: t.bgSurface1`. Selected: `backgroundColor: t.bgSurface1` + `borderLeft: 3px solid t.accent` (violet replaces status border).

**Cost per conv**: check one real EVENTS.jsonl file first (EC-2.6). Filter by `e.conversation === conv.num`. If field absent, hide cost row entirely.

**Card layout** (52px min-height):
```
  [icon] Conv N · Phase title               [status badge]
         agents · Phase N–M · X ago
         Xk in / Yk out · $Z                (if cost data; fontFamilyMono 12px)
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
