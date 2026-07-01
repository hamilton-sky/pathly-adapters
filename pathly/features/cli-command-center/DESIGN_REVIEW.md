# Design Review — CLI Command Center (CliMonitorBar)

> UI/UX pass · Stack: Electron/React · 2026-07-01

---

## Diagnosis: the three-altitude problem

The panel currently stacks four sections vertically with no visual weight
distinction between them:

```
┌─────────────────────────────────┐  ← header  (drag / counts)
│ FLOW        [buttons wrapping]  │  ← altitude 1: primary action
│ CODE INTELLIGENCE [toggles]     │  ← altitude 2: configuration
│ QUEUE (n) / limits              │  ← altitude 3: infra management
│ ACTIVE    [session rows]        │  ← altitude 3: live monitoring
│ RECENT    [history rows]        │
└─────────────────────────────────┘
```

Every section uses the same `sectionLabel` style (9px / 700 / uppercase /
`var(--text-muted)`), the same 4px body padding, and the same border
treatment. Nothing tells the eye what to focus on first. The result: a
dense column of equally-weighted controls inside 288px.

The fix is to treat information altitude as a visual axis:
- Altitude 1 (Flow) → primary chrome, always visible, highest contrast
- Altitude 2 (Code Intel) → collapsed by default, revealed on demand
- Altitude 3 (Queue + Engines) → monitoring tier, fills remaining space

---

## Violations

| # | Rule | Location | Severity |
|---|---|---|---|
| V1 | No visual hierarchy between primary actions and configuration settings | `CliMonitorBar.tsx` — body stack order | Critical |
| V2 | `width: 288px` hard-codes panel size; does not widen for expanded state | `CliMonitorBar.module.css:7` | High |
| V3 | `max-height: 340px` clips engine rows when queue + sessions both present | `CliMonitorBar.module.css:107` | High |
| V4 | CODE INTELLIGENCE sits between FLOW (primary) and engines (live) — breaks logical order | `CliMonitorBar.tsx:129` | High |
| V5 | Flow button row wraps unpredictably at 288px; no grouping cues beyond the `sep` dividers | `FlowControlBar.module.css` `.bar` wraps at `flex-wrap: wrap` | Medium |
| V6 | Header title "CLI Engines" no longer describes the panel contents (flow + code intel + engines) | `CliMonitorBar.tsx:113` | Medium |
| V7 | `flowSection` only adds `padding-top: 4px`; no bottom separator or breathing room | `CliMonitorBar.module.css:18` | Medium |
| V8 | `sectionLabel` used for both structural section headers (FLOW, ACTIVE) and sub-panel headers (QUEUE) — overloaded style | `CliMonitorBar.module.css:220` | Medium |
| V9 | CODE INTELLIGENCE row squeezes Backend + Re-index + two field labels into one 288px flex row | `CodeIntelControl.module.css` `.row` | Medium |
| V10 | Body `padding: 4px` is uniform; no per-section inset that distinguishes settings from monitoring | `CliMonitorBar.module.css:105` | Low |

---

## Near-term refinement spec (implementable now)

### 1. Panel width: 320px

Change `CliMonitorBar.module.css` line 7 from `width: 288px` to `width: 320px`.
This gives the flow button row 32 extra px — enough to prevent wrap on the
primary lifecycle group (Start / Pause / Resume) and gives Code Intel room
to lay out its two rows without crowding.

### 2. Body max-height: 480px

Change `CliMonitorBar.module.css` line 107 from `max-height: 340px` to
`max-height: 480px`. When queue + multiple active sessions are present,
340px clips the engine rows below the fold. 480px covers 3–4 active sessions
plus the queue before requiring scroll.

### 3. Header rename: "Command Center"

`CliMonitorBar.tsx` line 113: change `CLI Engines` to `Command Center`. The
panel now owns flow control, code intel, and engine monitoring. The title
should match.

### 4. Section visual hierarchy — three bands

Introduce two new CSS classes to distinguish section tier:

```
.sectionLabelPrimary   — FLOW: slightly more prominent
.sectionLabelMeta      — CODE INTELLIGENCE: de-emphasized, used for collapsible
.sectionLabel          — ACTIVE / RECENT / QUEUE: unchanged (current style is correct here)
```

**sectionLabelPrimary** (add to `CliMonitorBar.module.css`):
```css
.sectionLabelPrimary {
  padding: 6px 8px 2px;
  font-size: var(--font-size-xs);   /* 10px */
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.06em;
  color: var(--text-secondary);     /* one step brighter than --text-muted */
  text-transform: uppercase;
  border-top: var(--border-subtle);
}
```

**sectionLabelMeta** (used for the collapsible CODE INTELLIGENCE toggle):
```css
.sectionLabelMeta {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: var(--font-size-xs);   /* 10px */
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.06em;
  color: var(--text-muted);
  text-transform: uppercase;
  cursor: pointer;
  border-top: var(--border-subtle);
  user-select: none;
  transition: color var(--transition-fast);
}
.sectionLabelMeta:hover {
  color: var(--text-secondary);
}
.sectionLabelMeta .chevron {
  margin-left: auto;
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}
.sectionLabelMeta.open .chevron {
  transform: rotate(180deg);
}
```

### 5. Section order (new render order in CliMonitorBar.tsx)

```
header                           (drag / counts / close)
─────────────────────────────────
FLOW section        [primary]    always visible, sectionLabelPrimary
FlowControlBar
─────────────────────────────────
CODE INTELLIGENCE   [meta]       collapsed by default, sectionLabelMeta + chevron
CodeIntelControl                 renders only when expanded
─────────────────────────────────
rate-limit banner                conditional
SpawnQueuePanel                  (includes QUEUE label internally)
─────────────────────────────────
ACTIVE              [sectionLabel]
session rows
─────────────────────────────────
RECENT              [sectionLabel]
history rows
```

Add a `codeIntelOpen` boolean to `useCliMonitor` (default `false`).
The CODE INTELLIGENCE row becomes a `<button>` that toggles this state.

### 6. Flow button row — grouping and widths

The `FlowControlBar` `.bar` currently relies only on `sep` dividers to
communicate grouping. At 320px those dividers remain. No new groups are needed
but the buttons need slightly wider touch targets:

Change `FlowControlBar.module.css` `.btn`:
```css
.btn {
  width: 30px;   /* was 28px */
  height: 26px;  /* was 24px — meets 24px minimum, now comfortably 26px */
}
```

Active state for the mode toggle is already defined (`btnModeInteractive`).
No structural change needed — just the width/height bump.

Disabled buttons must be visually clear. Add to `FlowControlBar.module.css`:
```css
.btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
}
```
(Currently `btnDisabled` class exists but it applies `cursor: not-allowed`
only when the class is added manually. Prefer `:disabled` pseudo-class so
the rule fires unconditionally when `disabled` attribute is set.)

### 7. Code Intel layout — split into two rows with clear labels

Current: Backend toggle + Re-index segmented control crammed into one flex
row at 288px. At 320px there is still not enough room for four flex items
plus their gap.

Recommended layout for `CodeIntelControl` (no new component needed, just
restructure the two existing `.row` divs):

```
Row 1:  [Backend label]  [toggle]   ←→ gap →   [Auto-commit label]  [toggle]
Row 2:  [Re-index label]  [Off] [Stage] [Auto]
```

Row 1 uses `justify-content: space-between` to push the two toggle pairs
to opposite ends. Row 2 runs full-width with the segmented control taking
the remaining space.

CSS change in `CodeIntelControl.module.css`:
```css
.rowPrimary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  gap: 8px;
  min-width: 0;
}

.rowSecondary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px 6px;
  min-width: 0;
}

.rowSecondary .segmented {
  flex: 1;
  min-width: 0;
  justify-content: flex-end;
}

.rowSecondary .segBtn {
  flex: 1;       /* distribute evenly across the three options */
  min-width: 0;
  text-align: center;
}
```

### 8. Spacing scale — bring body padding in line with token scale

`CliMonitorBar.module.css` `.body`: change `padding: 4px` to `padding: var(--space-2) var(--space-1)` (4px 2px). The horizontal padding of 4px was already producing double-margin with row items that have their own `padding: 5px 6px`. Reducing horizontal body padding to 2px gives row items a flush-left optical anchor while keeping vertical rhythm.

### 9. FlowSection bottom border

Add to `CliMonitorBar.module.css`:
```css
.flowSection {
  padding-top: var(--space-2);       /* was 4px, same value, use token */
  border-bottom: var(--border-subtle);  /* add — visually caps the primary zone */
}
```

---

## Token reference table

| Token | Value (dark) | Used for |
|---|---|---|
| `--bg-mantle` | `#0B0F1A` | Panel background |
| `--bg-surface0` | `#1E2433` | Section headers, row hover |
| `--bg-surface1` | `#283044` | Raised element backgrounds |
| `--bg-base` | `#111827` | Expanded detail well |
| `--text-primary` | `#E2E8F0` | Interactive labels |
| `--text-secondary` | `#A8BBCC` | Row labels, section primary |
| `--text-muted` | `#8899B0` | Section meta, badges, time-ago |
| `--accent` | `#38BDF8` | Active states, Start button |
| `--green` | `#34D399` | Done status, codex badge |
| `--orange` | `#f97316` | Decision cluster (Advance/Reroute/Retry) |
| `--red` | `#f87171` | Stop / abort / error |
| `--border` | `1px solid #283044` | Section separators |
| `--border-subtle` | `1px solid #1E2433` | Inner section dividers |
| `--font-size-xs` | `10px` | Section labels |
| `--font-size-sm` | `11px` | Row labels, elapsed times |
| `--font-weight-semibold` | `600` | Primary section labels |
| `--font-weight-medium` | `500` | Meta section labels |
| `--font-weight-bold` | `700` | Counts, badges |
| `--space-2` | `4px` | Body padding |
| `--space-3` | `6px` | Row gap |
| `--space-4` | `8px` | Section label horizontal padding |
| `--radius-sm` | `4px` | Row hover, badge |
| `--radius-lg` | `8px` | Panel border-radius |
| `--transition-fast` | `100ms ease-out` | All interactive transitions |

---

## Ordered build list (near-term)

1. **Panel width + max-height** — `CliMonitorBar.module.css` lines 7, 107. Two property changes, no logic.
2. **Header rename** — `CliMonitorBar.tsx` line 113: `"CLI Engines"` → `"Command Center"`.
3. **sectionLabelPrimary + sectionLabelMeta CSS** — add both classes to `CliMonitorBar.module.css`. No component change yet.
4. **Collapsible Code Intel** — add `codeIntelOpen` state to `useCliMonitor.ts` (default `false`). Update `CliMonitorBar.tsx` to render the CODE INTELLIGENCE label as a `<button>` using `.sectionLabelMeta` with a `ChevronDown` icon, and gate `<CodeIntelControl />` on `codeIntelOpen`.
5. **Section reorder** — in `CliMonitorBar.tsx` body: move `<CodeIntelControl />` after the flow section but before the queue/engine monitoring section. (Already the current order; confirm after step 4.)
6. **Code Intel row restructure** — split `.row` into `.rowPrimary` and `.rowSecondary` in `CodeIntelControl.module.css`; update `CodeIntelControl.tsx` to use them.
7. **FlowControlBar button sizing** — `FlowControlBar.module.css` `.btn`: width 28→30, height 24→26; add `:disabled` rule.
8. **FlowSection border-bottom** — `CliMonitorBar.module.css` `.flowSection`: add `border-bottom: var(--border-subtle)`.
9. **Body padding correction** — `CliMonitorBar.module.css` `.body`: `padding: 4px` → `padding: var(--space-2) var(--space-1)`.

Each step is independently shippable. Steps 1–3 are purely CSS/text changes with zero risk. Steps 4–6 require React logic changes. Steps 7–9 are CSS-only fixups.

---

## North-star: CLI Command Center modal (future scope)

### Concept

Clicking the panel header (or a dedicated "expand" chevron in the header)
transitions the compact 320px floating panel into a full-width modal overlay
— the **CLI Command Center** — that displays all spawned engine sessions and
all concurrent flows as styled cards on a dark canvas.

### Expand interaction

```
compact panel header → click "expand" icon (Maximize2 from lucide)
  → modal overlay appears (z-index 950)
  → panel fades/scales out (opacity 0, scale 0.98, 80ms)
  → modal fades/scales in (opacity 1, scale 1, 120ms, --ease-out)
  → clicking outside modal OR pressing Escape → reverse transition → compact panel returns
```

The Cpu topbar button still toggles visibility of the compact panel. When the
modal is open, the Cpu button keeps its active state and clicking it collapses
the modal back to the compact panel.

### Modal layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Command Center                               [compact] [close]  │  header strip
├─────────────────────┬───────────────────────────────────────────┤
│   FLOWS             │   ENGINES                                  │
│                     │                                            │
│  ┌──────────────┐   │  ┌─────────────┐  ┌─────────────┐        │
│  │ team.flow    │   │  │ claude      │  │ codex       │        │
│  │ ● running    │   │  │ builder     │  │ reviewer    │        │
│  │ stage: BUILD │   │  │ 2m 14s      │  │ 45s         │        │
│  │ [Pause][Adv] │   │  │ [stop] [↗]  │  │ [stop] [↗]  │        │
│  └──────────────┘   │  └─────────────┘  └─────────────┘        │
│                     │                                            │
│  ┌──────────────┐   │  ┌─────────────┐                          │
│  │ lint.flow    │   │  │ antigravity │                          │
│  │ ○ idle       │   │  │ queued #1   │                          │
│  │              │   │  │ tester      │                          │
│  │ [Start]      │   │  │ [cancel]    │                          │
│  └──────────────┘   │  └─────────────┘                          │
│                     │                                            │
│  CODE INTEL    ───  │  ┌──────────────────────────────────────┐ │
│  Backend  [on]      │  │ SPAWN LIMITS  total 8  headless 5    │ │
│  Re-index [auto]    │  │               chat  5  [edit]        │ │
│  Auto-commit [on]   │  └──────────────────────────────────────┘ │
└─────────────────────┴───────────────────────────────────────────┘
```

### Flow card spec

```
background:  var(--bg-surface0)
border:      var(--border)
border-radius: var(--radius-lg)
padding:     var(--space-4) var(--space-5)   [8px 10px]
min-width:   160px
gap between cards: var(--space-4)

Header row:
  [flow name — font-size-sm, semibold, text-primary]
  [status badge — data-status attr, matches RunnerStatus union]

Status badge tokens:
  running  → border: var(--accent); color: var(--accent)
  paused   → border: var(--yellow); color: var(--yellow)
  blocked  → border: var(--orange); color: var(--orange); animation: pulse 1.8s
  done     → border: var(--green);  color: var(--green)
  error    → border: var(--red);    color: var(--red)
  idle     → border: var(--border-color); color: var(--text-muted)

Body:
  stage row: font-size-xs, text-muted, "stage: BUILD"
  action buttons: same RunnerBtn component, renders Start/Pause/Resume/Advance
                  depending on status — reuses existing logic from FlowControlBar

Card height: auto (no fixed height); cards in a flow column wrap with gap
```

### Engine card spec

```
background:  var(--bg-surface0)
border:      var(--border)
border-radius: var(--radius-lg)
padding:     var(--space-4) var(--space-5)
width:       180px (fixed in modal; wider than compact row)

Header: [adapter badge] [tab label truncated]
Body:   elapsed time (tabular-nums, text-secondary) + last output line (font-mono, text-muted)
Footer: [stop button] [open-terminal button]

Adapter badge tokens: existing `.badge` + data-adapter styling — no change needed
Queued engines: opacity 0.6, "queued #N" label replaces elapsed time
```

### Component sharing strategy

The modal is a new component `CliCommandCenter` in a new folder:
```
components/CliCommandCenter/
  CliCommandCenter.tsx
  CliCommandCenter.module.css
  FlowCard/
    FlowCard.tsx
    FlowCard.module.css
  EngineCard/
    EngineCard.tsx
    EngineCard.module.css
```

`FlowCard` reuses `RunnerBtn` directly. `EngineCard` reuses the stop and
open-terminal logic from `SessionRow` (extract to a shared hook
`useSessionActions(tab)` inside the CliMonitorBar folder so both compact
and expanded views share the same kill/open logic).

The compact panel and the modal read from the same stores
(`useRunnerStore`, `useTerminalStore`, `useCliMonitor`). No new state is
needed. The only new state is `commandCenterOpen: boolean` in `uiStore`.

---

## Verdict

**FAIL — near-term refinement required before north-star work begins.**

The panel is functional but visually unranked. The nine-step build list
above resolves the critical hierarchy problem (V1), the size constraints
(V2, V3), and the layout density issues (V5, V9) without touching the
north-star modal. All nine steps are bounded to `CliMonitorBar/`,
`CodeIntelControl/`, and `FlowControlBar/` — no cross-cutting changes.

Estimated LOC change: ~60 lines CSS added/modified, ~20 lines TSX changed.
