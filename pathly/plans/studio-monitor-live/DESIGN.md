# studio-monitor-live — Design Reference

> Builder: read this before implementing any phase. It captures every visual design decision from the architect, PO, designer, and UI/UX reviews. Keep it open alongside IMPLEMENTATION_PLAN.md.

---

## 1. Token Additions — theme.ts (Phase 1, do first)

Add to the `Theme` interface and BOTH `darkTheme` and `lightTheme` objects:

```ts
// Theme interface
runtime: string       // live/active signal color (cyan)
fontFamilyMono: string  // monospace font for logs, traces, badges

// darkTheme values
runtime: '#22D3EE',
fontFamilyMono: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",

// lightTheme values
runtime: '#0EA5E9',   // slightly desaturated — #22D3EE is too saturated on white
fontFamilyMono: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
```

`t.runtime` is the single source of truth for all live/active/running signals across Monitor, PlanBoard, Sidebar, and banner. Do not use `t.blue` for active status anywhere in this feature.

---

## 2. Color Constants (not tokens — local to component)

### `completedGreen` — for FSM rail completed-state dots

Do NOT use `t.green` (`#4ade80` — bright lime). Use a **solid** muted forest green that passes WCAG AA (3:1 contrast on dark surface). The previous `rgba(22,163,74,0.7)` failed at ~3.1:1 — replaced:

```ts
// In FsmView.tsx — define at module scope
const COMPLETED_GREEN = '#16A34A'
// Intentionally not t.green — spec requires muted forest green, not lime.
// Previously rgba(22,163,74,0.7) — alpha-blended version fails WCAG 3:1 contrast on dark bg.
```

### Cyan token split — REQUIRED

`t.runtime` (`#22D3EE`) was overloaded for both interactive chrome and data encoding. Split:

| Usage | Value |
|---|---|
| Interactive chrome: tab underline, SSE badge, header CTAs | `t.runtime` = `#22D3EE` |
| Data encoding: FSM active dot, running card border | `ACTIVE_CYAN` = `#06B6D4` |

```ts
// In FsmView.tsx and PlanBoard.tsx — define at module scope
const ACTIVE_CYAN   = '#06B6D4'  // cyan-500: data encoding only, not interactive chrome
const BLOCKED_AMBER = '#FBBF24'  // amber-400: blocked/waiting-for-artifact state
```

### Color roles summary

| Signal | Color | Token/Constant |
|---|---|---|
| Interactive chrome (tab underline, SSE badge, CTA border) | `#22D3EE` | `t.runtime` |
| Data: active / running state | `#06B6D4` | `ACTIVE_CYAN` local constant |
| Data: completed / done | `#16A34A` | `COMPLETED_GREEN` local constant |
| Data: blocked / waiting for artifact | `#FBBF24` | `BLOCKED_AMBER` local constant |
| Data: failed / error | `#F87171` (dark) / `#DC2626` (light) | `t.red` |
| Data: pending / future | `#5a5d8a` | `t.textMuted` |
| Selected / accent | `#A78BFA` | `t.accent` |

---

## 3. FSM Topology Rail — Phase 1

### Rail container
The rail container doubles as a `progressbar` for screen readers:
```tsx
<div
  role="progressbar"
  aria-valuenow={activeIdx}
  aria-valuemin={0}
  aria-valuemax={pipelineStates.length - 1}
  aria-label={`Pipeline progress: ${fsmState.current} — step ${activeIdx + 1} of ${pipelineStates.length}`}
  style={{
    display: 'flex',
    alignItems: 'center',
    position: 'relative',
    padding: '20px 16px 8px 16px',  // top padding for label clearance
    gap: 0
  }}
>
```

### Rail line (connecting dots)
Two segments — the line is live, not static:
```
// Done segment (start → active dot)
position: absolute
top: 50%
left: 16px
width: `${(activeIdx / (total-1)) * 100}%`
height: 2px          ← was 1px; 2px survives high-DPI and dark surfaces
borderRadius: 1px
backgroundColor: COMPLETED_GREEN

// Pending segment (active dot → end)
position: absolute
top: 50%
left: `calc(16px + ${(activeIdx / (total-1)) * 100}%)`
right: 16px
height: 2px
borderRadius: 1px
backgroundColor: t.bgSurface1   ← #343452
```

### State dot — shape encoding (required for accessibility)

Each dot must communicate status via **both color AND shape**, not color alone (WCAG 1.4.1):

| State | Fill | Border | Shape note |
|---|---|---|---|
| Completed | `COMPLETED_GREEN` solid | none | Filled circle |
| Active | `ACTIVE_CYAN` solid | none | Ring with inner dot (see below) |
| Future | transparent | `1px solid t.textMuted` | Hollow ring |

```ts
// Completed dot — filled circle
{ backgroundColor: COMPLETED_GREEN, border: 'none', width: 10, height: 10, borderRadius: '50%' }

// Active dot — use ring + inner dot: outer ring border in ACTIVE_CYAN, inner dot via ::after or box-shadow
{ backgroundColor: 'transparent', border: `2px solid ${ACTIVE_CYAN}`,
  boxShadow: `inset 0 0 0 3px ${ACTIVE_CYAN}`,  // creates inner filled circle
  width: 10, height: 10, borderRadius: '50%' }
// Also add pathly-pulse class for entrance animation

// Future dot
{ backgroundColor: 'transparent', border: `1px solid ${t.textMuted}`, width: 10, height: 10, borderRadius: '50%' }
// NOT bgSurface0 — too close to background, nearly invisible
```

Each dot also needs an accessible label:
```tsx
<div
  key={state}
  role="img"
  aria-label={`${state}: ${idx < activeIdx ? 'completed' : idx === activeIdx ? 'active' : 'pending'}`}
  style={dotStyle}
/>
```

### Sliding active marker (the dot that moves)
Separate absolutely-positioned element above the rail line:
```ts
position: 'absolute'
width: 12px
height: 12px
borderRadius: '50%'
backgroundColor: ACTIVE_CYAN   // data encoding — use ACTIVE_CYAN not t.runtime
top: '50%'
transform: `translateX(${offsetPx}px) translateY(-50%)`
transition: `transform ${t.transitionBase}`   // reuse existing token: '150ms ease-out'
pointerEvents: 'none'
zIndex: 2
```

**First-position calculation:** Run the initial `offsetPx` calculation synchronously in `useLayoutEffect` **before** the ResizeObserver fires. Otherwise there is a one-frame flash at position 0 on mount. ResizeObserver only handles subsequent resize events.

**Chained scale-in animation:** After the translateX transition completes, scale from 0.6 → 1.0 over 100ms:
```css
@keyframes pathly-dot-arrive {
  from { transform: translateX(var(--dot-x)) translateY(-50%) scale(0.6); }
  to   { transform: translateX(var(--dot-x)) translateY(-50%) scale(1.0); }
}
```
Apply this class on each state change, remove it after the animation ends.

**Compute `offsetPx`** from `activeIdx`, total states, and measured rail container width (`useLayoutEffect` + `ResizeObserver`).

### State labels
Labels truncate gracefully for 6+ states:
```ts
fontSize: '10px'
fontFamily: t.fontFamilyBase
textTransform: 'uppercase'
letterSpacing: '0.05em'
marginTop: '6px'
textAlign: 'center'
maxWidth: '64px'
overflow: 'hidden'
textOverflow: 'ellipsis'
whiteSpace: 'nowrap'
// Active label: color: t.textPrimary, fontWeight: 600
// Completed label: color: COMPLETED_GREEN
// Future label: color: t.textMuted
```

> **>6 states compact mode:** When `pipelineStates.length > 6`, show only the active state name inline below the active dot; replace completed/pending labels with rings showing counts: `"3 done · 2 remaining"` in `t.textMuted` 10px centered below the rail.

### Animation — prefers-reduced-motion (REQUIRED)

Use the **opt-in pattern**: base state = no motion; add motion only when `prefers-reduced-motion: no-preference`. This is safer than opt-out.

Add to the PULSE_CSS injection block in FsmView.tsx:

```css
/* Active dot pulse — 2-cycle entrance only, not infinite */
@keyframes pathly-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}
/* Run exactly 2 cycles then hold. 1.5s continuous was too aggressive for a 30-min run */
.pathly-pulse { animation: none; }
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse { animation: pathly-pulse 600ms ease-in-out 2; }
}

/* pathly-pulse-border defined in §8 Plan Cards */
.pathly-pulse-border { animation: none; }
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse-border { animation: pathly-pulse-border 600ms ease-in-out 2; }
}
```

For the sliding dot's CSS transition:
```ts
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const dotTransition = reducedMotion ? 'none' : `transform ${t.transitionBase}`
// If reduced motion: replace slide with instant opacity crossfade:
// reducedMotion: { transition: 'opacity 100ms', opacity: isActive ? 1 : 0 }
```

Or use a `useReducedMotion` hook if one exists in the codebase.

---

## 4. Execution Trace — Phase 2

### Typography — row hierarchy (required, not flat)

Do NOT render all row columns at the same weight/size. Hierarchy:

| Column | Size | Weight | Color |
|---|---|---|---|
| Status icon (`✓ ● ✗`) | 12px | — | semantic token |
| **State name** | **12px** | **600** | `t.textPrimary` (active) / `t.textSecondary` (done) |
| conv/cycle label | 11px | 400 | `t.textSecondary` |
| agent name | 11px | 400 | `t.textMuted` |
| relative time | 11px | 400 | `t.textMuted` |

```ts
fontFamily: t.fontFamilyMono   // new token from §1
lineHeight: '1.7'
whiteSpace: 'pre'
```

Cost values in the trace (if shown) must use `fontVariantNumeric: 'tabular-nums'` so columns stay aligned as values update live.

### Row color map
| Column | Color |
|---|---|
| `✓` icon | `COMPLETED_GREEN` |
| `●` icon | `ACTIVE_CYAN` (+ pathly-pulse entrance) |
| `✗` icon | `t.red` |
| State name (active) | `t.textPrimary` |
| State name (done/pending) | `t.textSecondary` |
| conv/cycle label | `t.textMuted` |
| agent name | `t.textMuted` |
| relative time | `t.textMuted` |

### Auto-scroll with user override

The trace must auto-scroll to the latest entry (append-only log), but pause auto-scroll the moment the user scrolls up:

```ts
const traceRef = useRef<HTMLDivElement>(null)
const [userScrolled, setUserScrolled] = useState(false)

// Auto-scroll on new event
useEffect(() => {
  if (!userScrolled && traceRef.current) {
    traceRef.current.scrollTop = traceRef.current.scrollHeight
  }
}, [events, userScrolled])

// Detect user scroll-up
const handleScroll = () => {
  const el = traceRef.current
  if (!el) return
  const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8
  setUserScrolled(!isAtBottom)
}
```

Show a "↓ scroll to latest" affordance in `t.textMuted` 11px when `userScrolled` is true.

### Timestamp auto-refresh

`formatRelativeTime` is computed at render time only — rows showing "2m ago" will stale. Add a `useInterval` refresh every 30 seconds to force re-render of the trace:

```ts
// In FsmView.tsx or a parent:
const [tick, setTick] = useState(0)
useEffect(() => {
  const id = setInterval(() => setTick(t => t + 1), 30_000)
  return () => clearInterval(id)
}, [])
// Include `tick` in the trace render dependencies so relative times update
```

### Debounce live region updates

For high-frequency SSE bursts (>5 events/sec), debounce the `aria-live` write by 300ms to avoid flooding screen readers:

```ts
const liveRegionRef = useRef<HTMLDivElement>(null)
const debounceRef = useRef<ReturnType<typeof setTimeout>>()

function announceLatest(msg: string) {
  clearTimeout(debounceRef.current)
  debounceRef.current = setTimeout(() => {
    if (liveRegionRef.current) liveRegionRef.current.textContent = msg
  }, 300)
}
```

### Accessibility
Wrap the trace list in:
```tsx
<div
  role="log"
  aria-label="Execution trace"
  aria-live="polite"
  aria-atomic="false"
  tabIndex={0}           // keyboard-focusable for scroll access
  ref={traceRef}
  onScroll={handleScroll}
>
```
`aria-atomic="false"` ensures only newly appended rows are announced, not the full list. `tabIndex={0}` enables keyboard scrolling with arrow keys.

### `formatRelativeTime` spec
```ts
// In Monitor/utils.ts
export function formatRelativeTime(ts: string): string {
  const diffMs = Date.now() - new Date(ts).getTime()
  const diffS = Math.floor(diffMs / 1000)
  if (diffS < 60) return 'now'
  const diffM = Math.floor(diffS / 60)
  if (diffM < 60) return `${diffM}m ago`
  return `${Math.floor(diffM / 60)}h ago`
}
```
Color for relative time: always `t.textMuted`.

---

## 5. SSE Source Badge — Phase 3

```tsx
// Three states — no lying to the user. Derived from EventSource.readyState, not just monitorSource:
// readyState 1 (OPEN) + events arriving → 'sse'
// readyState 0 (CONNECTING) → show 'reconnecting...' transitionally, then 'polling'
// readyState 2 (CLOSED) or null → '—'

monitorSource === 'sse'      → '● live'    color: t.runtime   fontSize: 12px
monitorSource === 'chokidar' → '○ polling' color: t.textMuted fontSize: 12px
null / anything else         → '—'         color: t.textMuted fontSize: 12px
```

The badge wrapper must be announced to screen readers when status changes:
```tsx
<span
  role="status"
  aria-live="polite"
  aria-atomic="true"    // re-announce full string on change, not just changed chars
  aria-label={monitorSource === 'sse' ? 'Live connection' : monitorSource === 'chokidar' ? 'Polling for updates' : 'Not connected'}
>
  <span aria-hidden="true">{badgeText}</span>
</span>
```

The `●` and `○` glyphs are `aria-hidden="true"` — the `aria-label` on the wrapper carries the text alternative.

Remove any existing `Source: SSE live` or `Source:` text from the header.

---

## 6. Monitor Tab Bar — Phase 4

### Layout
```ts
height: 32px
display: 'flex'
alignItems: 'center'
borderBottom: `1px solid ${t.bgSurface0}`
backgroundColor: t.bgMantle
paddingLeft: '8px'
gap: '2px'
role: 'tablist'
aria-label: 'Active flows'
```

### Tab button
```ts
// Base
role: 'tab'
height: '100%'
padding: '0 12px'
fontSize: '12px'
fontFamily: t.fontFamilyBase
color: t.textMuted
border: 'none'
borderBottom: '2px solid transparent'
backgroundColor: 'transparent'
cursor: 'pointer'

// Active tab
color: t.textPrimary
borderBottom: `2px solid ${t.runtime}`
backgroundColor: t.bgSurface0  // subtle bg lift

// Focus ring (keyboard)
outline: t.focusRing
outlineOffset: '-2px'
```

### Keyboard navigation (REQUIRED)
```tsx
onKeyDown={(e) => {
  if (e.key === 'ArrowRight') focusNextTab()
  if (e.key === 'ArrowLeft') focusPrevTab()
  if (e.key === 'Enter' || e.key === ' ') selectFocusedTab()
}}
```
Tab key enters the tablist; Arrow keys navigate within it. This is the standard ARIA tab pattern.

### Running indicator dot
```tsx
{s.isRunning && (
  <span
    className="pathly-pulse"
    style={{ color: t.runtime, fontSize: '8px', marginLeft: '4px' }}
    aria-hidden="true"   // decorative — tab's aria-selected conveys state
  >●</span>
)}
```

### `◐` paused state — DEFERRED TO POST-MVP
`isPaused` is always `false` in this plan (no production signal). Do NOT render the `◐` branch. Remove it from Phase 4 implementation. It will be wired when the paused signal is added.

---

## 7. Running-Flow Banner — Phase 5

### Position and size
```ts
position: 'absolute'
top: '12px'
left: '50%'
transform: 'translateX(-50%)'
maxWidth: '520px'
width: 'calc(100% - 48px)'
zIndex: Z.toast - 1    // from FlowEditor/zIndex.ts
borderRadius: '6px'
padding: '10px 14px'
backgroundColor: t.bgSurface1
border: `1px solid ${t.runtime}`
display: 'flex'
alignItems: 'center'
gap: '10px'
```

### Content layout
```
[● cyan dot] [flow.yaml is running · conv N / STATE]  [View in Monitor →]  [✕]
```

### Accessibility
The banner is a disruptive notification — use `role="alert"` (not "status") so it interrupts screen readers immediately:
```tsx
<div
  role="alert"
  aria-live="assertive"
  aria-label={`${flowName} pipeline is running in ${fsmState.current}`}
>
  {/* banner content */}
  <button
    onClick={() => setActivePanel('monitor')}
    aria-label="View running flow in Monitor panel"
  >
    View in Monitor →
  </button>
  <button
    onClick={() => setDismissed(true)}
    aria-label="Dismiss banner"
  >
    ✕
  </button>
</div>
```

### Hover-to-pause auto-dismiss (REQUIRED)
```ts
const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

function startTimer() {
  timerRef.current = setTimeout(() => setDismissed(true), 8000)
}
function clearTimer() {
  if (timerRef.current) clearTimeout(timerRef.current)
}

useEffect(() => {
  if (!isRunning || dismissed) return
  startTimer()
  return clearTimer
}, [isRunning, dismissed])

// On the banner div:
onMouseEnter={clearTimer}
onMouseLeave={startTimer}
```

---

## 8. Plan Conversation Cards — Phase 6

### PlanBoard active-status color change (REQUIRED before new work)
Replace `t.blue` with `t.runtime` in `statusBorderColor` and `statusBgColor` for active statuses:
```ts
// statusBorderColor — change
if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
  return t.runtime    // was t.blue

// statusBgColor — change
if (status === 'IN_PROGRESS' || ...) return 'rgba(34,211,238,0.05)'  // was blue tint
```
`t.blue` (#60AAFF) remains only in EventLog's `eventType` label color — do NOT replace there.

### Pulsing border — 2-cycle entrance only, color only, width stays fixed

Card always has `borderLeft: '3px solid <color>'`. Active: color = `ACTIVE_CYAN`. Pulse runs **exactly 2 cycles** to draw attention on state entry, then holds steady — not an infinite loop (a 30-min run with a 1.5s infinite pulse is visual noise):
```css
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: #06B6D4; }
  50%       { border-left-color: rgba(6,182,212,0.15); }
}

/* Base: no animation */
.pathly-pulse-border { border-left-color: #06B6D4; }
/* Add motion only when allowed — 2 cycles then hold */
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse-border { animation: pathly-pulse-border 600ms ease-in-out 2; }
}
```
Inject once via `styleInjectedRef` (same pattern as FsmView). Apply class on card mount when status is active; remove the class after `animationend` fires (so re-activating a card re-triggers the entrance).

### Card click → selected state
Cards are interactive. Wrap each card in a `<button>` or add:
```tsx
<div
  role="button"
  tabIndex={0}
  onClick={() => setSelectedConv(conv.num)}
  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedConv(conv.num) }}
  style={{ cursor: 'pointer' }}
  aria-pressed={selectedConv === conv.num}
>
```

### Hover / selected visual states
```ts
// Hover (via onMouseEnter/Leave — track hoveredConv state)
backgroundColor: t.bgSurface1

// Selected (selectedConv === conv.num)
backgroundColor: t.bgSurface1
borderLeft: `3px solid ${t.accent}`   // violet replaces status color while selected
```

### Card layout (52px min-height)
```
┌─ 3px left border ─────────────────────────────────────────┐
│  [icon]  Conv N · Phase title               [status badge] │  ← row 1
│          agents · Phase N–M · 2h ago                       │  ← row 2
│          12.1k in / 1.8k out · $0.031                      │  ← row 3 (if data)
└────────────────────────────────────────────────────────────┘
```
Row 1: `fontSize: 14px, color: t.textPrimary`
Row 2: `fontSize: 12px, color: t.textMuted, fontFamily: t.fontFamilyMono`
Row 3: `fontSize: 12px, color: t.textMuted, fontFamily: t.fontFamilyMono, fontVariantNumeric: 'tabular-nums'` — hide if no cost data

`tabular-nums` on the cost row ensures `Xk in / Yk out · $Z` stays column-aligned as values update live.

---

## 9. Last-Used Flow + Theme Persistence — Phase 4 (Conv 1)

```ts
// localStorage key
const LAST_FLOW_KEY = 'pathly:lastUsedFlowPath'

// On init — wrap in try/catch (localStorage can throw in sandboxed contexts)
try {
  const saved = localStorage.getItem(LAST_FLOW_KEY)
  if (saved) setLastUsedFlowPath(saved)
} catch { /* silently ignore; canvas shows empty state */ }

// On change
try { localStorage.setItem(LAST_FLOW_KEY, newPath) } catch { /* ignore */ }
```

Light/dark theme already persists via `useTheme.ts` — no changes needed there.

---

## 10. Blocked/Waiting State Banner — Phase 7 (Conv 2)

When an agent is blocked waiting for an artifact, this is the most actionable info on the panel. Surface it as a first-class amber callout band between the FSM rail and the trace pane — not as sub-label text below the active dot.

### Trigger condition
```ts
const isBlocked = fsmState.waitingFor !== undefined && fsmState.waitingFor !== null
// fsmState.waitingFor: e.g. 'REVIEW_FAILURES.md' — populated by FSM when agent yields
```

### Visual spec
```tsx
{isBlocked && (
  <div
    role="status"
    aria-live="polite"
    aria-label={`Pipeline blocked: ${fsmState.activeAgent} is waiting on ${fsmState.waitingFor}`}
    style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 12px',
      backgroundColor: 'rgba(251,191,36,0.08)',   // BLOCKED_AMBER at 8% opacity
      borderLeft: `3px solid ${BLOCKED_AMBER}`,
      fontSize: '12px',
      color: t.textPrimary,
      fontFamily: t.fontFamilyMono,
    }}
  >
    <span style={{ color: BLOCKED_AMBER }}>●</span>
    <span>{fsmState.activeAgent} is waiting on</span>
    <strong style={{ color: BLOCKED_AMBER }}>{fsmState.waitingFor}</strong>
    <span style={{ color: t.textMuted, marginLeft: 'auto' }}>
      since {formatRelativeTime(fsmState.blockedSince)}
    </span>
  </div>
)}
```

Renders between the FSM rail and the execution trace. Only one blocked banner at a time. Clears when `waitingFor` becomes null.

---

## 11. SSE Resilience — Notes for Phase 3 Implementation

These are server-side requirements that the renderer relies on. Confirm with the backend before Phase 3 ships:

| Requirement | Why | Server action |
|---|---|---|
| `id: <seq>` on every event | Enables `Last-Event-ID` replay on reconnect; without it, trace holes after drop | Server must emit `id:` per message |
| `retry: 5000` directive | Overrides browser's 3s default; 5s is a reasonable floor for monitoring | Server emits `retry: 5000\n` on connect |
| `: heartbeat` comment every 20s | Prevents corporate proxies from closing idle HTTP connections silently | Server sends SSE comment `": heartbeat"` |

Client-side `onerror` handling:
```ts
es.onerror = () => {
  if (es.readyState === EventSource.CLOSED) {
    // Fatal — server closed connection or auth failed. Do not auto-reconnect blindly.
    setMonitorSource(null)
    // Show '—' badge; do not show 'reconnecting' — the connection is gone
  }
  // readyState === CONNECTING → browser is auto-reconnecting (SSE default backoff)
  // Leave monitorSource as-is; badge already shows current state
}
```

---

## 12. Deferred Features — Not in This Plan

These are real product gaps identified in the PO review (2026-05-20). They are out of scope here but should be planned in a follow-on feature:

| Feature | Gap | Priority |
|---|---|---|
| **Stop/Cancel flow** | User has no way to halt a running flow from Studio. A runaway loop in FIXING burns tokens with no recourse. | High — plan immediately after Conv 2 ships |
| **Error detail drill-down** | `✗` icon in trace shows failure but no error message. User must leave Studio to see logs. | High |
| **Flow-level total cost + elapsed time** | S6 shows per-conversation cost. The flow header has no total `$X.XX` or `⏱ 12m 43s`. | Medium |
| **Monitor tabs (S4)** | Deferred from MVP. Implement when there is evidence of ≥2 concurrent flows in production. | Low until evidence |
