# studio-monitor-live — Conversation Guide

Split into 2 conversations. Each produces runnable, typecheck-passing code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Rail, Trace & Live Badge (Phases 1–3)

**Stories delivered:** S1, S2, S3

**Prompt to paste:**
```
Implement studio-monitor-live Conversation 1 (Phases 1–3) from pathly/plans/studio-monitor-live/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read the live files listed below to confirm their current state. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: Phases 1 and 2
- `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: Phase 3
- `studio/src/renderer/src/store/uiStore.ts` — READ ONLY: confirm monitorSource field exists

**Context from design spec:** pathly/plans/studio-visual-flow-builder/MONITOR_DESIGN_SPEC.md Q3 (Monitor design), Q5 (debug flows), Q2 (entry point). Read this for visual design details.

Scope:

Phase 1 — Upgrade FsmView to connected rail:
- Replace the current box-list layout with a horizontal connected rail (thin 1px line, state dots as 10px circles)
- Completed dots: green fill; active: cyan fill + pathly-pulse animation; future: muted outline
- Active dot slides via CSS `transform: translateX` (150ms ease-out) — use a ref-driven absolutely positioned marker, NOT a full re-render
- Loop-back: activeIdx is computed from current fsmState.current — if the state is REVIEWING and the next event sends it back to BUILDING, activeIdx just reflects the new current state (the dot snaps back naturally)
- `cycle N` label for debug/explore flows (`fsmState.flow === 'debug' || 'explore'`); `conv N` for team
- Remove the "System active — STATE" status line; the rail replaces it

Phase 2 — Execution trace below the rail:
- Add a scrollable chronological list of STATE_TRANSITION events below the rail
- Each row: `icon | STATE | conv/cycle N | agent | relative time`
- Derive agent for each state visit: find the AGENT_SPAWNED event with the closest timestamp after the STATE_TRANSITION
- Status icon: `✓` (green) for past states, `●` (cyan, pulsing) for active, `✗` (red) for failed (use heuristic: REVIEWING that was followed by a backward transition)
- Loop re-visits appear as separate rows
- Empty state: single muted line "Waiting for flow activity."
- `formatRelativeTime(ts)`: returns "now" (<60s), "Xm ago", "Xh ago"

Phase 3 — SSE live source badge:
- In HeaderBar (inside Monitor/index.tsx), read `monitorSource` from `useStore()`
- Render `● live` (color: `#22D3EE`, 11px) or `○ polling` (color: textMuted, 11px) flush-right in the header title row

Architectural rules:
- Read CLAUDE.md if present for project-wide rules
- Stay within Monitor components and FsmView. Do not touch PlanBoard, FlowEditor, or store schema.
- No new IPC calls — all data comes from existing store (events, fsmState, pipelineStates, monitorSource)

Do NOT touch PlanBoard, FlowEditor, Sidebar, or store state shape.
Verify: `cd studio; npm run typecheck`
After done, update pathly/plans/studio-monitor-live/PROGRESS.md phases 1–3 to DONE.

If typecheck fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** Monitor shows a connected rail with a sliding dot, an execution trace below it, and a small `● live`/`○ polling` badge in the header.

**Files touched:** `Monitor/FsmView.tsx`, `Monitor/index.tsx`

---

## Conversation 2: Tabs, Banner & Plan Cards (Phases 4–6)

**Stories delivered:** S4, S5, S6

**Prompt to paste:**
```
Implement studio-monitor-live Conversation 2 (Phases 4–6) from pathly/plans/studio-monitor-live/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read the live files listed below to confirm their current state. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/store/uiStore.ts` — MODIFY: add activeFlowSessions, activeMonitorTab
- `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: tab bar
- `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` — MODIFY: running banner
- `studio/src/renderer/src/components/PlanBoard.tsx` — MODIFY: card enhancements

**Context from design spec:** pathly/plans/studio-visual-flow-builder/MONITOR_DESIGN_SPEC.md Q2 (entry point), Q3 (monitor tabs), Q4 (plan cards), Q6 (multi-flow). Read for precise visual specs.

Scope:

Phase 4 — Multi-flow store + Monitor tabs:
- Add to uiStore.ts: `activeFlowSessions: Record<string, FlowSession>`, `activeMonitorTab: string | null`, and their setters. FlowSession = `{ flowKey: string, topic: string, isRunning: boolean, isCli: boolean }`.
- In Monitor/index.tsx: when Object.keys(activeFlowSessions).length > 1, render a tab bar above the rail content. Each tab: flow filename + cyan `●` if running + `>_` badge if CLI.
- Clicking a tab calls `setActiveMonitorTab(flowKey)`.
- Overflow >4 tabs: `...` overflow button that opens a simple dropdown list.
- Single-session path (activeTopic only, no multi-flow): no tab bar, existing behavior unchanged.
- When `activeMonitorTab` is set, Monitor reads session data for that tab's topic instead of `activeTopic`.

Phase 5 — Running-flow banner on canvas:
- In FlowEditor/VisualView/index.tsx: read `fsmState` from store. Derive `isRunning = fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'`.
- Render a banner absolutely positioned at the top of the VisualView container (z-index 59 — from Z.toast - 1).
- Banner content: `[flowName] is running ● conv N / STATE  [View in Monitor →]  [dismiss]`
- `[dismissed, setDismissed]` local state. Reset when `activeTopic` changes (useEffect dep).
- Auto-dismiss: `useEffect` with `setTimeout(8000)` → `setDismissed(true)`. Clear on unmount.
- `[View in Monitor →]` button: switch bottom panel to Monitor. Wire to whatever tab-switching mechanism exists in App.tsx (check if there's a `bottomPanel` store value or a ref/callback). If no mechanism exists, add `setBottomPanel: (tab: string) => void` to uiStore.
- Banner style: `bgSurface1` background, 1px `#22D3EE` border, cyan `●` dot.

Phase 6 — Plan conversation card enhancements:
- In PlanBoard.tsx, enhance each ConvRow card:
  - Active status: add `pathly-pulse-border` animation (keyframes in the injected <style> tag or inline — pick simpler). Active = status IN_PROGRESS/BUILDING/REVIEWING.
  - Failed: red `✗` icon + red border color.
  - Add a second line in the card: "Phase N–M · X ago" (parse phase range from conv.title if available, else omit)
  - Add cost/token row: filter events by `e.conversation === conv.num`, sum cost_usd/tokens_in/tokens_out from AGENT_DONE entries. Show `Xk in / Yk out · $Z` muted below title. Hide row if no cost data.
  - Relative timestamp: compute from most recent event ts for that conv num.
  - Min-height: 52px per card.
  - Status icon in front of conv number: `✓` (green), `●` (cyan), `○` (muted), `✗` (red).

Architectural rules:
- Read CLAUDE.md if present for project-wide rules
- uiStore changes must be backwards-compatible — existing selectors like `activeTopic`, `monitorSource` must still work
- Do NOT touch FlowEditor canvas logic, Sidebar, FsmView, or EventLog

Verify: `cd studio; npm run typecheck`
After done, update pathly/plans/studio-monitor-live/PROGRESS.md phases 4–6 to DONE.

If typecheck fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** Monitor has a tab bar for multi-flow, canvas shows a running banner when a flow is active, PlanBoard cards show pulsing active state and cost data.

**Files touched:** `store/uiStore.ts`, `Monitor/index.tsx`, `FlowEditor/VisualView/index.tsx`, `PlanBoard.tsx`
