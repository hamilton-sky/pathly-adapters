# studio-monitor-live — Implementation Plan

## Overview

Upgrades the Pathly Studio Monitor panel from its current working-but-minimal state to the full UX spec resolved in MONITOR_DESIGN_SPEC.md. The changes are renderer-only: three Monitor components (FsmView, EventLog/trace, Monitor index), the PlanBoard, and a minor canvas banner in VisualView. No backend, IPC, or store schema changes beyond adding multi-flow session tracking.

## Layer Architecture

```
Store (uiStore/projectStore)   →   Monitor components          →   Visual output
activeSessions, monitorSource      FsmView (rail + trace)          Connected rail, sliding dot
                                   Monitor/index (tabs, SSE)       Tab bar, live badge
                                   PlanBoard (cards)               Pulsing cards, cost rows
                                   VisualView banner               Running-flow banner
```

## Conversation Map

| Conv | Phases | Focus |
|------|--------|-------|
| 1 | 1, 2, 3 | FSM rail visual upgrade, execution trace, SSE badge |
| 2 | 4, 5, 6 | Monitor tabs, running banner, plan card enhancements |

## Phases

### Phase 1: Upgrade FsmView to connected rail with CSS dot   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: replace the box-list layout with a horizontal connected rail (thin line, state dots, sliding active dot via CSS transform).

**Done when:** The Monitor pipeline section shows a rail of dots connected by a line; the active dot slides to the current state (no JS animation loop, CSS `transition: transform 150ms ease-out`); loop-back re-positions the dot on the earlier state correctly.

**Delivers stories:** S1

**Depends on:** Existing FsmView + pipelineStates from store.

**Enables:** Phase 2 (trace below the rail), Phase 3 (source badge in same component).

**Details:**

Rail layout:
```
  ●─────────────●────────────◯──────────◯
PLANNING     BUILDING    REVIEWING    DONE
                ↑ cyan dot (active)
```

- Container: `display: flex; align-items: center; position: relative;`
- Rail line: absolutely positioned 1px horizontal line across the full rail width, `bgSurface1` color
- State dot: 10px circle. Completed: green fill. Active: cyan fill + `pathly-pulse` class. Future: muted outline.
- Active dot marker: a separate absolutely-positioned cyan circle that moves via `transform: translateX` driven by a `useRef` on the active state index. Position = `(activeIdx / (total - 1)) * 100%` mapped to pixel offset. Use `requestAnimationFrame` once on mount to avoid paint-before-transition.
- State label: below each dot, 11px muted text, uppercase.
- `cycle N` vs `conv N` label: derive from `fsmState.flow`. If `flow === 'debug'` or `flow === 'explore'`, label reads `cycle N`. Otherwise `conv N`. Read conv number from `fsmState.conv ?? fsmState.current_conversation`.
- Remove the "System active — STATE" status line; the rail replaces it.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 2: Add execution trace below the rail   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx` — MODIFY: add an `ExecutionTrace` sub-section below the rail that renders a chronological list of state visits.

**Done when:** The trace shows each STATE_TRANSITION event as a row; BUILDING visited twice shows two rows; active state row has a pulsing `●`; failed states (where a review found failures) show `✗`.

**Delivers stories:** S2

**Depends on:** Phase 1.

**Enables:** Full Q3 spec compliance — rail shows WHERE, trace shows HOW WE GOT HERE.

**Details:**

Trace derives from `events` (from store), filtering for `STATE_TRANSITION` type. Build a list of `{ state, fromState, idx, ts, agent, result }` entries from those events in order.

Determine `result` per entry:
- Last transition away from a state: look at the next `STATE_TRANSITION`. If it went BACKWARDS (looped), mark the departed visit as `'looped'`. If the system moved to a state named `FIXING` or similar after a review, mark the REVIEWING visit as `'failed'`.
- Simpler heuristic: a STATE_TRANSITION event whose `from` state is REVIEWING and `to` is not DONE/next-forward → mark as `failed`.

Row layout (monospace 12px):
```
  ✓  PLANNING    conv 1    planner    2h ago
  ●  BUILDING    conv 2    builder    now         (pulsing cyan)
```

- Icon: `✓` green, `●` cyan pulse, `✗` red
- State name: `textPrimary`
- Conv/cycle label: `textMuted`
- Agent: `textMuted`, read from the AGENT_SPAWNED event closest after the STATE_TRANSITION
- Relative time: `formatRelativeTime(ts)` — "Xm ago" / "now" / "Xh ago"

Empty state (no transitions yet): single muted line "Waiting for flow activity."

**Verify:** `cd studio; npm run typecheck`

---

### Phase 3: SSE live source badge in Monitor header   ← Conversation: 1

**File:** `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: surface the `monitorSource` store value as a small muted badge in the `HeaderBar`.

**Done when:** The header shows `● live` (cyan dot) when SSE connected, `○ polling` when falling back to chokidar.

**Delivers stories:** S3

**Depends on:** `monitorSource` already in store and set in Monitor useEffect.

**Enables:** Debugging silent update failures without dev tools.

**Details:**

In `HeaderBar`, read `monitorSource` from `useStore()`. Render:
```tsx
<span style={{ fontSize: '11px', color: monitorSource === 'sse' ? t.runtime : t.textMuted }}>
  {monitorSource === 'sse' ? '● live' : '○ polling'}
</span>
```
Place it flush-right in the header title row. Use `t.runtime` (`#22D3EE`) for the live state. Size 11px, muted baseline.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 4: Multi-flow store + Monitor tab bar   ← Conversation: 2

**File:** `studio/src/renderer/src/store/uiStore.ts` — MODIFY: add `activeFlowSessions` (record of flowId → session info) and `activeMonitorTab` (current tab flow key).

**File:** `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: add tab bar above monitor content when `activeFlowSessions` has entries.

**Done when:** When multiple flows are tracked, a tab bar appears above the rail; clicking a tab switches the monitor display; CLI-originated sessions show `>_`.

**Delivers stories:** S4

**Depends on:** Conversation 1 complete.

**Enables:** Full multi-flow monitoring without separate windows.

**Details:**

Store additions to `uiStore.ts`:
```ts
interface FlowSession {
  flowKey: string          // e.g. "team.flow.yaml"
  topic: string
  isRunning: boolean
  isCli: boolean           // CLI-originated
}
activeFlowSessions: Record<string, FlowSession>
activeMonitorTab: string | null
setActiveFlowSessions: (s: Record<string, FlowSession>) => void
setActiveMonitorTab: (tab: string | null) => void
```

Monitor/index.tsx: when `Object.keys(activeFlowSessions).length > 1`, render a tab bar:
```tsx
<div style={tabBarStyle}>
  {sessions.map(s => (
    <button key={s.flowKey} onClick={() => setActiveMonitorTab(s.flowKey)}
      style={{ borderBottom: isActive ? `2px solid ${t.runtime}` : 'none', ... }}>
      {s.flowKey}
      {s.isRunning && <span style={{ color: t.runtime }}>●</span>}
      {s.isCli && <span style={{ color: t.textMuted }}>&gt;_</span>}
    </button>
  ))}
</div>
```

Overflow (>4 tabs): collect extras into a `...` button that opens a small dropdown.

Current `activeTopic`-based logic remains the default single-session path. Tab selection sets `activeMonitorTab` which the Monitor reads in place of `activeTopic` when non-null.

**Verify:** `cd studio; npm run typecheck`

---

### Phase 5: Running-flow entry banner on canvas   ← Conversation: 2

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` — MODIFY: add a non-blocking dismissible banner that appears when a flow is actively running.

**Done when:** When `fsmState.current` is not null/IDLE/DONE, the banner appears at top of canvas; "View in Monitor →" switches to Monitor tab; it auto-dismisses after 8s; `[dismiss]` closes immediately.

**Delivers stories:** S5

**Depends on:** Phase 4 (Monitor tab switching).

**Enables:** Passive awareness of running pipelines while working in the canvas.

**Details:**

Read `fsmState` and `activeTopic` from store. Derive `isRunning = fsmState.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'`.

Banner renders absolutely positioned at top of VisualView container (z-index from `Z.toast - 1 = 59`):
```
╔══════════════════════════════════════════╗
║  team.flow.yaml is running ● conv 3 / BUILDING   [View in Monitor →]  [dismiss]  ║
╚══════════════════════════════════════════╝
```

State: `const [dismissed, setDismissed] = useState(false)`. Reset `dismissed` when `activeTopic` changes. Auto-dismiss: `useEffect` with `setTimeout(8000)` that calls `setDismissed(true)`. Clear timeout on unmount.

"View in Monitor →" calls a store action to switch the active bottom-panel tab to Monitor (or sets a `bottomPanel: 'monitor'` store value — wire to whatever existing tab switching mechanism is in `App.tsx`/`TopBar.tsx`).

Banner color: `bgSurface1` background, 1px `runtime` border. Cyan `●` dot (`t.runtime`).

**Verify:** `cd studio; npm run typecheck`

---

### Phase 6: Plan conversation card enhancements   ← Conversation: 2

**File:** `studio/src/renderer/src/components/PlanBoard.tsx` — MODIFY: upgrade conversation cards with pulsing active border, `✗` failure indicator, cost/token row, and relative timestamps.

**Done when:** Active conv card has a pulsing cyan left border; failed has red `✗`; cost row appears when events have AGENT_DONE cost data; cards are min 52px tall.

**Delivers stories:** S6

**Depends on:** Existing PlanBoard + events loaded from EVENTS.jsonl.

**Enables:** Plan progress visibility without opening Event Log.

**Details:**

Status determination per conv: cross-reference `conv.status` with EVENTS.jsonl:
- Active: `conv.status === 'IN_PROGRESS'` or `conv.status === 'BUILDING'` or `conv.status === 'REVIEWING'`
- Failed: `conv.status === 'BLOCKED'` or events contain a RETRY/FILE_DELETED for that conv number
- Done: `conv.status === 'DONE'`

Active card: inject CSS animation class `pathly-pulse-border` (keyframes: border-color cycles from cyan → transparent → cyan, 1.5s). Or simpler: add the `pathly-pulse` class to the left border element. Keep the 3px width.

Status icons in card:
```
  [✓ or ● or ○ or ✗]  Conv N · Phase title        [status badge]
  agents · phase range · relative time
  Xk in / Yk out · $Z                              (if cost data exists)
```

Relative time: compute from the most recent event `ts` for that conversation number. Format: "Xm ago" / "Xh ago" / "just now".

Cost aggregation: filter `events` by `conversation === conv.num`, sum `cost_usd`, `tokens_in`, `tokens_out` from AGENT_DONE entries.

Min-height: add `minHeight: '52px'` to the card container style.

Phase range: PlanBoard already reads `ConvRow`; extend `ConvRow` to include `phases?: string` from the PROGRESS.md parser if available. Display as `Phase N–M` if present.

**Verify:** `cd studio; npm run typecheck`

---

## Prerequisites

- Conversation 1 (`studio-visual-flow-builder` Conv 1) must be complete — this plan does not change FlowEditor components beyond the banner in Phase 5.
- Confirm `monitorSource` exists in `uiStore.ts` before implementing Phase 3.
- Confirm `fsmState`, `events`, `pipelineStates` in store before implementing Phases 1–2.

## Key Decisions

- Rail dot uses CSS `transform: translateX` on a ref-driven element — no full re-render on each transition event.
- Execution trace is derived from `STATE_TRANSITION` events in the existing store; no new server data needed.
- Multi-flow tabs add `activeFlowSessions` to uiStore; current single-topic path remains the default.
- Running banner is canvas-local state (dismissed flag) that reads global `fsmState`; it does not write to store.
- Plan cards aggregate cost from EVENTS.jsonl already loaded in PlanBoard — no extra IPC calls.
