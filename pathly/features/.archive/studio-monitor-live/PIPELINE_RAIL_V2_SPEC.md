# Pipeline Rail V2 — Vertical Stepper Spec

> Feature: studio-monitor-live
> Component: replaces horizontal FSM rail in `Monitor/FsmView.tsx`
> Date: 2026-05-20
> Stack: React + inline styles only (no CSS modules)
> Target container width: 220–300px

---

## Why the horizontal rail is being replaced

The existing horizontal rail (MONITOR_DESIGN_SPEC.md) has six documented defects at 8 states on a narrow panel:

- 10px dots — below the 16px industry minimum; invisible at arm's length
- Labels truncate at "REVIEWIN…" — `maxWidth: 64px` is inadequate for 9-char uppercase labels at 10px
- Sliding marker + static ring-dot produce a double-dot overlap
- Percentage-based line segments bleed past dot boundaries
- Compact mode (labels hidden for >6 states) degrades to no label context at all
- Horizontal layout exhausts horizontal space; sidebar cannot grow wider

A vertical layout eliminates all six problems: dots stack down the Y axis, labels sit beside each dot with 140–160px of text room, and no sliding marker is needed.

---

## ASCII — Before / After

### BEFORE (horizontal rail, 8 states, 280px container)

```
conv 2 · 3 done · 4 remaining

← 16px → [●][●][●][●][○][○][○][○] ← 10px dots, cramped
                      ↑
              12px sliding cyan marker (overlaps ring dot)

Rail line: done ████████████████░░░░░░░░░░░░░░░░ pending

STORM- PLANN- BUILD- REVIE- REVIEWIN… TESTIN… RETRO DONE
                              ↑ truncated
```

### AFTER (vertical stepper, 8 states, 220–300px container)

```
conv 2 · 4 done · 3 remaining          ← 11px textMuted, top of section

  │                                     ← rail line, left: 8px from padding edge
  ●  STORMING                           ← completed: solid #16A34A dot, textMuted label
  │
  ●  PLANNING                           ← completed
  │
  ●  BUILDING                           ← completed
  │
  ●  REVIEWING                          ← completed
  │
  ◉  ARCHITECTURE                       ← ACTIVE: ring-with-fill, textPrimary bold
  │
  ○  TESTING                            ← pending: hollow muted ring
  │
  ○  RETRO                              ← pending
  │
  ○  DONE                               ← pending
```

Legend:
- `●` solid #16A34A — completed
- `◉` ring 2px #06B6D4 border + inset 4px fill — active
- `○` 1px solid #5a5d8a hollow — pending
- `│` 2px rail line — completed segment #16A34A, pending segment #343452

---

## Token / Constant Reference

| Name | Value | Source |
|---|---|---|
| `bgBase` | `#0e0e1a` | theme token |
| `bgSurface0` | `#1a1a2e` | theme token |
| `bgSurface1` | `#343452` | theme token |
| `textPrimary` | `#e2e3f0` | theme token |
| `textSecondary` | `#9ca3af` | theme token |
| `textMuted` | `#5a5d8a` | theme token |
| `accent` | `#7c6af7` | theme token |
| `focusRing` | `0 0 0 2px #7c6af7` | theme token |
| `transitionBase` | `150ms ease-out` | theme token |
| `fontFamilyMono` | `Geist Mono` | theme token |
| `COMPLETED_GREEN` | `#16A34A` | local constant (not t.green — #4ade80 is lime, fails WCAG on dark bg) |
| `ACTIVE_CYAN` | `#06B6D4` | local constant (data encoding only — t.runtime #22D3EE is for chrome) |

Define at module scope in `FsmView.tsx`:

```ts
const COMPLETED_GREEN = '#16A34A'
const ACTIVE_CYAN     = '#06B6D4'
```

---

## Element Specs

### 1. Container — outer wrapper

```ts
{
  display: 'flex',
  flexDirection: 'column',
  gap: 0,
  padding: '8px 12px 12px 12px',
  // padding-left 12px = 8px rail inset + 4px breathing room before dot
  // container width 220–300px — no fixed width, fills panel
}
```

Accessibility:
```tsx
<div
  role="group"
  aria-label={`Pipeline progress: ${currentState} — step ${activeIdx + 1} of ${totalStates}`}
>
```

Note: `role="group"` rather than `role="progressbar"` because the stepper is not a linear 0–100% progress bar — it is a named-step pipeline where state transitions are not uniform. Screen readers will announce the group label on entry. Individual step items carry their own `role="listitem"` status.

Wrap the step list in:
```tsx
<ol
  role="list"
  aria-label="Pipeline states"
  style={{ listStyle: 'none', margin: 0, padding: 0, position: 'relative' }}
>
```

---

### 2. Conv/count indicator line

Positioned above the step list. Always visible. Updates live.

```tsx
<div
  aria-live="polite"
  aria-atomic="true"
  style={{
    fontSize: '11px',
    fontFamily: t.fontFamilyMono,
    color: t.textMuted,              // #5a5d8a
    letterSpacing: '0.02em',
    marginBottom: '8px',
    paddingLeft: '20px',             // aligns text with label column (dot width 16px + gap 4px)
    whiteSpace: 'nowrap',
  }}
>
  {convLabel} {convNum} · {doneCount} done · {remainingCount} remaining
</div>
```

Example output: `conv 2 · 4 done · 3 remaining`

`convLabel` is `'cycle'` for debug/explore modes, `'conv'` for normal pipeline mode.

---

### 3. Rail line (vertical, two segments)

The rail line is a 2px-wide vertical line that runs from the first dot center to the last dot center. It is split at the active dot's vertical midpoint: completed segment in `COMPLETED_GREEN`, pending segment in `bgSurface1`.

Implementation approach: render the rail line as two absolutely-positioned divs behind the step list. The step list wrapper has `position: 'relative'`.

```ts
// Shared rail line base
const railLineBase = {
  position: 'absolute' as const,
  left: '19px',    // 12px container padding-left + 8px = center-x of 16px dot
               // dot center-x = paddingLeft(12) + dotRadius(8) = 20px
               // but the 2px rail should be centered: left = 20 - 1 = 19px
  width: '2px',
  borderRadius: '1px',
  pointerEvents: 'none' as const,
  zIndex: 0,
}
```

Compute segment heights from step item heights. The cleanest approach: measure the step list's total height and use the step-item row height × index as the split point.

Each step row is 28px tall (16px dot + vertical gap 6px above + 6px below). Total rail height = `(totalStates - 1) * 28px`. The split point = `activeIdx * 28 + 14` (center of the active dot row).

```ts
const rowHeight = 28         // px per step item
const dotCenterOffset = 14   // half of rowHeight — center of dot within its row
const totalRailHeight = (totalStates - 1) * rowHeight
const splitY = activeIdx * rowHeight + dotCenterOffset

// Top (first dot center) offset: the first dot's center-y relative to the ol top
// = dotCenterOffset of row 0 = 14px
const railTop = dotCenterOffset  // 14px — first dot center

// Completed segment: from first dot center to active dot center
const completedSegmentStyle = {
  ...railLineBase,
  top: `${railTop}px`,
  height: `${splitY - railTop}px`,
  backgroundColor: COMPLETED_GREEN,
}

// Pending segment: from active dot center to last dot center
const pendingSegmentStyle = {
  ...railLineBase,
  top: `${splitY}px`,
  height: `${totalRailHeight - splitY + railTop}px`,
  backgroundColor: t.bgSurface1,   // #343452
}
```

When `activeIdx === 0`: completed segment height = 0, hide it (do not render a zero-height div).
When `activeIdx === totalStates - 1`: pending segment height = 0, hide it.

---

### 4. Step row

Each pipeline state is a list item containing: dot + label side by side.

```ts
const stepRowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',               // gap between dot and label
  height: '28px',           // fixed — used for rail line math
  position: 'relative' as const,
  zIndex: 1,                // above rail line (zIndex: 0)
  cursor: 'default',
}
```

```tsx
<li
  key={state}
  role="listitem"
  aria-label={`${state}: ${status}`}   // status = 'completed' | 'active' | 'pending'
  style={stepRowStyle}
>
  <DotComponent status={status} />
  <LabelComponent state={state} status={status} />
</li>
```

---

### 5. Dot — three states

All dots: `width: 16px, height: 16px, borderRadius: '50%', flexShrink: 0`.

The dot center-x within the step row = `paddingLeft(12) + 8 = 20px` from container left edge. The rail line at `left: 19px` with `width: 2px` is centered on this x position.

#### 5a. Completed dot

```ts
{
  width: 16,
  height: 16,
  borderRadius: '50%',
  flexShrink: 0,
  backgroundColor: COMPLETED_GREEN,   // #16A34A — solid, no alpha
  border: 'none',
}
```

#### 5b. Active dot — ring-with-inner-fill

The design requires a 16px circle with a visible ring (2px cyan border) and a filled center. The math:

- Outer diameter: 16px
- Border: 2px → border consumes 4px total (2px per side)
- Interior diameter: 12px
- Desired inner fill: solid center circle of 8px, leaving a 2px gap ring between border and fill
- `boxShadow: inset 0 0 0 4px ACTIVE_CYAN` draws a solid fill starting 4px inward from element edge
- That leaves a (16 - 2×4)px = 8px solid center — but on top of the 2px border, the ring visible between border and fill = 4px inset − 2px border = 2px gap ring

This is correct. The gap ring is 2px wide. The center fill diameter = 16 − 2×4 = 8px.

```ts
{
  width: 16,
  height: 16,
  borderRadius: '50%',
  flexShrink: 0,
  backgroundColor: 'transparent',
  border: `2px solid ${ACTIVE_CYAN}`,                 // outer ring: #06B6D4
  boxShadow: `inset 0 0 0 4px ${ACTIVE_CYAN}`,       // inner fill: 8px diameter center
}
```

No pulsing animation on the dot itself. The ring-with-fill is a static, clear indicator. Pulsing is reserved for the 2-cycle entrance animation on state entry only (see Section 8 — Animation).

#### 5c. Pending dot

```ts
{
  width: 16,
  height: 16,
  borderRadius: '50%',
  flexShrink: 0,
  backgroundColor: 'transparent',
  border: `1px solid ${t.textMuted}`,   // #5a5d8a — hollow ring
}
```

---

### 6. Label — three states

Label sits to the right of the dot, single line, never wraps. In a 220px container: dot column = 16px, gap = 8px, label column = 220 − 12 − 16 − 8 − 12 = 172px. At 300px: 252px. Both are sufficient for "ARCHITECTURE" (12 chars at 12px Geist Mono ≈ 86px). No truncation expected for typical pipeline state names up to 12 characters.

#### 6a. Active label

```ts
{
  fontSize: '12px',
  fontFamily: t.fontFamilyMono,
  fontWeight: 600,
  color: t.textPrimary,             // #e2e3f0
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}
```

#### 6b. Completed label

```ts
{
  fontSize: '11px',
  fontFamily: t.fontFamilyMono,
  fontWeight: 400,
  color: t.textMuted,               // #5a5d8a
  letterSpacing: '0.03em',
  textTransform: 'uppercase',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}
```

#### 6c. Pending label

Same as completed label — identical style. Both are de-emphasized. The active label's weight-600 and `textPrimary` color create the visual hierarchy without any additional differentiation between done and not-yet-done states.

```ts
{
  fontSize: '11px',
  fontFamily: t.fontFamilyMono,
  fontWeight: 400,
  color: t.textMuted,               // #5a5d8a
  letterSpacing: '0.03em',
  textTransform: 'uppercase',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
}
```

---

### 7. Contrast audit

| Element | Foreground | Background | Contrast | WCAG AA (3:1 for UI) |
|---|---|---|---|---|
| Active label | `#e2e3f0` | `#0e0e1a` | ~14.5:1 | Pass |
| Completed/Pending label | `#5a5d8a` | `#0e0e1a` | ~3.3:1 | Pass (borderline — do not reduce further) |
| Completed dot | `#16A34A` fill | `#0e0e1a` | ~4.1:1 | Pass |
| Active dot border | `#06B6D4` | `#0e0e1a` | ~5.2:1 | Pass |
| Rail done segment | `#16A34A` | `#0e0e1a` | ~4.1:1 | Pass |
| Rail pending segment | `#343452` | `#0e0e1a` | ~1.9:1 | Intentionally low — decorative connector |
| Count indicator | `#5a5d8a` | `#0e0e1a` | ~3.3:1 | Pass |

The pending rail segment deliberately uses low contrast (`bgSurface1`) — it is a structural connector, not a data signal. A bright pending rail would compete with completed state encoding.

---

### 8. Animation

#### Entrance animation — active dot on state change

When the active state changes (new state becomes active), apply a 2-cycle pulse to the new active dot. Base state = no animation. Motion gated by `prefers-reduced-motion`.

CSS to inject once via `styleInjectedRef`:

```css
@keyframes pathly-dot-arrive-v2 {
  0%, 100% { box-shadow: inset 0 0 0 4px #06B6D4; }
  50%       { box-shadow: inset 0 0 0 4px rgba(6,182,212,0.25); }
}

.pathly-stepper-active { /* base: no animation */ }

@media (prefers-reduced-motion: no-preference) {
  .pathly-stepper-active {
    animation: pathly-dot-arrive-v2 500ms ease-in-out 2;
  }
}
```

Apply the class to the active dot div on mount and on each state transition. Remove the class after `animationend` fires so the next state transition re-triggers the entrance.

```tsx
const dotRef = useRef<HTMLDivElement>(null)

useEffect(() => {
  const el = dotRef.current
  if (!el || status !== 'active') return
  el.classList.add('pathly-stepper-active')
  const onEnd = () => el.classList.remove('pathly-stepper-active')
  el.addEventListener('animationend', onEnd, { once: true })
  return () => el.removeEventListener('animationend', onEnd)
}, [currentState, status])
```

#### No sliding marker

The vertical layout has no sliding horizontal marker. The active dot's ring-with-fill is the sole active state indicator. This eliminates the flash-at-position-0 bug and the double-dot overlap from the horizontal design.

#### Reduced-motion fallback

When `prefers-reduced-motion: reduce` is active: the dot renders in its static ring-with-fill state immediately with no animation. No opacity crossfade, no transition — the ring appearance change itself is the transition.

---

### 9. React component — complete inline-style snippet

```tsx
// PipelineRailV2.tsx
// Drop-in replacement for the horizontal FSM rail section of FsmView.tsx
// Uses inline styles only. No CSS modules.

import React, { useEffect, useRef } from 'react'

const COMPLETED_GREEN = '#16A34A'
const ACTIVE_CYAN     = '#06B6D4'

// Inject animation CSS once
let styleInjected = false
function injectStyles() {
  if (styleInjected || typeof document === 'undefined') return
  styleInjected = true
  const el = document.createElement('style')
  el.textContent = `
    @keyframes pathly-dot-arrive-v2 {
      0%, 100% { box-shadow: inset 0 0 0 4px #06B6D4; }
      50%       { box-shadow: inset 0 0 0 4px rgba(6,182,212,0.25); }
    }
    .pathly-stepper-active {}
    @media (prefers-reduced-motion: no-preference) {
      .pathly-stepper-active {
        animation: pathly-dot-arrive-v2 500ms ease-in-out 2;
      }
    }
  `
  document.head.appendChild(el)
}

type StepStatus = 'completed' | 'active' | 'pending'

interface StepDotProps {
  status: StepStatus
  isCurrentActive: boolean
  currentState: string
}

function StepDot({ status, isCurrentActive, currentState }: StepDotProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || status !== 'active') return
    el.classList.add('pathly-stepper-active')
    const onEnd = () => el.classList.remove('pathly-stepper-active')
    el.addEventListener('animationend', onEnd, { once: true })
    return () => el.removeEventListener('animationend', onEnd)
  }, [currentState, status])

  const baseStyle: React.CSSProperties = {
    width: 16,
    height: 16,
    borderRadius: '50%',
    flexShrink: 0,
    position: 'relative',
    zIndex: 1,
  }

  const dotStyle: React.CSSProperties =
    status === 'completed'
      ? { ...baseStyle, backgroundColor: COMPLETED_GREEN, border: 'none' }
      : status === 'active'
      ? {
          ...baseStyle,
          backgroundColor: 'transparent',
          border: `2px solid ${ACTIVE_CYAN}`,
          boxShadow: `inset 0 0 0 4px ${ACTIVE_CYAN}`,
        }
      : {
          ...baseStyle,
          backgroundColor: 'transparent',
          border: '1px solid #5a5d8a',
        }

  return <div ref={ref} style={dotStyle} />
}

interface PipelineRailV2Props {
  states: string[]              // pipeline state names, already normalized (no leading dashes)
  currentState: string          // active state name
  convNum: number
  isDebugOrExplore?: boolean
  theme: {
    textPrimary: string
    textMuted: string
    bgSurface1: string
    fontFamilyMono: string
  }
}

export function PipelineRailV2({
  states,
  currentState,
  convNum,
  isDebugOrExplore = false,
  theme: t,
}: PipelineRailV2Props) {
  useEffect(() => { injectStyles() }, [])

  // Normalize state names defensively (strip YAML list dash prefix if present)
  const PIPELINE = states.map((s) => s.replace(/^[-\s]+/, '').trim())

  const activeIdx = PIPELINE.indexOf(currentState)
  const doneCount = activeIdx >= 0 ? activeIdx : 0
  const remainingCount = activeIdx >= 0 ? PIPELINE.length - activeIdx - 1 : PIPELINE.length
  const convLabel = isDebugOrExplore ? 'cycle' : 'conv'

  // Rail line geometry
  const ROW_HEIGHT = 28        // px — must match step row height
  const DOT_CENTER = 14        // ROW_HEIGHT / 2 — vertical center of dot within row
  const totalStates = PIPELINE.length
  const railTop = DOT_CENTER   // center-y of first dot relative to ol top
  const splitY = activeIdx >= 0 ? activeIdx * ROW_HEIGHT + DOT_CENTER : DOT_CENTER
  const railBottom = (totalStates - 1) * ROW_HEIGHT + DOT_CENTER
  const showCompletedSegment = activeIdx > 0
  const showPendingSegment = activeIdx >= 0 && activeIdx < totalStates - 1

  const railLineBase: React.CSSProperties = {
    position: 'absolute',
    left: '19px',   // container paddingLeft(12) + dotRadius(8) - halfLineWidth(1) = 19px
    width: '2px',
    borderRadius: '1px',
    pointerEvents: 'none',
    zIndex: 0,
  }

  return (
    <div
      role="group"
      aria-label={`Pipeline progress: ${currentState} — step ${activeIdx + 1} of ${totalStates}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        padding: '8px 12px 12px 12px',
      }}
    >
      {/* Conv/count indicator */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={{
          fontSize: '11px',
          fontFamily: t.fontFamilyMono,
          color: t.textMuted,
          letterSpacing: '0.02em',
          marginBottom: '8px',
          paddingLeft: '20px',
          whiteSpace: 'nowrap',
        }}
      >
        {convLabel} {convNum} · {doneCount} done · {remainingCount} remaining
      </div>

      {/* Step list with rail lines */}
      <ol
        role="list"
        aria-label="Pipeline states"
        style={{ listStyle: 'none', margin: 0, padding: 0, position: 'relative' }}
      >
        {/* Completed rail segment */}
        {showCompletedSegment && (
          <div
            aria-hidden="true"
            style={{
              ...railLineBase,
              top: `${railTop}px`,
              height: `${splitY - railTop}px`,
              backgroundColor: COMPLETED_GREEN,
            }}
          />
        )}

        {/* Pending rail segment */}
        {showPendingSegment && (
          <div
            aria-hidden="true"
            style={{
              ...railLineBase,
              top: `${splitY}px`,
              height: `${railBottom - splitY}px`,
              backgroundColor: t.bgSurface1,
            }}
          />
        )}

        {/* Step rows */}
        {PIPELINE.map((state, idx) => {
          const status: StepStatus =
            idx < activeIdx
              ? 'completed'
              : idx === activeIdx
              ? 'active'
              : 'pending'

          const labelStyle: React.CSSProperties =
            status === 'active'
              ? {
                  fontSize: '12px',
                  fontFamily: t.fontFamilyMono,
                  fontWeight: 600,
                  color: t.textPrimary,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }
              : {
                  fontSize: '11px',
                  fontFamily: t.fontFamilyMono,
                  fontWeight: 400,
                  color: t.textMuted,
                  letterSpacing: '0.03em',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }

          return (
            <li
              key={state}
              aria-label={`${state}: ${status}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                height: `${ROW_HEIGHT}px`,
                position: 'relative',
                zIndex: 1,
              }}
            >
              <StepDot
                status={status}
                isCurrentActive={status === 'active'}
                currentState={currentState}
              />
              <span style={labelStyle}>{state}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
```

---

### 10. Accessibility requirements

| Requirement | Implementation |
|---|---|
| Group label announced on focus entry | `role="group"` with `aria-label` on outer div |
| Each step's status announced | `aria-label="{state}: completed/active/pending"` on `<li>` |
| Count indicator updates announced | `aria-live="polite" aria-atomic="true"` on count div |
| Rail line segments hidden from SR | `aria-hidden="true"` on both segment divs |
| Dot divs hidden from SR | Screen reader uses `<li>`'s aria-label; dot div has no aria role |
| Focus ring on outer group | Outer div does not receive focus — it is not interactive. No focus ring needed. |
| Color-alone prohibition (WCAG 1.4.1) | Status communicated via shape AND color: solid fill (completed), ring+fill (active), hollow (pending) |
| Minimum touch target | Dots are 16px — below the 44px touch target minimum. The step row is 28px tall. This component is sidebar-only (pointer input). If a mobile breakpoint is added later, increase dot to 24px and row to 44px. |
| prefers-reduced-motion | Animation CSS gated behind `@media (prefers-reduced-motion: no-preference)`. Base state = static ring appearance. |

---

### 11. What is removed from V1

| V1 element | V2 decision |
|---|---|
| Horizontal flex dot row | Removed. Replaced by vertical `<ol>` list. |
| Absolutely-positioned sliding marker | Removed. Ring-with-fill dot is the sole active indicator. |
| `useLayoutEffect` + `ResizeObserver` for marker position | Removed. No marker means no position calculation. |
| `dotOffsetPx` state | Removed. |
| `dotReady` gate | Removed. Rail line geometry is pure arithmetic from `ROW_HEIGHT` constant — no DOM measurement needed. |
| `pathly-dot-arrive` keyframe (horizontal) | Removed. Replaced by `pathly-dot-arrive-v2` (inset box-shadow pulse). |
| Labels centered below dots | Removed. Labels are inline-right of dots. |
| `maxWidth: 64px` label truncation | Removed. Labels now have 140–240px horizontal room. |
| Compact mode (label hidden for >6 states) | Removed. Every state always shows its label. |
| Percentage-based rail line segments | Removed. Replaced by `ROW_HEIGHT`-based pixel arithmetic. |

---

### 12. Integration checklist for the builder

- [ ] Remove the existing `<div role="progressbar">` horizontal rail section from `FsmView.tsx`
- [ ] Remove the `useLayoutEffect` + `ResizeObserver` block that computed `dotOffsetPx`
- [ ] Remove `dotReady` and `dotOffsetPx` state declarations
- [ ] Remove the sliding marker element
- [ ] Remove the `pathly-dot-arrive` keyframe from the injected CSS block (keep `pathly-pulse`, `pathly-pulse-border`)
- [ ] Import and render `<PipelineRailV2>` in the position the old rail occupied
- [ ] Pass `states={PIPELINE}` where `PIPELINE` already has the dash-normalizer applied (`.map(s => s.replace(/^[-\s]+/, '').trim())`)
- [ ] Pass `currentState={fsmState.current}` (the raw store value — component normalizes internally)
- [ ] Pass `convNum`, `isDebugOrExplore`, and the required `theme` subset
- [ ] Verify `ROW_HEIGHT = 28` still produces a non-scrolling list at 8 states: `8 * 28 = 224px` — fits in a typical monitor panel height without overflow
- [ ] If the monitor panel is shorter than 224px, add `overflowY: 'auto'` to the outer container and verify rail line segments still render correctly (they are absolute inside the `<ol>`, which remains `position: 'relative'`)
