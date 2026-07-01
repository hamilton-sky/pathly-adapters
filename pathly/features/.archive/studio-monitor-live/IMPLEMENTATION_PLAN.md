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
- **Loop/retry badge**: when a state has been visited more than once (`visitCount > 1`), render a small `↩ N` badge above the dot (12px, `t.textMuted`, no color change to the dot itself). This is additive — count visits from the execution trace rows. Matches production pattern (CircleCI, GitHub Actions) where loops are annotated not animated.

**ResizeObserver pitfalls (architect review 2026-05-20):**
- **"ResizeObserver loop completed with undelivered notifications"**: if the dot-transform write causes a layout change that re-triggers the observer, you get console spam. Mitigation: write the translated value to a CSS custom property on the parent element instead of directly setting `style.transform` on the dot — this avoids the observed element's layout being dirtied by the observer callback. Alternatively, `requestAnimationFrame`-debounce the handler.
- **Font loading race**: `useLayoutEffect` runs before web fonts resolve. State label widths depend on text metrics, so the first-paint dot position may be wrong and then jump when fonts load. Fix: subscribe to `document.fonts.ready` once on mount and recompute the dot position after fonts are settled.
- **Strict Mode double-invoke**: `useLayoutEffect` runs twice in React dev/Strict Mode. Ensure the ResizeObserver setup is idempotent — disconnect before reconnecting, or check `observerRef.current` before creating a new one.

> **Why connected rail over canvas diagram (decision recorded 2026-05-20):** The canvas is for flow *editing* (React Flow nodes, YAML structure). The monitor needs a single instant read: "where is the pipeline now?" A full canvas diagram adds node boxes, edge curves, and zoom overhead that slow this read. The connected dot rail is the correct monitor primitive — dense, linear, CI/CD-standard (GitHub Actions, GitLab, Buildkite all converge here). Canvas-style visualization belongs in the flow editor, not the monitor panel.

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

**`prefers-reduced-motion` — static fallback required, not just `animation: none`** (Pope Tech / web.dev finding): removing animation without a static alternative is an accessibility regression if the animation communicates state. The active dot must remain visually distinct (ring + inner dot with `ACTIVE_CYAN`) even when all animation is disabled — the shape encoding is what carries the state information, not the pulse. Confirm the no-animation render still passes WCAG 1.4.1 before shipping.

**Runtime subscription**: subscribe to `window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', handler)` in the same `useEffect` that sets up the initial value. Users can toggle accessibility settings at runtime; reading once on mount leaves the component stale.

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

**`role="log"` mount rule** (W3C ARIA23): the live region must be present and empty in the DOM on initial render — not dynamically injected after data loads. If you conditionally render this container, the screen reader won't have registered it when events start arriving. Mount it unconditionally; show the empty-state message inside it.

**Failed-row copy** (PatternFly pattern): use specific past-tense descriptions for failed rows, not a generic `✗ failed` label. Example: `✗ REVIEWING — issues found, retried` rather than just `✗`. The failure reason comes from the transition metadata, not invented copy.

Typography hierarchy (NOT flat monospace for all columns):
- State name: 12px weight-600 `t.textPrimary` (active) / `t.textSecondary` (done)
- Conv label + agent + timestamp: 11px weight-400 `t.textMuted`

Performance: Wrap `VisitRow` in `React.memo`. Use insertion sort into already-sorted array (O(n) on new event) instead of `[...rows].sort()` on every render.

**Virtualize from row 1 — not at 500 rows** (architect + web research review): 500 rows × ~40px = 20,000px of DOM with ~25 visible. A 3-hour pipeline can easily emit 5,000+ events. The cost of `react-window` is one wrapper; the cost of late adoption is unbounded DOM growth. Use `react-logviewer` (melloware fork — actively maintained, has built-in ScrollFollow behavior) or `react-scroll-to-bottom`. Do NOT use `react-lazylog` — archived September 2024.

**SSE backpressure**: React 18 auto-batches updates inside event handlers but behavior inside `EventSource.onmessage` callbacks varies. Wrap rapid-fire event dispatch in `ReactDOM.unstable_batchedUpdates` (or `flushSync` if ordering matters) to prevent excessive re-renders when the SSE server emits bursts (e.g. 10+ events on flow start).

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

**Depends on:** `monitorSource` in projectStore (type: `'http' | 'chokidar' | 'sse' | null`). `t.runtime` from Phase 1.

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

**Cold-start timeout** (architect review): if no `open` event fires within 5s of `new EventSource(...)`, treat as failure — set `monitorHealth: 'offline'`, show `—` badge, and retry with exponential backoff. "CONNECTING → leave as-is" is silent failure when the server is down on boot.

**Reconnecting state** (Ably / OneUptime finding): when connection drops and SSE is auto-reconnecting, show `↻ reconnecting` text next to the badge instead of staying silent. Silent failure is the worst outcome — users assume polling is working when it isn't.

**Badge flashing** (Vercel Geist finding): only update the badge when `readyState` actually changes — do NOT update it on every SSE message receipt. Updating on every tick causes unnecessary `role="status"` announcements that flood screen readers.

**Screen reader debounce**: the `role="status"` wrapper for the badge should debounce its `aria-label` updates. Multiple rapid reconnect cycles (CONNECTING → OPEN → CLOSED → CONNECTING) within 1s should announce only the final stable state.

**Event-ID deduplication**: maintain a `Set<string>` of processed event IDs in the store. `Last-Event-ID` replay on auto-reconnect means the same `AGENT_DONE` can arrive twice and double cost totals. Guard all cost-aggregation writes with this set. Key: `event.lastEventId` from the MessageEvent.

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

**localStorage failure modes** (architect review): the `try/catch` in the plan handles sandboxed-context throws, but two additional failure modes need coverage:
- `QuotaExceededError` on write — catch this separately, log a warning, continue without persisting
- JSON parse failure on read (corrupted entry) — wrap `JSON.parse` in try/catch; on failure, delete the key and show empty state. Applies if `lastUsedFlowPath` is ever serialised as JSON rather than a raw string.

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

**Cost aggregation semantics — decide before shipping** (architect review, confirmed by screenshot showing RETRY events): the screenshot shows a flow that retried conv-4 twice (`RETRY conv-4:REVIEW_FAILURES.md` appears twice). Does a retried conversation emit two `AGENT_DONE` events? If yes, decide: **sum them** (true cost = what you actually paid) vs **take only the last** (logical cost = final successful run). Decision affects user mental model and cannot be changed silently after shipping. Recommendation: sum all `AGENT_DONE` events for the same `conversation` — users should see true cost, not an undercount.

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

Elapsed time: use `serverNow - flowStartTs` where **both values come from event `ts` fields** — do NOT use `Date.now()` for the current end of the range. Clock skew between the Electron renderer clock and the SSE server clock (which wrote the `ts` values) will produce negative or wildly wrong durations. Instead: track the `ts` of the most recent event received; elapsed = `mostRecentEventTs - flowStartTs`. Refresh via the same `useInterval` 30s tick used for relative timestamps in Phase 2.

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
- **Confirm error envelope in EVENTS.jsonl** (e.g. `{error: {message, stack}}` on failed STATE_TRANSITION or AGENT_DONE events) — required for post-MVP error drill-down. If absent, schedule schema addition before Conv 2.

## Must-Fix Before Conv 1 Coding (from plan review 2026-05-20)

> These are not scope changes — they are fixes to planning errors and architecture gaps identified in cross-review.

1. **Delete Phase 7 (Conv 2)** — it duplicates Phase 4 (Conv 1). Both implement `lastUsedFlowPath` + auto-open Monitor. Phase 7 is leftover from the multi-tab strikethrough. If genuine persistence-hardening work exists (multi-project scope, schema migration), rename it and spec only the delta.

2. **SSE cold-start timeout** — add to Phase 3 spec: if no `open` event fires within 5s of `new EventSource(...)`, treat as failure (`monitorHealth: 'offline'`), show `—` badge, retry with exponential backoff. The current "CONNECTING → leave as-is" rule is silent failure on boot when the server is down.

3. **Event-ID deduplication** — add to Phase 3 spec: maintain a `Set<string>` of processed event IDs in the store. `Last-Event-ID` replay on reconnect means the same `AGENT_DONE` can arrive twice, doubling cost totals. Guard all cost aggregation with this set.

4. **Move `activeFlowSessions` producer to module level in Phase 1** — not deferred until tabs. The current single-flow producer in `useEffect` leaks across HMR, double-subscribes in React Strict Mode, and loses events during unmount. Lift to a module-level subscriber at app bootstrap (alongside the SSE `EventSource` setup). This is ~10 lines and pre-pays the tab architecture.

5. **`prefers-reduced-motion` subscription** — add to Phase 1 spec: subscribe to `matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', ...)` rather than reading once on mount. Users can toggle this at runtime.

## Should-Fix Before Conv 2 Coding

- **Split `monitorSource`** into `monitorTransport: 'sse' | 'chokidar' | null` + `monitorHealth: 'live' | 'degraded' | 'offline'`. Current `null` conflates "no transport" with "transport failed."
- **Add `runId` to session shape** now — stop/cancel (highest-priority post-MVP) requires threading a run identifier through every card. Adding it now costs 0 effort; retrofitting costs a half-day.
- **Type `activeMonitorTab` as `SessionId | null`** now — avoids a breaking type change when tabs ship.
- **Define banner precedence policy** — running banner vs blocked banner vs (future) error banner. Which wins? What is the z-order? `FlowEditor/zIndex.ts` is a prereq for z-value but the policy is unspecified.

## Key Decisions

- Monitor and canvas are mutually exclusive (`activePanel`). "View in Monitor →" calls `setActivePanel('monitor')` — no new `bottomPanel` field.
- **Monitor tabs (S4) deferred** — no evidence of concurrent-flow usage. See crossed-out Phase 4 note.
- **`activeFlowSessions` producer must NOT live inside a component `useEffect`** — lift to module-level subscriber at app bootstrap in Phase 1 (see Must-Fix #4 above).
- **Canvas diagram NOT used in Monitor** — the connected dot rail is the correct monitor primitive. Canvas-style visualization (React Flow nodes, edge curves) belongs in the flow editor. Decision confirmed 2026-05-20. Sources: GitHub Actions, GitLab CI, Buildkite, Vercel all converge on linear stepper rails for monitoring; XState Visualizer uses canvas for topology editing, not runtime observation.
- Failure detection uses `pipelineStates` order (backward index = failed), never hardcoded state names.
- `prefers-reduced-motion`: opt-in pattern — base state is no animation, motion added only under `no-preference` media query. Subscribe to `matchMedia.change` at runtime — do not read once on mount.
- **`prefers-reduced-motion` static fallback required**: removing animation without a static visual alternative is an accessibility regression (Pope Tech, ESRI ArcGIS production precedent). The active dot ring+fill must remain visually distinct under `reduce` — shape encoding carries state, not pulse alone.
- **Loop/retry annotation**: dot snaps back on loop (no backward rail animation — CI/CD production consensus); `↩ N` badge above dot when `visitCount > 1`. Sources: CircleCI, GitHub Actions, Buildkite all avoid dot regression and use retry counters instead.
- **Execution trace library**: use `react-logviewer` (melloware fork, active maintained) or `react-scroll-to-bottom` — NOT `react-lazylog` (archived 2024-09). Virtualize from row 1, not at a 500-row threshold. Follow-tail pattern (scroll-up pauses, "↓ scroll to latest" affordance, return-to-bottom resumes) is the production standard: GitHub Actions, OrbStack, VS Code terminal all implement it.
- **Time source for elapsed/relative timestamps**: use server `ts` from event payloads as both reference points — do not mix `Date.now()` with server timestamps. Clock skew between Electron renderer and SSE server will produce negative durations.
- **Cost aggregation on retries**: sum ALL `AGENT_DONE` events for a conversation (including retried runs) — true cost, not logical cost. Cannot be changed silently after shipping.
- **SSE badge update frequency**: update badge state only on `readyState` transitions, NOT on every event receipt (Vercel Geist production pattern). Prevents screen reader flooding.
- **`role="log"` must be present on initial render** (W3C ARIA23): mount the trace container unconditionally; don't conditionally render it after data loads or the screen reader won't have registered the live region.
