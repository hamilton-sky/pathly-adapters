# studio-monitor-live — User Stories

## Context

Pathly Studio has a working Monitor panel with SSE event streaming, an FsmView pipeline display, and a PlanBoard with conversation cards. The design spec (MONITOR_DESIGN_SPEC.md) has resolved all open UX questions and specifies a set of visual and functional upgrades: a connected FSM topology rail with a sliding dot, an execution trace below the rail, multi-flow monitor tabs, a running-flow entry banner, and richer plan conversation cards. This plan implements those spec decisions without touching the visual flow editor or sidebar (scope of `studio-visual-flow-builder`).

## Stories

### Story S1: FSM Topology Rail with Sliding Dot

**As a** developer watching a Pathly pipeline, **I want** a horizontal connected rail that shows all FSM states as nodes with a dot that slides to the active state, **so that** I can instantly see where the pipeline is at a glance without reading text labels.

**Acceptance Criteria:**
- [ ] Rail renders as a horizontal flex row with a thin 1px line connecting state dots (not colored boxes)
- [ ] Active dot slides to the current state via CSS `transform: translateX` (150ms ease-out, no JS animation loop, ref-driven)
- [ ] Completed dots: green filled; active: cyan filled with pulse; future: muted outline
- [ ] When a loop-back occurs the dot snaps back to the earlier state (activeIdx = `PIPELINE.indexOf(fsmState.current)` — single-index lookup, no history tracking)
- [ ] Debug/explore flows show `cycle N`; team flows show `conv N` in the header (`fsmState.flow === 'debug' || fsmState.flow === 'explore'`)
- [ ] `t.runtime` theme token (`#22D3EE`) is confirmed/added to `theme.ts` before use

**Edge Cases:**
- State not found in PIPELINE array: dot stays at last known position
- PIPELINE array empty: fall back to `['STORMING','PLANNING','BUILDING','REVIEWING','DONE']`
- Custom flow names (not `team`/`debug`/`explore`): fall back to `conv N` label

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Execution Trace Below Rail

**As a** developer, **I want** a chronological execution trace below the rail, **so that** I can see every state visit in order — including loop re-visits — without losing history.

**Acceptance Criteria:**
- [ ] Trace renders below the rail as a scrollable list of rows
- [ ] Each row: `icon | STATE | conv/cycle N | agent | relative time`
- [ ] Status icons: `✓` completed (green), `●` active (cyan, pulsing), `✗` failed (red)
- [ ] Loop re-visits appear as additional rows (BUILDING visited twice = two rows)
- [ ] Trace reads from `STATE_TRANSITION` events in the store
- [ ] Failure detection uses `pipelineStates` order (backward transition = failed), NOT hardcoded state names like "FIXING"
- [ ] Empty state: single muted line "Waiting for flow activity."
- [ ] `formatRelativeTime(ts)` helper created in Conv 1 ("now" <60s, "Xm ago", "Xh ago")
- [ ] Agent per row derived from nearest AGENT_SPAWNED after the STATE_TRANSITION; eventual-consistency acceptable (may show previous agent for one frame)

**Edge Cases:**
- EVENTS.jsonl initial load can race with live SSE appends (pre-existing bug); trace must not crash on reorder
- No AGENT_SPAWNED found for a visit: show `—` for agent column

**Delivered by:** Phase 2 → Conversation 1

---

### Story S3: SSE Live Source Badge

**As a** developer, **I want** a small live-source indicator in the Monitor header, **so that** I know immediately whether the monitor is receiving live SSE events or polling via file-watch.

**Acceptance Criteria:**
- [ ] `● live` (cyan `t.runtime`, 11px) shown when `monitorSource === 'sse'`
- [ ] `○ polling` (textMuted, 11px) shown when `monitorSource === 'chokidar'`
- [ ] `—` (textMuted) shown when `monitorSource` is `null` (not yet connected)
- [ ] Any existing `Source: SSE live` text label removed from the header
- [ ] Badge visible in the Monitor header flush-right in the title row

**Edge Cases:**
- SSE reconnects after failure: badge switches back to `● live`
- `projectPath` missing: `monitorSource` stays null → badge shows `—`

**Delivered by:** Phase 3 → Conversation 1

---

### Story S4: Monitor Tabs for Concurrent Flows

**As a** developer, **I want** a tab bar in the Monitor when multiple flows are active, **so that** I can watch and switch between concurrent pipelines without losing context.

**Acceptance Criteria:**
- [ ] Tab bar appears when **≥2** active Studio-launched sessions are tracked in `activeFlowSessions`
- [ ] No tab bar when 0 or 1 session (single-flow stays clean; existing `activeTopic` path unchanged)
- [ ] Each tab shows flow filename + cyan `●` when `isRunning: true`
- [ ] `◐` (half-filled, muted) shown for paused/waiting sessions (`isPaused: true`)
- [ ] Clicking a tab: sets `activeMonitorTab` AND re-keys the SSE subscription to that session's topic
- [ ] >4 tabs: `...` overflow button opens a simple dropdown list
- [ ] `isCli` field defaults to `false` in all sessions (CLI discovery is Post-MVP; no `>_` badge yet)
- [ ] `activeFlowSessions` is populated from `activeTopic` + `fsmState` when a flow is running (Studio-launched sessions only)

**Edge Cases:**
- Session ends: tab closes; monitor returns to remaining active session
- No active sessions: tab bar hidden; Monitor shows "Select a topic" placeholder

**Delivered by:** Phase 4 → Conversation 2

---

### Story S5: Running-Flow Entry Banner

**As a** developer, **I want** a non-blocking banner on the canvas when a flow is actively running, **so that** I don't miss an in-progress session when switching to the canvas view.

**Acceptance Criteria:**
- [ ] Banner shows when `fsmState.current` is non-null and not `IDLE`/`DONE` and only **one** flow is active
- [ ] Banner content: `[flow.yaml] is running ● conv N / STATE  [View in Monitor →]  [dismiss]`
- [ ] Cyan `●` dot (`t.runtime #22D3EE`) for the running indicator
- [ ] `[View in Monitor →]` calls `setActivePanel('monitor')` — switches to Monitor view
- [ ] Banner auto-dismisses after 8s if not interacted with
- [ ] `[dismiss]` button closes it immediately
- [ ] `dismissed` state resets when `activeTopic` changes OR when `fsmState.current` transitions from non-running → running again (re-show on new run)
- [ ] When **multiple** flows are active: no banner; `setActivePanel('monitor')` is called automatically on load
- [ ] Banner styled: `bgSurface1` background, 1px `t.runtime` border
- [ ] z-index uses `Z.toast - 1` from `FlowEditor/zIndex.ts` (Phase 7b of studio-visual-flow-builder must be complete)

**Edge Cases:**
- Flow stops and restarts: banner re-appears (dismissed flag resets on running→IDLE→running cycle)

**Delivered by:** Phase 5 → Conversation 2

---

### Story S6: Plan Conversation Cards Enhancement

**As a** developer reviewing a plan, **I want** conversation cards that show active pulsing, failure indicators, cost data, hover/selected states, and timestamps, **so that** I can assess plan progress at a glance without opening the event log.

**Acceptance Criteria:**
- [ ] Active card: pulsing cyan left border (3px, CSS animation, same `pathly-pulse` class pattern as FsmView)
- [ ] Failed card: red `✗` icon and red left border (`#EF4444`)
- [ ] Pending card: muted `○` outline border
- [ ] Hover state: `bgSurface1` background fill (no border change)
- [ ] Selected state: `bgSurface1` + accent violet left border (replaces status border)
- [ ] Token/cost row shown when `EVENTS.jsonl` has `AGENT_DONE` events with `cost_usd` for that conv number
- [ ] Cost filtered by `e.conversation === conv.num` (confirm `conversation` field is populated in EVENTS.jsonl)
- [ ] Relative timestamp shown from most recent event `ts` for that conv
- [ ] Phase range shown if `ConvRow.phases` is populated (requires `parseProgressMd` update)
- [ ] 52px min-height per card

**Edge Cases:**
- No cost data: cost row hidden
- Active conv with no events yet: pulsing border, no cost row

**Delivered by:** Phase 6 → Conversation 2

---

### Story S7: Last-Used Flow on Studio Open + Auto-Open Monitor

**As a** developer reopening Studio, **I want** the canvas to load the last-used flow automatically and the Monitor to open automatically if a flow is already running, **so that** I resume work immediately without navigating to find my in-progress session.

**Acceptance Criteria:**
- [ ] On Studio open, the last-used flow file is loaded in the canvas (persisted across sessions)
- [ ] If a flow is already actively running when Studio opens (`fsmState.current` not null/IDLE/DONE), `setActivePanel('monitor')` is called automatically
- [ ] If no flow is running: canvas opens with last-used flow; no automatic panel switch
- [ ] First-launch (no last-used flow): canvas shows empty state hint

**Edge Cases:**
- Last-used flow file deleted since last session: canvas shows empty state hint
- Multiple flows running on open: Monitor tab bar shown; canvas shows last-edited flow

**Delivered by:** Phase 7 → Conversation 2
