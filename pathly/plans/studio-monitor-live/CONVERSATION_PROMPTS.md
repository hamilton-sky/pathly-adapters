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
- `studio/src/renderer/src/components/Monitor/utils.ts` — CREATE: formatRelativeTime helper
- `studio/src/renderer/src/theme.ts` — VERIFY/MODIFY: confirm `runtime` token (#22D3EE) exists; add if missing

**Context from design spec:** read pathly/plans/studio-visual-flow-builder/MONITOR_DESIGN_SPEC.md Q3 (Monitor design), Q5 (debug flows), Q2 (entry point) for visual design details before implementing.

Scope:

Phase 1 — Upgrade FsmView to connected rail:
- FIRST: read theme.ts and confirm `runtime` token exists at `#22D3EE`. Add it if missing (e.g. `runtime: '#22D3EE'` in the theme object and Theme type). Every subsequent phase uses `t.runtime`.
- Replace the current box-list layout with a horizontal connected rail: thin 1px absolute line, state dots as 10px circles
- Completed dots: green fill; active: cyan fill + pathly-pulse class; future: muted outline
- Active dot slides via CSS `transform: translateX` (150ms ease-out) — ref-driven absolutely positioned marker. Use `useRef` on the rail container + `useLayoutEffect` to compute rail width for transform calc. One `requestAnimationFrame` on mount to avoid paint-before-transition.
- `activeIdx = PIPELINE.indexOf(fsmState.current ?? '')` — single-index lookup. Loop-back emerges naturally.
- `cycle N` label: `fsmState.flow === 'debug' || fsmState.flow === 'explore'` → `cycle N`; else `conv N`. Custom/unknown flow names → `conv N`.
- Remove the "System active — STATE" status line entirely — the rail replaces it.
- Keep existing `pathly-pulse` keyframes injection (styleInjectedRef pattern).

Phase 2 — Execution trace below the rail:
- CREATE `studio/src/renderer/src/components/Monitor/utils.ts` with `formatRelativeTime(ts: string): string`:
  - <60s → "now"; <60min → "Xm ago"; else "Xh ago"
- Add scrollable execution trace below the rail in FsmView.tsx
- Filter `events` from store for `type === 'STATE_TRANSITION'`; build chronological VisitRow list
- Agent per row: first AGENT_SPAWNED event with ts > stateTransition.ts; if none → "—"
- **Failure detection — IMPORTANT: do NOT hardcode state names like "FIXING" or "REVIEWING".**
  Use `pipelineStates` order: after a STATE_TRANSITION, check the next STATE_TRANSITION's `to` field.
  If `PIPELINE.indexOf(nextTo) < PIPELINE.indexOf(currentTo)` → mark current visit as `'failed'`.
  This works for any flow topology (team, debug, explore, custom).
- **EVENTS.jsonl / SSE race note:** initial `readFile` load can arrive after SSE appends, overwriting events.
  Do NOT try to fix this pre-existing bug. Just sort VisitRows by `ts` before rendering to avoid crashes.
- Row layout: `[icon]  STATE    conv/cycle N    agent    relative time` (12px monospace)
- Icon: `✓` green for done, `●` cyan pulsing for active, `✗` red for failed
- Empty state: single muted line "Waiting for flow activity."

Phase 3 — SSE live source badge:
- In HeaderBar (Monitor/index.tsx), read `monitorSource` from `useStore()`
- Three states: `'sse'` → `● live` (t.runtime, 11px); `'chokidar'` → `○ polling` (textMuted, 11px); `null` or anything else → `—` (textMuted)
- Remove any existing `Source: SSE live` or similar label text from the header
- Render flush-right in the header title row

Architectural rules:
- Read CLAUDE.md if present for project-wide rules
- Stay within Monitor components. Do not touch PlanBoard, FlowEditor, or store schema.
- No new IPC calls — all data from existing store (events, fsmState, pipelineStates, monitorSource)

Do NOT touch PlanBoard, FlowEditor, Sidebar, or store state shape.
Verify: `cd studio; npm run typecheck`
After done, update pathly/plans/studio-monitor-live/PROGRESS.md phases 1–3 to DONE.

If typecheck fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** Monitor shows a connected rail with a sliding dot, execution trace below it, and `● live`/`○ polling`/`—` badge in the header. `formatRelativeTime` utility created in `Monitor/utils.ts`.

**Files touched:** `Monitor/FsmView.tsx`, `Monitor/index.tsx`, `Monitor/utils.ts`, `theme.ts` (conditional)

---

## Conversation 2: Tabs, Banner, Cards & Last-Used Flow (Phases 4–7)

**Stories delivered:** S4, S5, S6, S7

**Prompt to paste:**
```
Implement studio-monitor-live Conversation 2 (Phases 4–7) from pathly/plans/studio-monitor-live/IMPLEMENTATION_PLAN.md.

**Before editing anything:** read the live files listed below. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `studio/src/renderer/src/store/uiStore.ts` — MODIFY: activeFlowSessions, activeMonitorTab, lastUsedFlowPath
- `studio/src/renderer/src/components/Monitor/index.tsx` — MODIFY: tab bar + SSE re-key
- `studio/src/renderer/src/components/FlowEditor/VisualView/index.tsx` — MODIFY: running banner
- `studio/src/renderer/src/components/FlowEditor/zIndex.ts` — READ ONLY: confirm Z.toast exists
- `studio/src/renderer/src/components/PlanBoard.tsx` — MODIFY: card enhancements
- `studio/src/renderer/src/types/index.ts` — MODIFY: extend ConvRow with phases?
- `studio/src/renderer/src/hooks/usePlanConversations.ts` — MODIFY: parse phase range
- `studio/src/renderer/src/App.tsx` — MODIFY: auto-open Monitor on mount

**Context from design spec:** read pathly/plans/studio-visual-flow-builder/MONITOR_DESIGN_SPEC.md Q2, Q4, Q6 before implementing.

Scope:

Phase 4 — Multi-flow store + Monitor tabs + SSE re-key:
- Add to uiStore.ts:
  ```ts
  interface FlowSession {
    flowKey: string; topic: string; isRunning: boolean; isPaused: boolean; isCli: false
  }
  activeFlowSessions: Record<string, FlowSession>
  activeMonitorTab: string | null
  setActiveFlowSessions: (s: Record<string, FlowSession>) => void
  setActiveMonitorTab: (tab: string | null) => void
  ```
  `isCli` is always `false` — CLI session discovery is Post-MVP. Do NOT implement pid/lock file watchers.
- Producer in Monitor/index.tsx useEffect: after STATE.json is parsed, call setActiveFlowSessions to upsert current topic. Remove session on useEffect cleanup.
- Tab bar: show when `Object.keys(activeFlowSessions).length >= 2`. Hide for 0 or 1 session.
  Each tab: flowKey + `●` (runtime, isRunning) + `◐` (textMuted, isPaused). NO `>_` badge (isCli always false).
  Overflow at >4 tabs: `...` button opens simple dropdown.
- **SSE re-key — CRITICAL:** derive `effectiveTopic = activeMonitorTab ?? activeTopic` inside the Monitor useEffect. Add `activeMonitorTab` to the dependency array. The existing cleanup (es.close(), removeListener()) already handles re-keying when deps change. Use `effectiveTopic` everywhere `activeTopic` was used inside that useEffect.
- Note: tab bar redundancy — `flowKey` should NOT be repeated as a field if it's already the Record key. Use topic as the key; keep flowKey as a display field.

Phase 5 — Running-flow banner on canvas:
- FIRST: read `studio/src/renderer/src/components/FlowEditor/zIndex.ts`. Confirm `Z.toast` exists. If the file doesn't exist, stop and report — it's a prerequisite from studio-visual-flow-builder Phase 7b.
- In FlowEditor/VisualView/index.tsx: read fsmState, activeTopic, activeFlowSessions, setActivePanel from store.
- `isRunning = fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE'`
- `isMultiFlow = Object.keys(activeFlowSessions).length >= 2`
- Show banner ONLY when `isRunning && !isMultiFlow`
- When `isMultiFlow && isRunning`: call `setActivePanel('monitor')` automatically (once per mount, via useEffect with empty dep array — so it runs once when the component first sees both conditions true)
- **"View in Monitor →" button calls `setActivePanel('monitor')` from uiStore — NOT a new bottomPanel field. Monitor and canvas are mutually exclusive panels.**
- Banner local state (dismissed, auto-dismiss, reset):
  - `dismissed` resets when `activeTopic` changes
  - `dismissed` also resets when isRunning transitions false→true (new run started): track with `useRef`
  - Auto-dismiss: `setTimeout(8000)` in useEffect, clear on cleanup
- Banner style: absolute top of VisualView, `bgSurface1` bg, 1px `t.runtime` border, z-index `Z.toast - 1`
- Banner text: `{flowName} is running ● {convLabel} / {fsmState.current}  [View in Monitor →]  [dismiss]`

Phase 6 — Plan card enhancements:
- FIRST: check one real EVENTS.jsonl file (e.g. pathly/plans/studio-monitor-live/EVENTS.jsonl) to confirm the `conversation` field is present on AGENT_DONE events. If absent, omit cost rows entirely.
- Extend ConvRow in types/index.ts: add `phases?: string`
- Update parseProgressMd in usePlanConversations.ts: parse phase range from the "| Conv | Phases |" table row and set `phases` (e.g. "1–3")
- Card status: active = IN_PROGRESS/BUILDING/REVIEWING; failed = BLOCKED; done = DONE; pending = TODO
- Status icons: `✓` (green), `●` (cyan, pulsing), `○` (muted), `✗` (red)
- Active border: inject `pathly-pulse-border` keyframes once via styleInjectedRef pattern. Class name `pathly-pulse-border` applied to active card wrapper.
- Hover state: `backgroundColor: t.bgSurface1`. Track `hoveredConv` in local state.
- Selected state: `backgroundColor: t.bgSurface1` + violet accent left border (replaces status border). Track `selectedConv`.
- Cost row: filter events by `e.conversation === conv.num`, sum from AGENT_DONE. Show `Xk in / Yk out · $Z` muted. Hide if no data or conversation field absent.
- Relative timestamp: formatRelativeTime from Monitor/utils.ts (import it). Use most recent event ts for that conv num.
- Phase range: show `conv.phases` if present (e.g. "Phase 1–3")
- Min-height: 52px per card

Phase 7 — Last-used flow + auto-open Monitor:
- Add `lastUsedFlowPath: string | null` to uiStore.ts with setter. Persist to localStorage: read on init, write on change.
- In App.tsx, add a one-time mount useEffect:
  ```ts
  useEffect(() => {
    if (fsmState?.current && fsmState.current !== 'IDLE' && fsmState.current !== 'DONE') {
      setActivePanel('monitor')
    }
    // load lastUsedFlowPath — wire to whatever action opens a flow file in the canvas
  }, [])
  ```
- Set `lastUsedFlowPath` whenever the selected flow changes (find the existing flow-open action/setter and hook in).
- On mount: if `lastUsedFlowPath` is non-null, attempt to open it. If readFile fails (deleted), clear `lastUsedFlowPath` and show empty state.

Architectural rules:
- Read CLAUDE.md if present for project-wide rules
- uiStore changes must be backwards-compatible — existing selectors (activeTopic, monitorSource, activePanel) must still work
- Do NOT implement CLI discovery, pid watchers, or `>_` badges — Post-MVP
- Do NOT add a `bottomPanel` store field — use existing `activePanel`
- Do NOT touch FlowEditor canvas logic, Sidebar, FsmView, or EventLog

Verify: `cd studio; npm run typecheck`
After done, update pathly/plans/studio-monitor-live/PROGRESS.md phases 4–7 to DONE.

If typecheck fails and the fix requires out-of-scope changes, stop and report.
If FlowEditor/zIndex.ts is missing at Phase 5, stop and report — do not invent z-index values.
```

**Expected output:** Monitor has tab bar for multi-flow, SSE re-keys on tab switch, canvas shows running banner pointing at `setActivePanel`, PlanBoard cards are enhanced, Studio reopens to last-used flow.

**Files touched:** `store/uiStore.ts`, `Monitor/index.tsx`, `FlowEditor/VisualView/index.tsx`, `PlanBoard.tsx`, `types/index.ts`, `hooks/usePlanConversations.ts`, `App.tsx`
