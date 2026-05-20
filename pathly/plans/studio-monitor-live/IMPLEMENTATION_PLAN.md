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
| 1 | 1, 2, 3, 4 | FSM rail upgrade, execution trace, SSE badge, last-used flow + auto-open |
| 2 | 5, 6, 7, 8 | Running banner, plan card enhancements, blocked/waiting banner, flow-level cost |
| Post-MVP | — | Monitor tabs (S4), stop/cancel control, error detail drill-down, CLI session discovery |

> **Re-split rationale (PO review 2026-05-20):** S7 (last-used flow + auto-open Monitor) moved into Conv 1 — it gates the value of the entire observability core for returning users. Monitor tabs (S4) deferred: no evidence of users running ≥2 concurrent flows in Studio today; the tab machinery is non-trivial and speculative. Stop/cancel and error surfacing are product gaps but intentionally Post-MVP scope.

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

Color constants at module scope in `FsmView.tsx` (do NOT use `t.green` or `t.runtime` for data):
```ts
const COMPLETED_GREEN = '#16A34A'        // solid — rgba version fails WCAG 3:1
const ACTIVE_CYAN     = '#06B6D4'        // data encoding; t.runtime (#22D3EE) is for chrome only
const BLOCKED_AMBER   = '#FBBF24'        // blocked/waiting state
```

Rail visual:
- Rail line: 2px height, split into done-segment (`COMPLETED_GREEN`) + pending-segment (`t.bgSurface1`)
- Completed dot: `COMPLETED_GREEN` solid fill
- Active dot: ring + inner dot via `border + box-shadow` with `ACTIVE_CYAN` — NOT just fill (shape encoding required for WCAG 1.4.1)
- Future dot: `t.textMuted` stroke, transparent fill
- Each dot: `role="img"` + `aria-label="STATE: completed/active/pending"`
- Rail container: `role="progressbar"` + `aria-valuenow` + `aria-valuemin` + `aria-valuemax` + `aria-label`
- Sliding marker: `transform: translateX` driven by `useLayoutEffect` + `ResizeObserver` for rail width
- **First position**: calculate in `useLayoutEffect` directly on mount, before ResizeObserver fires (avoids one-frame flash)
- Transition: `t.transitionBase` (`'150ms ease-out'`) — reuse token, do NOT hardcode

`prefers-reduced-motion` — use opt-in pattern (base = no motion):
```css
/* Base: no animation */
.pathly-pulse       { animation: none; }
.pathly-pulse-border { animation: none; }

/* Add motion only when user has no preference (opt-in) */
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse        { animation: pathly-pulse 600ms ease-in-out 2; }
  .pathly-pulse-border { animation: pathly-pulse-border 600ms ease-in-out 2; }
}
```
For sliding dot transition: check `window.matchMedia('(prefers-reduced-motion: reduce)').matches`; if true, use instant opacity crossfade instead of translateX.

Remove existing "System active — STATE" status line entirely.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 2: Add execution trace below the rail   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: add execution trace section below the rail.
**File:** `studio/src/renderer/src/components/Monitor/utils.ts` — CREATE: `formatRelativeTime(ts: string): string` helper.

**Done when:** Trace shows each STATE_TRANSITION as a row; BUILDING visited twice shows two rows; active row has pulsing `●`; failed rows show `✗`; trace container has `role="log"` + `aria-live="polite"` + `tabIndex={0}`; `formatRelativeTime` works correctly; auto-scroll to latest entry; user scroll-up pauses auto-scroll; `useInterval` 30s refresh for timestamps; `React.memo` on `VisitRow`.

**Delivers stories:** S2

**Depends on:** Phase 1 (requires `t.fontFamilyMono`, `COMPLETED_GREEN`, `ACTIVE_CYAN` constants).

**Details:**

> See **DESIGN.md §4** for full typography hierarchy, auto-scroll, debounce, and accessibility spec.

Trace container (accessibility required):
```tsx
<div role="log" aria-label="Execution trace" aria-live="polite" aria-atomic={false}
  tabIndex={0} ref={traceRef} onScroll={handleScroll}>
```

Typography hierarchy (NOT flat monospace for all columns):
- State name: 12px weight-600 `t.textPrimary` (active) / `t.textSecondary` (done)
- Conv label + agent + timestamp: 11px weight-400 `t.textMuted`

Performance: Wrap `VisitRow` in `React.memo`. Use insertion sort into already-sorted array (O(n) on new event) instead of `[...rows].sort()` on every render. Virtualize with `react-window` if trace can exceed 500 rows.

Failure detection: `PIPELINE.indexOf(nextTo) < PIPELINE.indexOf(thisTo)` → failed. Never hardcode state names.

Sort `VisitRow[]` by `ts` before rendering (EC-1.1 guard — EVENTS.jsonl/SSE race; do NOT fix the race, just sort).

Row layout:
```
  ✓  PLANNING    conv 1    planner    2h ago
  ●  BUILDING    conv 2    builder    now
  (state=12/600) (rest=11/400 muted)
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

In `HeaderBar`, read `monitorSource` and `EventSource.readyState` via `useStore()`. Render flush-right:
```tsx
const badgeText = monitorSource === 'sse' ? '● live'
  : monitorSource === 'chokidar' ? '○ polling' : '—'
const badgeColor = monitorSource === 'sse' ? t.runtime : t.textMuted
```

Badge wrapper must announce to screen readers on change:
```tsx
<span role="status" aria-live="polite" aria-atomic="true"
  aria-label={monitorSource === 'sse' ? 'Live connection' : monitorSource === 'chokidar' ? 'Polling for updates' : 'Not connected'}>
  <span aria-hidden="true">{badgeText}</span>
</span>
```

Wire `es.onerror` to distinguish `readyState === CLOSED` (fatal, set `null`) vs `CONNECTING` (auto-reconnecting, leave badge as-is). See DESIGN.md §11 for SSE resilience requirements.

Font size: `t.fontSizeSm` (12px) — NOT 11px (below readable floor for dark backgrounds).
Remove any existing `Source:` text from the header. Use `t.runtime` from Phase 1 (`theme.ts`).

**Verify:** `cd studio; npm run typecheck`

---

### Phase 4: Last-used flow on open + auto-open Monitor   ← Conversation: 1

> **Moved from old Phase 7 into Conv 1** (PO review 2026-05-20): S7 gates the value of the whole observability core for returning users. Without it, Conv 1 delivers a beautiful monitor that nobody sees on startup.

**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY: persist `lastUsedFlowPath` to localStorage.
**File:** `studio/src/renderer/src/App.tsx` — MODIFY: on mount, load last-used flow; auto-switch to Monitor if already running.

**Done when:** Studio reopens to the last-used flow; if a flow is already running on open, Monitor panel opens automatically; missing flow file clears the stored path and shows empty canvas.

**Delivers stories:** S7

**Depends on:** Phase 3 complete (fsmState available on mount).

**Details:**

```ts
// localStorage key — wrap ALL reads/writes in try/catch
// localStorage can throw in sandboxed Electron contexts and on corrupted profiles
const LAST_FLOW_KEY = 'pathly:lastUsedFlowPath'

try {
  const saved = localStorage.getItem(LAST_FLOW_KEY)
  if (saved) setLastUsedFlowPath(saved)
} catch { /* silently ignore; canvas shows empty state */ }

// On flow open
try { localStorage.setItem(LAST_FLOW_KEY, newPath) } catch {}
```

On mount in `App.tsx`, after state hydration:
```ts
useEffect(() => {
  if (fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE') {
    setActivePanel('monitor')
  }
}, [])  // run once on mount only
```

First launch: `lastUsedFlowPath` is null → canvas shows empty state (existing behavior).
File deleted: catch the readFile error, clear `lastUsedFlowPath`, show empty state.

**Verify:** `cd studio; npm run typecheck`

---

### ~~Phase 4 (old): Multi-flow Monitor tabs~~ → DEFERRED TO POST-MVP

> **Deferred (PO review 2026-05-20):** No evidence of users running ≥2 concurrent flows in Studio. The tab machinery is non-trivial and speculative. Implement when production telemetry shows multi-flow usage.
>
> The `activeFlowSessions` store slice was also architecturally problematic: populating it inside `Monitor/index.tsx`'s `useEffect` meant the data was only valid while Monitor was mounted. Any future consumer (sidebar badge, status bar) would silently read stale data. If/when tabs are revisited, the producer must be lifted to a module-level subscriber at app bootstrap — **not** inside a component lifecycle.

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

Accessibility (required — use `role="alert"`, NOT `role="status"`, per designer review):
```tsx
<div role="alert" aria-live="assertive" aria-label={`${flowName} is running in ${fsmState.current}`}>
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

### Phase 7: Blocked/waiting state amber banner   ← Conversation: 2

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: render amber callout band when `fsmState.waitingFor` is set.

**Done when:** When the active agent is blocked waiting for an artifact, an amber banner renders between the FSM rail and execution trace showing the agent name, artifact name, and elapsed wait time; banner clears when `waitingFor` becomes null/undefined.

**Delivers stories:** S8

**Depends on:** Phase 1 (rail) and Phase 2 (trace); `fsmState.waitingFor` field populated by FSM.

**Details:**

> See **DESIGN.md §10** for exact color values, layout, and accessibility markup.

Confirm `fsmState.waitingFor` field exists in STATE.json before implementing. If the field is absent in the current FSM version, add a `TODO` comment and skip rendering — do not invent a mock value.

The `●` amber dot uses `BLOCKED_AMBER` (`#FBBF24`). The callout background uses `rgba(251,191,36,0.08)` — consistent with how `t.runtime` backgrounds use `rgba(34,211,238,0.05)`.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 8: Flow-level total cost + elapsed time in Monitor header   ← Conversation: 2

**File:** `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: compute and display flow total cost and elapsed time in the header.

**Done when:** Monitor header shows `$X.XX total · ⏱ Xm Xs` when cost/time data is available; both are hidden if no data.

**Delivers stories:** S9

**Depends on:** Phase 3 (header bar), Phase 6 (per-conv cost already computed in PlanBoard — reuse the same aggregation logic).

**Details:**

Total cost: sum `cost_usd` across all `AGENT_DONE` events in EVENTS.jsonl for the current topic. Same field check as Phase 6 — if `cost_usd` field is absent, hide the cost display entirely.

Elapsed time: `Date.now() - flowStartTs`, where `flowStartTs` is the `ts` of the first `STATE_TRANSITION` event. Refresh via the same `useInterval` 30s tick used for relative timestamps in Phase 2.

Display format in header (small, `t.textMuted`, 11px):
```
[ team.flow.yaml ]    ● live    conv 3 / 5    $0.12 total · ⏱ 8m 42s
```

Use `font-variant-numeric: tabular-nums` for both cost and time values.

**Verify:** `cd studio; npm run typecheck`

---

## Prerequisites

- `studio-visual-flow-builder` Phase 7b complete (`FlowEditor/zIndex.ts` must exist for Phase 5)
- Confirm `t.runtime` in `theme.ts` before Phase 1 (add if missing)
- Confirm `conversation` field presence in EVENTS.jsonl before Phase 6 cost filtering
- Confirm `waitingFor` field presence in STATE.json before Phase 7 blocked banner
- Confirm SSE server emits `id:` per event and `: heartbeat` every 20s (DESIGN.md §11)

## Key Decisions

- Monitor and canvas are mutually exclusive (`activePanel`). "View in Monitor →" calls `setActivePanel('monitor')` — no new `bottomPanel` field.
- **Monitor tabs (S4) deferred** — no evidence of concurrent-flow usage. See crossed-out Phase 4 note.
- **`activeFlowSessions` producer must NOT live inside a component `useEffect`** — if/when tabs ship, lift producer to module-level subscriber at app bootstrap.
- Failure detection uses `pipelineStates` order (backward index = failed), never hardcoded state names.
- `prefers-reduced-motion`: opt-in pattern — base state is no animation, motion added only under `no-preference` media query.
