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

Do NOT use `t.green` (`#4ade80` — bright lime). The spec requires a muted forest green:

```ts
// In FsmView.tsx — define at module scope
const COMPLETED_GREEN = 'rgba(22, 163, 74, 0.7)'  // #16A34A at 70% opacity
```

Add comment: `// Intentionally not t.green — spec requires muted forest green, not lime`

### Color roles summary

| Signal | Color | Token/Constant |
|---|---|---|
| Live / active / running | #22D3EE | `t.runtime` |
| Completed / done | rgba(22,163,74,0.7) | `COMPLETED_GREEN` local constant |
| Failed / error | #f87171 (dark) / #dc2626 (light) | `t.red` |
| Pending / future | #5a5d8a | `t.textMuted` |
| Selected / accent | #A78BFA | `t.accent` |

---

## 3. FSM Topology Rail — Phase 1

### Rail container
```
display: flex
align-items: center
position: relative
padding: 20px 16px 8px 16px   ← top padding for label clearance
gap: 0                          ← dots and line handled absolutely
```

### Rail line (connecting dots)
```
position: absolute
top: 50%  (of the dot row — ~5px from container top after padding)
left: 16px
right: 16px
height: 1px
backgroundColor: t.bgSurface1   ← #343452 — NOT bgSurface0 (#252538, too faint)
```

### State dot (each state node)
```
width: 10px
height: 10px
borderRadius: '50%'
position: relative   ← sits above the rail line (z-index: 1)
flexShrink: 0
```

**Completed dot:**
```ts
backgroundColor: COMPLETED_GREEN
border: 'none'
```

**Active dot (the visible circle):**
```ts
backgroundColor: t.runtime     // cyan fill
border: 'none'
// add pathly-pulse class for animation
```

**Future dot:**
```ts
backgroundColor: 'transparent'
border: `1px solid ${t.textMuted}`   // ← textMuted stroke, transparent fill
// NOT bgSurface0 — too close to background, nearly invisible
```

### Sliding active marker (the dot that moves)
Separate absolutely-positioned element above the rail line:
```ts
position: 'absolute'
width: 12px
height: 12px
borderRadius: '50%'
backgroundColor: t.runtime
top: '50%'
transform: `translateX(${offsetPx}px) translateY(-50%)`
transition: `transform ${t.transitionBase}`   // reuse existing token: '150ms ease-out'
pointerEvents: 'none'
zIndex: 2
```
Compute `offsetPx` from `activeIdx`, total states, and measured rail container width (`useLayoutEffect` + `ResizeObserver`).

### State labels
```ts
fontSize: '11px'          // label below dot — smaller than rail to keep compact
color: t.textMuted
fontFamily: t.fontFamilyBase
textTransform: 'uppercase'
letterSpacing: '0.03em'
marginTop: '6px'
textAlign: 'center'
// Active label: color: t.textPrimary, fontWeight: 600
// Completed label: color: COMPLETED_GREEN
```

### Animation — prefers-reduced-motion (REQUIRED)

Add to the PULSE_CSS injection block in FsmView.tsx:

```css
@keyframes pathly-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.pathly-pulse { animation: pathly-pulse 1.5s ease-in-out infinite; }
/* 1.5s: status heartbeat — intentional, not a micro-interaction */

@media (prefers-reduced-motion: reduce) {
  .pathly-pulse { animation: none; }
  .pathly-pulse-border { animation: none; }
}
```

For the sliding dot's CSS transition, add inline:
```ts
transition: window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ? 'none'
  : `transform ${t.transitionBase}`
```

Or use a `useReducedMotion` hook if one exists in the codebase.

---

## 4. Execution Trace — Phase 2

### Typography
```ts
fontFamily: t.fontFamilyMono   // new token from §1
fontSize: '12px'               // t.fontSizeSm — acceptable for developer tool log surface
lineHeight: '1.7'
whiteSpace: 'pre'
```

### Row color map
| Column | Color |
|---|---|
| `✓` icon | COMPLETED_GREEN |
| `●` icon | `t.runtime` (+ pathly-pulse) |
| `✗` icon | `t.red` |
| State name (active) | `t.textPrimary` |
| State name (done/pending) | `t.textSecondary` |
| conv/cycle label | `t.textMuted` |
| agent name | `t.textMuted` |
| relative time | `t.textMuted` |

### Accessibility
Wrap the trace list in:
```tsx
<div
  role="log"
  aria-label="Execution trace"
  aria-live="polite"
  aria-atomic="false"
>
```
`aria-atomic="false"` ensures only newly appended rows are announced, not the full list.

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

```ts
// Three states — no lying to the user
monitorSource === 'sse'      → '● live'    color: t.runtime   fontSize: t.fontSizeSm (12px)
monitorSource === 'chokidar' → '○ polling' color: t.textMuted fontSize: t.fontSizeSm (12px)
null / anything else         → '—'         color: t.textMuted fontSize: t.fontSizeSm (12px)
```

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
```tsx
<div
  role="status"
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

### Pulsing border — color only, width stays fixed
Card always has `borderLeft: '3px solid <color>'`. Active: color = `t.runtime`. Pulse animates the color, never the width:
```css
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: #22D3EE; }
  50% { border-left-color: rgba(34,211,238,0.15); }
}
.pathly-pulse-border { animation: pathly-pulse-border 1.5s ease-in-out infinite; }
/* 1.5s: status heartbeat — intentional */
```
Inject once via `styleInjectedRef` (same pattern as FsmView). Include `prefers-reduced-motion: reduce` → `animation: none` in the same block.

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
Row 3: `fontSize: 12px, color: t.textMuted, fontFamily: t.fontFamilyMono` — hide if no cost data

---

## 9. Last-Used Flow + Theme Persistence — Phase 7

```ts
// localStorage key
const LAST_FLOW_KEY = 'pathly:lastUsedFlowPath'

// On init
const saved = localStorage.getItem(LAST_FLOW_KEY)
if (saved) setLastUsedFlowPath(saved)

// On change
localStorage.setItem(LAST_FLOW_KEY, newPath)
```

Light/dark theme also already persists via `useTheme.ts` — no changes needed there.
