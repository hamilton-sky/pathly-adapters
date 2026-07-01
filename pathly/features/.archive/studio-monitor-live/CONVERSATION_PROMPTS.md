# studio-monitor-live — Conversation Guide

Split into 2 conversations. Each produces runnable, typecheck-passing code.
After each conversation, **commit your changes** before starting the next.

> Read **DESIGN.md** before implementing any phase — it has every token value, color constant, spacing spec, animation spec, and accessibility requirement in one place.

---

## Conversation 1: Rail, Trace & Live Badge (Phases 1–3)

**Stories delivered:** S1, S2, S3

**Prompt to paste:**
```
Implement studio-monitor-live Conversation 1 (Phases 1–3).

Read these files before writing a single line of code:
1. pathly/plans/studio-monitor-live/IMPLEMENTATION_PLAN.md  (phases 1–3)
2. pathly/plans/studio-monitor-live/DESIGN.md               (all design specs)
3. pathly/plans/studio-monitor-live/EDGE_CASES.md           (EC-1.x and EC-2.x)
4. pathly/plans/studio-visual-flow-builder/MONITOR_DESIGN_SPEC.md  (Q3, Q5 for context)

Confirm every file path below exists before editing:
- studio/src/renderer/src/components/Monitor/FsmView.tsx
- studio/src/renderer/src/components/Monitor/index.tsx
- studio/src/renderer/src/theme.ts
- studio/src/renderer/src/store/projectStore.ts  (confirm monitorSource field + type)

────────────────────────────────────────────────
PHASE 1 — theme.ts + FSM topology rail
────────────────────────────────────────────────

Step A — theme.ts (do this first, it unblocks all other phases):
Add to Theme interface AND both darkTheme and lightTheme:
  runtime: string          → dark: '#22D3EE'   light: '#0EA5E9'
  fontFamilyMono: string   → both: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace"

Step B — FsmView.tsx: replace box-list layout with connected rail.

Color constants at module scope (do NOT use t.green):
  const COMPLETED_GREEN = 'rgba(22, 163, 74, 0.7)'
  // Intentionally not t.green — spec requires muted forest green, not lime (#4ade80)

Rail structure (see DESIGN.md §3 for exact CSS values):
  - 1px horizontal rail line: backgroundColor t.bgSurface1 (#343452), NOT bgSurface0
  - State dots: 10px circles, position: relative, z-index: 1 above rail line
  - Completed dot: COMPLETED_GREEN fill
  - Active dot: t.runtime fill + pathly-pulse class
  - Future dot: t.textMuted stroke (#5a5d8a), transparent fill — NOT bgSurface0 (too faint)
  - Sliding marker: separate absolutely positioned cyan circle, moves via
    transform: translateX(offsetPx) translateY(-50%)
    transition: reuse t.transitionBase ('150ms ease-out') — do NOT hardcode
  - Compute offsetPx from activeIdx, PIPELINE.length, measured rail width (useLayoutEffect + ResizeObserver)
  - One requestAnimationFrame on mount to avoid paint-before-transition

State labels:
  - 11px, t.textMuted, uppercase, textAlign: center, marginTop: 6px
  - Active label: t.textPrimary, fontWeight: 600
  - Completed label: COMPLETED_GREEN

conv/cycle label:
  - fsmState.flow === 'debug' || 'explore' → 'cycle N'
  - All other values including custom flow names → 'conv N'
  - Conv number: fsmState.conv ?? fsmState.current_conversation

Remove entirely: the "System active — STATE" status line.

PULSE_CSS injection — update the existing block to include prefers-reduced-motion:
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

For the sliding dot's transition, also check prefers-reduced-motion at runtime:
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  transition: reducedMotion ? 'none' : `transform ${t.transitionBase}`

────────────────────────────────────────────────
PHASE 2 — Execution trace below the rail
────────────────────────────────────────────────

CREATE Monitor/utils.ts with formatRelativeTime:
  export function formatRelativeTime(ts: string): string {
    const diffMs = Date.now() - new Date(ts).getTime()
    const diffS = Math.floor(diffMs / 1000)
    if (diffS < 60) return 'now'
    const diffM = Math.floor(diffS / 60)
    if (diffM < 60) return `${diffM}m ago`
    return `${Math.floor(diffM / 60)}h ago`
  }

Add execution trace section in FsmView.tsx below the rail:

Trace container (accessibility required):
  <div
    role="log"
    aria-label="Execution trace"
    aria-live="polite"
    aria-atomic={false}
  >

Build VisitRow[] from STATE_TRANSITION events (see IMPLEMENTATION_PLAN.md Phase 2 for full spec).
Sort VisitRows by ts before rendering (EC-1.1 guard — EVENTS.jsonl/SSE race).

FAILURE DETECTION — use pipelineStates order, NOT hardcoded state names:
  After STATE_TRANSITION to stateA, look at next STATE_TRANSITION's `to` field.
  If PIPELINE.indexOf(nextTo) < PIPELINE.indexOf(stateATo) → mark stateA visit as 'failed'.
  This works for any flow topology. Never hardcode 'FIXING', 'REVIEWING', or any state name.

Row typography:
  fontFamily: t.fontFamilyMono  (new token from Phase 1)
  fontSize: '12px'
  lineHeight: '1.7'
  whiteSpace: 'pre'

Row color map (see DESIGN.md §4):
  ✓ icon: COMPLETED_GREEN | ● icon: t.runtime (pulse) | ✗ icon: t.red
  State name active: t.textPrimary | State name done: t.textSecondary
  conv/cycle + agent + time: t.textMuted

Agent per row: first AGENT_SPAWNED with ts > stateTransition.ts → show agent; else show '—'.
Eventual consistency is acceptable (EC-1.2).

Empty state: "Waiting for flow activity." in t.textMuted, 13px, centered.

────────────────────────────────────────────────
PHASE 3 — SSE source badge
────────────────────────────────────────────────

In HeaderBar (Monitor/index.tsx):
  Read monitorSource via useStore(). Three states (EC-2.1):
    'sse'           → '● live'    color: t.runtime   fontSize: t.fontSizeSm (12px)
    'chokidar'      → '○ polling' color: t.textMuted fontSize: t.fontSizeSm
    null/other      → '—'         color: t.textMuted fontSize: t.fontSizeSm

Remove any existing 'Source: SSE live' or 'Source:' text from the header.
Place badge flush-right in the header title row.

────────────────────────────────────────────────
SCOPE CONSTRAINTS
────────────────────────────────────────────────
Do NOT touch: PlanBoard, FlowEditor, Sidebar, store state shape.
Do NOT add new IPC calls.
Do NOT fix the EVENTS.jsonl/SSE race (EC-1.1) — documented limitation.

Verify: cd studio; npm run typecheck
After done, update pathly/plans/studio-monitor-live/PROGRESS.md phases 1–3 to DONE.
If typecheck fails and fix requires out-of-scope changes, stop and report.
```

**Expected output:** theme.ts has `runtime` and `fontFamilyMono` tokens. Monitor shows connected rail with `COMPLETED_GREEN` dots, sliding `t.runtime` active dot, execution trace in mono font with `aria-live`, and `● live`/`○ polling`/`—` badge. All animations respect `prefers-reduced-motion`.

**Files touched:** `theme.ts`, `Monitor/FsmView.tsx`, `Monitor/index.tsx`, `Monitor/utils.ts` (new)

---

## Conversation 2: Tabs, Banner, Cards & Last-Used Flow (Phases 4–7)

**Stories delivered:** S4, S5, S6, S7

**Prompt to paste:**
```
Implement studio-monitor-live Conversation 2 (Phases 4–7).

Read these files before writing a single line of code:
1. pathly/plans/studio-monitor-live/IMPLEMENTATION_PLAN.md  (phases 4–7)
2. pathly/plans/studio-monitor-live/DESIGN.md               (all design specs — §6, §7, §8, §9)
3. pathly/plans/studio-monitor-live/EDGE_CASES.md           (EC-3.x and EC-4.x)
4. pathly/plans/studio-visual-flow-builder/MONITOR_DESIGN_SPEC.md  (Q2, Q4, Q6)

Confirm every file path below exists before editing:
- studio/src/renderer/src/store/uiStore.ts
- studio/src/renderer/src/components/Monitor/index.tsx
- studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx
- studio/src/renderer/src/components/FlowEditor/zIndex.ts  ← MUST exist; stop if missing
- studio/src/renderer/src/components/PlanBoard.tsx
- studio/src/renderer/src/types/index.ts
- studio/src/renderer/src/hooks/usePlanConversations.ts
- studio/src/renderer/src/App.tsx
- studio/src/renderer/src/components/Monitor/utils.ts  (formatRelativeTime from Conv 1)

────────────────────────────────────────────────
PHASE 4 — Multi-flow store + Monitor tabs + SSE re-key
────────────────────────────────────────────────

Add to uiStore.ts (see DESIGN.md §6 for interface):
  interface FlowSession {
    flowKey: string; topic: string; isRunning: boolean; isPaused: boolean; isCli: false
  }
  activeFlowSessions: Record<string, FlowSession>   // key = topic
  activeMonitorTab: string | null
  setters for both

Producer in Monitor/index.tsx useEffect — after STATE.json parsed, upsert:
  setActiveFlowSessions(prev => ({
    ...prev,
    [activeTopic]: {
      flowKey: `${parsedState.flow ?? 'team'}.flow.yaml`,
      topic: activeTopic,
      isRunning: parsedState.current !== 'IDLE' && parsedState.current !== 'DONE',
      isPaused: false,
      isCli: false as const
    }
  }))
Remove session on useEffect cleanup (delete activeTopic key from sessions).

Tab bar — show ONLY when Object.keys(activeFlowSessions).length >= 2 (DESIGN.md §6):
  Container: role="tablist", aria-label="Active flows", height: 32px
  Each tab: role="tab", aria-selected, tabIndex={isActive ? 0 : -1} (roving tabindex)
  Active tab: borderBottom: 2px solid t.runtime, color: t.textPrimary, backgroundColor: t.bgSurface0
  Inactive tab: color: t.textMuted, borderBottom: 2px solid transparent
  Running dot: <span className="pathly-pulse" aria-hidden="true">●</span> in t.runtime
  Keyboard: onKeyDown → ArrowRight/ArrowLeft to navigate, Enter/Space to select (DESIGN.md §6)
  Focus ring: t.focusRing on :focus-visible

IMPORTANT — DO NOT render ◐ paused indicator. isPaused is always false; the branch is deferred Post-MVP.
IMPORTANT — DO NOT render >_ badge. isCli is always false; CLI discovery is Post-MVP.

SSE re-key (critical — see IMPLEMENTATION_PLAN.md Phase 4):
  Derive: const effectiveTopic = (activeMonitorTab && activeFlowSessions[activeMonitorTab])
            ? activeMonitorTab : activeTopic
  Add activeMonitorTab to useEffect dependency array.
  Use effectiveTopic everywhere activeTopic was used inside the useEffect.
  Handle stale tab: if activeFlowSessions[activeMonitorTab] is undefined → fall back to activeTopic (EC-4.3).

Overflow >4 tabs: collect extras in a '...' button dropdown.

On tab session end: setActiveMonitorTab(null) to revert to activeTopic path (EC-4.2).

────────────────────────────────────────────────
PHASE 5 — Running-flow banner
────────────────────────────────────────────────

READ FlowEditor/zIndex.ts first. If Z.toast is missing, STOP and report — do not invent z-index values.

In FlowEditor/VisualView/index.tsx:
  isRunning = fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'
  isMultiFlow = Object.keys(activeFlowSessions).length >= 2

Banner position and style (DESIGN.md §7 — exact values):
  position: absolute, top: 12px, left: 50%, transform: translateX(-50%)
  maxWidth: 520px, width: calc(100% - 48px), borderRadius: 6px, padding: 10px 14px
  backgroundColor: t.bgSurface1, border: 1px solid t.runtime
  zIndex: Z.toast - 1

Banner accessibility (required):
  <div role="status" aria-live="assertive" aria-label={`${flowName} is running in ${fsmState.current}`}>
  "View in Monitor →" button: aria-label="View running flow in Monitor panel"
  "✕" dismiss button: aria-label="Dismiss banner"
  Both buttons: apply t.focusRing on focus-visible

"View in Monitor →" calls setActivePanel('monitor') — NOT a new bottomPanel field.
When isMultiFlow && isRunning: call setActivePanel('monitor') once on mount.

Hover-to-pause auto-dismiss (DESIGN.md §7 — required, not optional):
  timerRef pattern — clearTimer on onMouseEnter, startTimer on onMouseLeave.
  startTimer sets setTimeout(8000) → setDismissed(true).
  Clear timer on effect cleanup.

dismissed state resets:
  - When activeTopic changes (useEffect dep)
  - When isRunning transitions false → true (useRef tracking, EC-3.2)

────────────────────────────────────────────────
PHASE 6 — Plan card enhancements
────────────────────────────────────────────────

FIRST — check a real EVENTS.jsonl file (e.g. pathly/plans/studio-monitor-live/EVENTS.jsonl)
to confirm 'conversation' field exists on AGENT_DONE events. If absent, omit cost row (EC-2.6).

ACTIVE STATUS COLOR FIX (do before new work — DESIGN.md §8):
  In statusBorderColor: replace t.blue with t.runtime for IN_PROGRESS/REVIEWING/BUILDING.
  In statusBgColor: replace blue tint with 'rgba(34,211,238,0.05)'.
  Leave t.blue ONLY in EventLog eventType labels — do NOT change those.

Extend ConvRow in types/index.ts: add phases?: string
Update parseProgressMd in usePlanConversations.ts: parse phase range from table, set conv.phases.

Pulsing border — color only, width always 3px (EC-3.4):
  @keyframes pathly-pulse-border {
    0%, 100% { border-left-color: #22D3EE; }
    50% { border-left-color: rgba(34,211,238,0.15); }
  }
  .pathly-pulse-border { animation: pathly-pulse-border 1.5s ease-in-out infinite; }
  /* 1.5s: status heartbeat — intentional */
  @media (prefers-reduced-motion: reduce) { .pathly-pulse-border { animation: none; } }
Inject once via styleInjectedRef (same pattern as FsmView).

Card interactivity (DESIGN.md §8):
  role="button", tabIndex={0}, cursor: pointer, aria-pressed={selectedConv === conv.num}
  onClick → setSelectedConv(conv.num)
  onKeyDown → Enter/Space → setSelectedConv(conv.num)
  Focus ring: t.focusRing via :focus-visible (or inline outline on focus)

Hover: backgroundColor: t.bgSurface1 (track hoveredConv state)
Selected: backgroundColor: t.bgSurface1 + borderLeft: 3px solid t.accent (violet, replaces status border)

Status icons: ✓ (COMPLETED_GREEN), ● (t.runtime + pulse), ○ (t.textMuted), ✗ (t.red)

Cost row (if data available):
  fontFamily: t.fontFamilyMono, fontSize: 12px, color: t.textMuted
  'Xk in / Yk out · $Z' — format: (tokens_in/1000).toFixed(1)k

Relative timestamp: import formatRelativeTime from Monitor/utils.ts (Conv 1 created this).
Phase range: conv.phases from updated parseProgressMd — show 'Phase N–M' if present.
Min-height: 52px per card.

────────────────────────────────────────────────
PHASE 7 — Last-used flow + auto-open Monitor
────────────────────────────────────────────────

Add to uiStore.ts:
  lastUsedFlowPath: string | null
  setLastUsedFlowPath: (p: string | null) => void
  Persist to localStorage key 'pathly:lastUsedFlowPath' — read on init, write on set.

Set lastUsedFlowPath whenever selected flow changes (hook into existing flow-open action).

In App.tsx — one-time mount useEffect:
  if (fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE') {
    setActivePanel('monitor')
  }
  if (lastUsedFlowPath) {
    // attempt to open — catch error, clear lastUsedFlowPath and show empty state (EC-2.5)
  }

────────────────────────────────────────────────
SCOPE CONSTRAINTS
────────────────────────────────────────────────
Do NOT add a bottomPanel store field — use existing setActivePanel.
Do NOT implement CLI discovery, pid watchers, or >_ badges (Post-MVP).
Do NOT render ◐ (no production signal for isPaused).
Do NOT fix EVENTS.jsonl/SSE race (EC-1.1) — documented limitation.
uiStore changes must be backwards-compatible (activeTopic, monitorSource, activePanel still work).

Verify: cd studio; npm run typecheck
After done, update pathly/plans/studio-monitor-live/PROGRESS.md phases 4–7 to DONE.
If FlowEditor/zIndex.ts is missing at Phase 5, stop and report.
If typecheck fails and fix requires out-of-scope changes, stop and report.
```

**Expected output:** Monitor has ARIA-compliant tab bar for multi-flow with Arrow key navigation, SSE re-keys on tab switch, canvas shows running banner with hover-to-pause and `setActivePanel`, PlanBoard cards have `t.runtime` active borders (not `t.blue`), pulsing color-only, cost rows, and `role="button"` interactivity. Studio reopens to last-used flow.

**Files touched:** `store/uiStore.ts`, `Monitor/index.tsx`, `FlowEditor/VisualView/index.tsx`, `PlanBoard.tsx`, `types/index.ts`, `hooks/usePlanConversations.ts`, `App.tsx`
