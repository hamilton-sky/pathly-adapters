# studio-monitor-live — User Stories

## Context

Pathly Studio has a working Monitor panel with SSE event streaming, an FsmView pipeline display, and a PlanBoard with conversation cards. The design spec (MONITOR_DESIGN_SPEC.md) has resolved all open UX questions and specifies a set of visual and functional upgrades: a connected FSM topology rail with a sliding dot, an execution trace below the rail, multi-flow monitor tabs, a running-flow entry banner, and richer plan conversation cards. This plan implements those spec decisions without touching the visual flow editor or sidebar (scope of `studio-visual-flow-builder`).

See **DESIGN.md** for all token values, spacing, color constants, and accessibility specs.
See **EDGE_CASES.md** for edge case handling per story.

---

## Stories

### Story S1: FSM Topology Rail with Sliding Dot

**As a** developer watching a Pathly pipeline, **I want** a horizontal connected rail that shows all FSM states as nodes with a dot that slides to the active state, **so that** I can instantly see where the pipeline is at a glance without reading text labels.

**Acceptance Criteria:**
- [ ] `t.runtime: '#22D3EE'` (dark) and `t.runtime: '#0EA5E9'` (light) added to `Theme` interface and both theme objects in `theme.ts` — do this before any other change
- [ ] `t.fontFamilyMono` added to `Theme` interface and both theme objects
- [ ] Module-scope constants in `FsmView.tsx`: `COMPLETED_GREEN = '#16A34A'` (solid, NOT rgba — rgba fails WCAG 3:1), `ACTIVE_CYAN = '#06B6D4'`, `BLOCKED_AMBER = '#FBBF24'`
- [ ] Rail renders as a horizontal flex row with a **2px** connecting line, split into done-segment (`COMPLETED_GREEN`) and pending-segment (`t.bgSurface1`)
- [ ] Rail container has `role="progressbar"` + `aria-valuenow` + `aria-valuemin` + `aria-valuemax` + `aria-label`
- [ ] Each dot has `role="img"` + `aria-label="STATE: completed/active/pending"`
- [ ] Completed dots: `COMPLETED_GREEN` solid fill (filled circle)
- [ ] Active dot: ring + inner dot via `border + box-shadow` using `ACTIVE_CYAN` (shape encoding — not color-only)
- [ ] Future dots: `t.textMuted` stroke, transparent fill (hollow ring)
- [ ] Active dot slides to current state via CSS `transform: translateX` using `t.transitionBase` (`150ms ease-out`) — ref-driven, no JS animation loop
- [ ] **First position** calculated in `useLayoutEffect` synchronously on mount (before ResizeObserver fires) — no one-frame flash
- [ ] Loop-back: dot snaps back to earlier state (index lookup on `PIPELINE.indexOf(fsmState.current)`)
- [ ] `cycle N` label for `fsmState.flow === 'debug'` or `=== 'explore'`; `conv N` for all others
- [ ] `pathly-pulse` uses **opt-in** motion: base = `animation: none`; add 2-cycle entrance under `prefers-reduced-motion: no-preference`
- [ ] Sliding dot: instant opacity crossfade (not translateX) when `prefers-reduced-motion: reduce`
- [ ] Old "System active — STATE" status line removed

**Edge Cases:** EC-2.2, EC-2.3, EC-2.4 in EDGE_CASES.md

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Execution Trace Below Rail

**As a** developer, **I want** a chronological execution trace below the rail, **so that** I can see every state visit in order — including loop re-visits — without losing history.

**Acceptance Criteria:**
- [ ] Trace renders below the rail in a scrollable container
- [ ] Container has `role="log"` `aria-label="Execution trace"` `aria-live="polite"` `aria-atomic="false"` `tabIndex={0}`
- [ ] Row typography hierarchy: state name = 12px weight-600 `t.textPrimary`; conv/agent/timestamp = 11px weight-400 `t.textMuted`
- [ ] Status icons: `✓` (`COMPLETED_GREEN`), `●` (`ACTIVE_CYAN`, 2-cycle entrance pulse), `✗` (`t.red`)
- [ ] Loop re-visits appear as additional rows (BUILDING visited twice = two rows)
- [ ] Failure detection uses `pipelineStates` order (backward index = failed), NOT hardcoded state names
- [ ] `formatRelativeTime(ts)` in `Monitor/utils.ts`: `<60s → 'now'`, `<60min → 'Xm ago'`, else `'Xh ago'`
- [ ] `useInterval` 30s refresh forces relative timestamp re-render (stale "2m ago" problem)
- [ ] Agent derived from nearest `AGENT_SPAWNED` after `STATE_TRANSITION`; shows `—` if none found
- [ ] Rows sorted by `ts` before rendering (guards against EVENTS.jsonl/SSE race, EC-1.1)
- [ ] `React.memo` on `VisitRow` with stable key (`ts + from + to`)
- [ ] Insertion sort into already-sorted array (not full `.sort()` on every render)
- [ ] Auto-scroll to latest entry; pauses when user scrolls up; `"↓ scroll to latest"` affordance visible when paused
- [ ] `aria-live` writes debounced 300ms to prevent screen reader flooding on SSE bursts
- [ ] Empty state: `"Waiting for flow activity."` in `t.textMuted` 13px centered

**Edge Cases:** EC-1.1, EC-1.2, EC-1.3 in EDGE_CASES.md

**Delivered by:** Phase 2 → Conversation 1

---

### Story S3: SSE Live Source Badge

**As a** developer, **I want** a small live-source indicator in the Monitor header, **so that** I know whether the monitor is receiving live SSE events, polling, or not yet connected.

**Acceptance Criteria:**
- [ ] `monitorSource === 'sse'` → `● live` in `t.runtime`, 12px
- [ ] `monitorSource === 'chokidar'` → `○ polling` in `t.textMuted`, 12px
- [ ] `monitorSource === null` → `—` in `t.textMuted`, 12px (does NOT show `○ polling`)
- [ ] Badge has `role="status"` + `aria-live="polite"` + `aria-atomic="true"` with accessible `aria-label`
- [ ] `●` and `○` glyphs wrapped in `aria-hidden="true"`; `aria-label` carries the text alternative
- [ ] `es.onerror` wired: `readyState === CLOSED` → set `null`; `readyState === CONNECTING` → leave badge as-is
- [ ] Any existing `Source: SSE live` or `Source:` label text removed from header
- [ ] Badge rendered flush-right in the header title row

**Edge Cases:** EC-2.1 in EDGE_CASES.md

**Delivered by:** Phase 3 → Conversation 1

---

### Story S4: Monitor Tabs for Concurrent Flows

**As a** developer, **I want** a tab bar when multiple flows are active, **so that** I can watch and switch between concurrent pipelines.

**Acceptance Criteria:**
- [ ] Tab bar shown only when `Object.keys(activeFlowSessions).length >= 2`; hidden for 0 or 1 session
- [ ] `activeFlowSessions` populated from Studio-launched sessions only (CLI discovery is Post-MVP)
- [ ] Each tab: `role="tab"`, `aria-selected`, flow filename, cyan `●` when `isRunning`
- [ ] Tab bar container: `role="tablist"`, `aria-label="Active flows"`
- [ ] Keyboard: Arrow keys navigate between tabs; Tab key exits the tablist; Enter/Space selects
- [ ] Only active tab has `tabIndex={0}`; all others have `tabIndex={-1}` (roving tabindex)
- [ ] Active tab: `borderBottom: 2px solid t.runtime`, `color: t.textPrimary`, `backgroundColor: t.bgSurface0`
- [ ] Inactive tab: `color: t.textMuted`, no underline
- [ ] `●` dot has `aria-hidden="true"` (decorative — `aria-selected` conveys state)
- [ ] >4 tabs: `...` overflow button opens dropdown
- [ ] Tab switch updates `activeMonitorTab` AND re-keys SSE subscription (`effectiveTopic = activeMonitorTab ?? activeTopic`)
- [ ] `isCli` always `false`; no `>_` badge rendered (Post-MVP)
- [ ] `◐` paused indicator NOT implemented (no production signal for `isPaused`; deferred Post-MVP)

**Edge Cases:** EC-3.5, EC-4.1, EC-4.2, EC-4.3 in EDGE_CASES.md

**Delivered by:** Phase 4 → Conversation 2

---

### Story S5: Running-Flow Entry Banner

**As a** developer, **I want** a non-blocking banner on the canvas when a flow is actively running, **so that** I don't miss an in-progress session when switching to the canvas view.

**Acceptance Criteria:**
- [ ] Banner shown only when `isRunning && !isMultiFlow`
- [ ] When `isMultiFlow && isRunning`: `setActivePanel('monitor')` called automatically on mount (once)
- [ ] Banner position: `top: 12px`, `left: 50%`, `transform: translateX(-50%)`, `maxWidth: 520px`, `borderRadius: 6px`, `padding: 10px 14px`
- [ ] Style: `backgroundColor: t.bgSurface1`, `border: 1px solid t.runtime`
- [ ] Content: `● {flowName} is running · {convLabel} / {fsmState.current}  [View in Monitor →]  [✕]`
- [ ] `"View in Monitor →"` calls `setActivePanel('monitor')` — NOT a new store field
- [ ] `"View in Monitor →"` has `aria-label="View running flow in Monitor panel"`
- [ ] Banner wrapper has `role="status"` and `aria-live="assertive"`
- [ ] Hover-to-pause: `onMouseEnter` clears 8s timer; `onMouseLeave` restarts it
- [ ] `dismissed` state resets when `activeTopic` changes
- [ ] `dismissed` state resets when `isRunning` transitions `false → true` (new run started)
- [ ] z-index: `Z.toast - 1` from `FlowEditor/zIndex.ts` (prerequisite: Phase 7b of studio-visual-flow-builder)
- [ ] Uses `t.transitionBase` token, not hardcoded `150ms`

**Edge Cases:** EC-3.1, EC-3.2, EC-3.3 in EDGE_CASES.md

**Delivered by:** Phase 5 → Conversation 2

---

### Story S6: Plan Conversation Cards Enhancement

**As a** developer reviewing a plan, **I want** conversation cards that show active pulsing, failure indicators, cost data, hover/selected states, and timestamps, **so that** I can assess plan progress at a glance.

**Acceptance Criteria:**
- [ ] `statusBorderColor` and `statusBgColor` in PlanBoard: replace `t.blue` with `ACTIVE_CYAN` for active statuses (IN_PROGRESS, REVIEWING, BUILDING) — leave `t.blue` in EventLog untouched
- [ ] Active card: 2-cycle entrance pulse via `pathly-pulse-border` (color-only, width stays `3px` always); class removed after `animationend` so re-activation re-triggers
- [ ] `pathly-pulse-border` uses opt-in pattern: base = `animation: none`; add under `prefers-reduced-motion: no-preference`
- [ ] Failed card: `t.red` left border + `✗` icon
- [ ] Pending card: `t.textMuted` left border + `○` icon
- [ ] Hover: `backgroundColor: t.bgSurface1` (no border change)
- [ ] Selected: `backgroundColor: t.bgSurface1` + `t.accent` violet left border (replaces status border)
- [ ] Card is interactive: `role="button"`, `tabIndex={0}`, `cursor: pointer`, Enter/Space triggers selection
- [ ] Focus ring applied via `t.focusRing` on keyboard focus
- [ ] Token/cost row: `Xk in / Yk out · $Z` in `t.fontFamilyMono` 12px; hidden if no `cost_usd` data
- [ ] Cost filtered by `e.conversation === conv.num` on AGENT_DONE events (EC-2.6: if field absent, hide row)
- [ ] Relative timestamp from most recent event `ts` via `formatRelativeTime` (imported from `Monitor/utils.ts`)
- [ ] Phase range shown if `ConvRow.phases` populated (from updated `parseProgressMd`)
- [ ] 52px min-height per card; error-state cards expand to 72px
- [ ] Cost row uses `font-variant-numeric: tabular-nums` for column-aligned values
- [ ] `pathly-pulse-border` injected once via `styleInjectedRef` (same pattern as FsmView)

**Edge Cases:** EC-2.6, EC-3.4 in EDGE_CASES.md

**Delivered by:** Phase 6 → Conversation 2

---

### Story S7: Last-Used Flow on Studio Open + Auto-Open Monitor

**As a** developer reopening Studio, **I want** the canvas to load the last-used flow automatically and the Monitor to open automatically if a flow is already running.

**Acceptance Criteria:**
- [ ] `lastUsedFlowPath` persisted to `localStorage` key `'pathly:lastUsedFlowPath'`
- [ ] ALL localStorage reads/writes wrapped in `try/catch` (can throw in sandboxed Electron contexts)
- [ ] On Studio open: if `lastUsedFlowPath` is set, load that flow file
- [ ] If flow file is missing: catch error, clear `lastUsedFlowPath`, show empty canvas hint (EC-2.5)
- [ ] If a flow is already running on open (`fsmState.current` not null/IDLE/DONE): `setActivePanel('monitor')` called once on mount
- [ ] First launch (no stored path): canvas shows empty state hint

**Edge Cases:** EC-2.5 in EDGE_CASES.md

**Delivered by:** Phase 4 → Conversation 1 (moved from Conv 2)

---

### Story S8: Blocked/Waiting State Amber Banner

**As a** developer monitoring a running pipeline, **I want** a clear visual indicator when an agent is blocked waiting for an artifact, **so that** I know why progress has stalled without having to scan the trace log.

**Acceptance Criteria:**
- [ ] Amber callout band renders between FSM rail and execution trace when `fsmState.waitingFor` is set
- [ ] Band shows: amber dot + agent name + artifact name + elapsed wait time since `fsmState.blockedSince`
- [ ] Colors: `BLOCKED_AMBER = '#FBBF24'` for dot and border; `rgba(251,191,36,0.08)` for background
- [ ] Band has `role="status"` + `aria-live="polite"` + accessible `aria-label`
- [ ] Band clears immediately when `fsmState.waitingFor` becomes null/undefined
- [ ] Only one blocked banner at a time (no stacking)
- [ ] If `fsmState.waitingFor` field is absent in current FSM version: band does not render; add TODO comment

**Edge Cases:** EC-5.3 in EDGE_CASES.md

**Delivered by:** Phase 7 → Conversation 2

---

### Story S9: Flow-Level Total Cost + Elapsed Time in Header

**As a** developer watching an AI pipeline, **I want** to see the total cost and elapsed time of the current flow run in the Monitor header, **so that** I can assess whether to let it continue or stop it.

**Acceptance Criteria:**
- [ ] Monitor header shows `$X.XX total` when AGENT_DONE events have `cost_usd` field
- [ ] Monitor header shows `⏱ Xm Xs` elapsed since first STATE_TRANSITION event
- [ ] Both are hidden if no cost/time data is available
- [ ] Both use `font-variant-numeric: tabular-nums`
- [ ] Elapsed time refreshes via `useInterval` 30s tick (same tick as trace timestamps)
- [ ] If `cost_usd` absent from events: cost display hidden entirely (same guard as S6)

**Delivered by:** Phase 8 → Conversation 2

---

## Deferred (Post-MVP — Explicitly Out of Scope)

These gaps were identified in the PO review (2026-05-20) and are real product needs. They are not in this plan:

| Story | Gap | Notes |
|---|---|---|
| **Stop/Cancel flow** | No way to halt a running flow from Studio | Highest-priority follow-on |
| **Error detail drill-down** | `✗` in trace shows failure but no error message | Critical for debugging; pair with stop/cancel |
| **Monitor tabs (S4)** | Multi-flow monitoring | Implement when production data shows concurrent-flow usage |
| **Completed-flow history** | Flow completed while Monitor closed — history not persisted | Depends on event store design |
