# Design Review — FSM Pipeline Rail (FsmView.tsx)

> Feature: studio-monitor-live · Phase 1
> Component: `studio/src/renderer/src/components/Monitor/FsmView.tsx`
> Reviewed: 2026-05-20
> Verdict: FAIL — 4 bugs requiring code fixes before ship

---

## Issues

| # | Rule | Location | Severity |
|---|---|---|---|
| 1 | STORMING label renders as "- STORMING" — leading dash visible | `convLabel` logic, line 251 | Critical |
| 2 | Double-dot on active state — sliding marker and active ring dot both visible simultaneously | Lines 362–448 | Critical |
| 3 | `COMPLETED_GREEN` uses rgba alpha — fails WCAG AA contrast on dark bg | Line 8 | Major |
| 4 | Active dot ring math is unsatisfiable — `border: 2px` + `boxShadow: inset 0 0 0 3px` on a 10px element overflows | Lines 378–382 | Major |
| 5 | Label truncation with `maxWidth: 64px` — inadequate for 8-state rail on narrow monitor panel | Lines 415–421 | Minor |
| 6 | Rail line segments use percentage width against container that includes 16px horizontal padding on each side — done segment bleeds past first dot | Lines 319–349 | Minor |

---

## Issue Analysis

### Issue 1 — STORMING label shows "- STORMING" (Critical)

**Root cause:** Line 251 reads:
```ts
const convLabel = isDebugOrExplore ? 'cycle' : 'conv'
```
This assigns `convLabel` correctly, but the rendered label in the state name row (`{state}`) is the raw pipeline state string, not `convLabel`. The leading dash is coming from `t.transitionBase` being concatenated somewhere else, OR — more likely — `pipelineStates` is being populated from the store with a value that already contains `"- STORMING"` as a string (e.g. from a YAML parser that renders a list item `- STORMING` without stripping the dash).

**Confirmed path:** The `PIPELINE` fallback on line 170–172 uses clean string literals. If `pipelineStates` from the store is populated by parsing a YAML sequence like:
```yaml
states:
  - STORMING
  - PLANNING
```
...and the parser returns `['- STORMING', '- PLANNING', ...]` (raw YAML scalar with dash prefix), the dash renders verbatim as the label text AND as the `aria-label`.

**Fix:** Strip leading `"- "` from every pipeline state string at the point of consumption. Add a normalizer when reading from the store:

```ts
// Line 169 — replace:
const PIPELINE = pipelineStates.length > 0
  ? pipelineStates
  : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']

// With:
const PIPELINE = (pipelineStates.length > 0 ? pipelineStates : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE'])
  .map((s) => s.replace(/^[-\s]+/, '').trim())
```

This is a defensive strip — it costs nothing if the data is already clean, and it fixes both the label display and the `PIPELINE.indexOf()` failure detection logic which would also be broken by the dash prefix.

---

### Issue 2 — Double dot at active state (Critical)

**Root cause:** Two independent elements are rendered at the same position:

1. The **static active dot** (lines 374–382) — a 10px circle with `border: 2px solid ACTIVE_CYAN` and `boxShadow: inset 0 0 0 3px ACTIVE_CYAN`, rendered as part of the flex row of state dots. It has `zIndex: 1` (via the parent wrapper on line 358).

2. The **sliding marker** (lines 431–448) — a 12px solid ACTIVE_CYAN circle, absolutely positioned with `zIndex: 2`.

Both are visible. The sliding marker sits on top of the ring dot but does not cover it fully because:
- Sliding marker: 12px solid cyan circle
- Ring dot: 10px with 2px cyan border + inset shadow = appears as 10px cyan ring with cyan inner fill

At `REVIEWING` (or any active state), the ring dot is rendered AND the sliding marker overlaps it — producing two visually distinct overlapping cyan shapes.

**Fix: Hide the static ring dot when it is the active state.** The sliding marker IS the active state indicator. The static dot for the active state should be replaced with a neutral pending-style dot so the sliding marker reads cleanly above it:

```ts
// Lines 362–390 — change isCurrent dot style:
// OLD:
: isCurrent
? {
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: 'transparent',
    border: `2px solid ${ACTIVE_CYAN}`,
    boxShadow: `inset 0 0 0 3px ${ACTIVE_CYAN}`,
    flexShrink: 0,
  }

// NEW:
: isCurrent
? {
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: 'transparent',
    border: `1px solid ${t.textMuted}`,  // neutral — sliding marker is the active signal
    flexShrink: 0,
  }
```

The sliding marker (12px solid cyan, `zIndex: 2`) provides the active indicator. The 10px ring beneath it serves as a neutral anchor point. The 2px size difference ensures the marker slightly overhangs, covering the ring while the marker is present.

**Alternative (if the pulse animation on the dot is required by spec):** Render the ring dot with `opacity: 0` on the active state and rely entirely on the sliding marker for the active signal. This is simpler and removes the overlap entirely:

```ts
: isCurrent
? {
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: 'transparent',
    border: `1px solid transparent`,
    flexShrink: 0,
    opacity: 0,  // hidden — sliding marker owns this position
  }
```

Recommended approach: use the `border: 1px solid t.textMuted` version (first option). Invisible dots create gaps in the flex row that can shift spacing. A neutral dot maintains layout stability.

---

### Issue 3 — COMPLETED_GREEN fails WCAG contrast (Major)

**Root cause:** Line 8 uses `rgba(22, 163, 74, 0.7)` — alpha-blended green on `bgBase=#0e0e1a`. The DESIGN.md spec explicitly flags this as a WCAG failure and requires the solid value.

**Actual rendered color:** `rgba(22,163,74,0.7)` on `#0e0e1a` composes to approximately `#106130` — a very dark green that falls below the 3:1 contrast ratio required for non-text UI elements (WCAG 1.4.11).

**Fix:** Line 8 — replace with the solid value specified in DESIGN.md §2:

```ts
// OLD:
const COMPLETED_GREEN = 'rgba(22, 163, 74, 0.7)'

// NEW:
const COMPLETED_GREEN = '#16A34A'
// Intentionally not t.green (#4ade80 — lime) and not rgba — alpha-blended version fails WCAG 3:1 on dark bg
```

`#16A34A` on `#0e0e1a` achieves approximately 4.1:1 contrast — passes WCAG AA for UI components.

---

### Issue 4 — Active dot ring math produces visual artifact (Major)

**Root cause:** The active dot style (lines 378–382) applies:
- `width: 10, height: 10`
- `border: 2px solid ACTIVE_CYAN` — this ring consumes 2px on each side inward from the element boundary
- `boxShadow: inset 0 0 0 3px ACTIVE_CYAN` — this inset shadow draws 3px inward from the element boundary

The inset shadow (3px) is larger than the remaining inner space after the border (10px - 2*2px = 6px interior, so 3px shadow fills half the interior). On a 10px dot: the border takes up 4px of width (2px per side), leaving a 6px interior. The inset shadow at 3px spread fills a 6px-diameter inner circle — which appears as a solid filled circle inside the border ring, producing a bullseye effect rather than a clean filled circle.

Additionally, the spec intent from DESIGN.md §3 was to create a "ring with inner dot" for shape encoding, but since the sliding marker now serves as the active indicator (Issue 2 fix), the bullseye style on the underlying dot is doubly redundant.

**Fix:** With Issue 2 resolved (active static dot becomes a neutral muted ring), this style problem is eliminated. If the ring-with-inner-dot is retained as a fallback for reduced-motion contexts, use consistent math:

```ts
// Ring + inner dot on a 10px element — correct math:
// border: 1.5px → leaves 7px interior → inset shadow 2px → 3px center gap remains
{
  width: 10,
  height: 10,
  borderRadius: '50%',
  backgroundColor: 'transparent',
  border: `1.5px solid ${ACTIVE_CYAN}`,
  boxShadow: `inset 0 0 0 2px ${ACTIVE_CYAN}`,  // fills inner 6px leaving 1px gap ring
  flexShrink: 0,
}
```

For a 10px element: 10px total − 3px (1.5×2 border) = 7px inner diameter. Inset 2px spread = 4px diameter center fill, leaving a 1.5px gap ring. This renders as a clean ring-with-center-dot at this size.

---

### Issue 5 — Label truncation at 8 states on narrow panels (Minor)

**Root cause:** `maxWidth: 64px` with 10px uppercase text and `letterSpacing: 0.05em`. Longest labels: STORMING (8 chars), DESIGNING (9 chars), REVIEWING (9 chars), BUILDING (8 chars). At 10px uppercase with Inter, approximately 7px per character (tracking-adjusted) — REVIEWING measures ~70px, DESIGNING ~73px. Both exceed `maxWidth: 64px` and will ellipsis-truncate to `REVIEWIN…` and `DESIGNIN…`.

The 8-state rail with 16px padding on each side:
- Available width per slot: `(containerWidth - 32px) / 8`
- At a typical 280px monitor panel: `(280 - 32) / 8 = 31px per slot`
- Labels are centered and overflow clipped — a 64px maxWidth means labels visually exceed their allocated slot and overlap neighbors

**Fix:** Two-part solution:

**Part A — Reduce font to 9px and tighten tracking:**
```ts
fontSize: '9px',
letterSpacing: '0.03em',
```
At 9px, REVIEWING measures approximately 59px — fits within 64px without truncation.

**Part B — Implement the compact mode already specified in DESIGN.md §3:**
```ts
// When pipelineStates.length > 6, only show active label; others are dots only
const showLabel = pipelineStates.length <= 6 || isCurrent
```
For 8-state pipelines, this eliminates the truncation problem entirely by only rendering the active state name (e.g. "REVIEWING") while all other dots are label-free. A centered count line below the rail reads: `"3 done · 4 remaining"` at 10px `t.textMuted`.

The compact mode is the correct fix at 8 states. Part A (9px font) is a band-aid for 6-state pipelines on narrower panels.

---

### Issue 6 — Rail line segment positioning bleeds past dot boundaries (Minor)

**Root cause:** Lines 319–349. The done segment is positioned:
```ts
left: '16px',
width: `${doneSegmentPct}%`,
```
The percentage is computed as `(activeIdx / (total-1)) * 100`. But this percentage is of the container's full width (including the 16px padding on each side). The rail dots are positioned in a flex row with `justifyContent: 'space-between'` — the first dot left edge is at `16px` and the last dot right edge is at `containerWidth - 16px`.

The done segment's right edge therefore extends past the center of the active dot — it reaches the percentage of the full container width, not the percentage of the dot-span width.

**Fix:** Rail lines should span from first dot center to last dot center, then be split at the active dot center. The span width is `containerWidth - 32px - 10px` (padding both sides minus the first dot width). The split point is `(activeIdx / (total-1)) * (containerWidth - 42px)`.

This is already how `dotOffsetPx` is computed (line 242: `15 + (activeIdx / (total - 1)) * (railWidth - 42)`). Apply the same formula to the line segments using absolute pixel positioning driven by `railWidth`:

```ts
// Replace percentage-based line segments with pixel-based:
// First dot center: railPadding + dotRadius = 16 + 5 = 21px
// Last dot center: railWidth - railPadding - dotRadius = railWidth - 21px
// Active dot center: dotOffsetPx + 6 (half of 12px sliding marker)

const lineStart = 21  // px from left of container
const lineEnd = railWidth - 21  // px from left of container
const lineSplit = dotOffsetPx + 6  // center of active sliding marker

// Done segment
{ left: lineStart, width: lineSplit - lineStart }

// Pending segment
{ left: lineSplit, width: lineEnd - lineSplit }
```

This requires `railWidth > 0` — already guarded by `dotReady` state. Show neither segment until `dotReady` is true.

---

## Recommendations

**Priority order — fix in this sequence:**

1. **Fix Issue 3 first** (5 min) — change the constant. No layout risk. Unblocks WCAG AA before anything else.

2. **Fix Issue 1 next** (10 min) — add the `.map(s => s.replace(/^[-\s]+/, '').trim())` normalizer. No visual change if data is already clean; fixes the visible bug if data has dashes.

3. **Fix Issue 2** (15 min) — change the active dot style to `border: 1px solid t.textMuted` (neutral). The sliding marker takes over as the sole active indicator. Verify visually that the 12px marker is centered over the 10px neutral dot.

4. **Fix Issue 4** (resolved by Issue 2 fix — no additional code needed unless ring-dot is retained for reduced-motion fallback).

5. **Fix Issue 6** (20 min) — switch rail line segments from percentage to pixel math using `railWidth`. Gated behind `dotReady` already.

6. **Fix Issue 5 last** (30 min) — implement the compact mode (labels only for active state when `pipelineStates.length > 6`). This is additive new behavior, lower risk, lower urgency than the above.

---

## Before / After Sketch

### BEFORE — Current broken state (REVIEWING active, 8-state rail)

```
Container width: 280px
Padding: 16px each side

             ← 16px →                                               ← 16px →
             |                                                       |
[dot][dot][dot][dot][CYANring+CYANfill][dot][dot][dot]   ← static dots
                         ↑
                   (cyan ring with cyan inset fill — bullseye)
                   (12px cyan marker ALSO here — two cyan shapes overlap)

Rail line: done segment % of FULL container width — bleeds ~4px past dots

Labels (10px uppercase):
STORM- | PLANN- | DESIGN- | BUILD- | REVIEWIN… | TESTIN… | RETRO | DONE
                                        ↑ truncated                ↑ truncated

First label: "- STORMING" (dash visible, overflows container left)
```

### AFTER — Fixed state

```
Container width: 280px
Padding: 16px each side
Rail line: pixel-math, dot-center to dot-center

             ← 21px center of first dot →                ← 21px from right edge →
             |                                                       |
[grn][grn][grn][grn][ neu ][ neu ][ neu ][ neu ]   ← static dots
                        ↑
                   neutral muted ring (10px, 1px border textMuted)
                        ↑
                   12px solid cyan sliding marker (zIndex: 2) — single active indicator
                   no double-dot

Rail line: done (green, pixel-exact) ──────── | ──── pending (bgSurface1)
           left: 21px              split at    right: railWidth - 21px
                                   active dot center

Labels (compact mode, 8 states):
  ○  ○  ○  ○  ●  ○  ○  ○        ← dots only for non-active states
               REVIEWING         ← label only for active state (centered, 10px)
                  ↑
           3 done · 4 remaining  ← count line below rail, t.textMuted, 10px, centered

No dash prefix. No truncation. No double dot.
```

### Dot state legend (after fix)

```
Completed:  ● solid #16A34A (10px)
Active:     ○ 1px border t.textMuted (10px) + 12px cyan sliding marker above (zIndex:2)
Pending:    ○ 1px border t.textMuted (10px)
```

The completed dot and the pending/active dot are visually distinct: filled green vs hollow muted ring. The sliding marker at `zIndex: 2` makes the active position unambiguous without needing a separate ring style on the static dot.

---

## Inline Style Snippets (React, copy-ready)

### Corrected COMPLETED_GREEN constant
```ts
const COMPLETED_GREEN = '#16A34A'
```

### Corrected pipeline state normalizer
```ts
const PIPELINE = (pipelineStates.length > 0
  ? pipelineStates
  : ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']
).map((s) => s.replace(/^[-\s]+/, '').trim())
```

### Corrected active dot style (static — neutral, not bullseye)
```ts
// isCurrent dot — neutral ring, sliding marker owns the active signal
{
  width: 10,
  height: 10,
  borderRadius: '50%',
  backgroundColor: 'transparent',
  border: `1px solid ${t.textMuted}`,
  flexShrink: 0,
}
```

### Corrected rail line segments (pixel math)
```ts
// Requires: railWidth > 0 and dotReady === true
const lineStart = 21  // first dot center (16px padding + 5px dot radius)
const lineEnd = railWidth - 21  // last dot center from left
const activeDotCenter = dotOffsetPx + 6  // center of 12px sliding marker

// Done segment (only render when activeIdx > 0)
{
  position: 'absolute',
  top: '50%',
  left: `${lineStart}px`,
  width: `${activeDotCenter - lineStart}px`,
  height: '2px',
  borderRadius: '1px',
  backgroundColor: COMPLETED_GREEN,
  transform: 'translateY(-50%)',
  pointerEvents: 'none',
}

// Pending segment
{
  position: 'absolute',
  top: '50%',
  left: `${activeDotCenter}px`,
  width: `${lineEnd - activeDotCenter}px`,
  height: '2px',
  borderRadius: '1px',
  backgroundColor: t.bgSurface1,
  transform: 'translateY(-50%)',
  pointerEvents: 'none',
}
```

### Compact mode label rendering
```ts
// Add above the label div in the PIPELINE.map:
const showLabel = PIPELINE.length <= 6 || isCurrent

// Wrap label in conditional:
{showLabel && (
  <div style={{
    fontSize: '10px',
    fontFamily: t.fontFamilyBase,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginTop: '6px',
    textAlign: 'center',
    maxWidth: '64px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    color: labelColor,
    fontWeight: isCurrent ? 600 : 400,
  }}>
    {state}
  </div>
)}

// Add below the dot row, when PIPELINE.length > 6:
{PIPELINE.length > 6 && activeIdx >= 0 && (
  <div style={{
    fontSize: '10px',
    color: t.textMuted,
    textAlign: 'center',
    marginTop: '4px',
    letterSpacing: '0.02em',
  }}>
    {activeIdx} done · {PIPELINE.length - activeIdx - 1} remaining
  </div>
)}
```

---

## Verdict

FAIL

4 issues require code changes before this component ships:
- Issue 1 (dash prefix) — data normalization bug, visible to all users
- Issue 2 (double dot) — overlapping indicators, visual regression vs spec
- Issue 3 (rgba green) — WCAG AA contrast failure
- Issue 4 (ring math) — resolved by Issue 2 fix

Issues 5 and 6 are pre-ship recommended but not blockers for a narrow panel at 6 states or fewer.
