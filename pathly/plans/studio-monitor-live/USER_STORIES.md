# studio-monitor-live — User Stories

## Context

Pathly Studio has a working Monitor panel with SSE event streaming, an FsmView pipeline display, and a PlanBoard with conversation cards. The design spec (MONITOR_DESIGN_SPEC.md) has resolved all open UX questions and specifies a set of visual and functional upgrades: a connected FSM topology rail with a sliding dot, an execution trace below the rail, multi-flow monitor tabs, a running-flow entry banner, and richer plan conversation cards. This plan implements those spec decisions without touching the visual flow editor or sidebar (scope of `studio-visual-flow-builder`).

## Stories

### Story S1: FSM Topology Rail with Sliding Dot

**As a** developer watching a Pathly pipeline, **I want** a horizontal connected rail that shows all FSM states as nodes with a dot that slides to the active state, **so that** I can instantly see where the pipeline is at a glance without reading text labels.

**Acceptance Criteria:**
- [ ] Rail renders as a horizontal flex row with a thin line connecting state dots (not colored boxes)
- [ ] Active dot slides to the current state via CSS `transform: translateX` (150ms ease-out, no JS animation loop)
- [ ] Completed states: green filled dot; active: cyan filled with pulse; future: muted outline
- [ ] When a loop-back occurs the dot snaps back to the earlier state (activeIdx reflects current FSM state, not history)
- [ ] Debug/explore flows show `cycle N`; team flows show `conv N` in the header

**Edge Cases:**
- State not found in PIPELINE array: dot stays at last known position
- PIPELINE array empty: fall back to `['STORMING','PLANNING','BUILDING','REVIEWING','DONE']`

**Delivered by:** Phase 1 → Conversation 1

---

### Story S2: Execution Trace Below Rail

**As a** developer, **I want** a chronological execution trace below the rail, **so that** I can see every state visit in order — including loop re-visits — without losing history.

**Acceptance Criteria:**
- [ ] Trace renders below the rail as a scrollable list of rows
- [ ] Each row: `icon | STATE | conv/cycle N | agent | relative time`
- [ ] Status icons: `✓` completed, `●` active (pulsing), `✗` failed (REVIEW failures)
- [ ] Loop re-visits appear as additional rows (BUILDING visited twice = two rows)
- [ ] Trace reads from `STATE_TRANSITION` events in the store

**Edge Cases:**
- No events yet: show empty-state hint "Waiting for flow activity"
- Failed state (REVIEW with failures): show red `✗` for that row

**Delivered by:** Phase 2 → Conversation 1

---

### Story S3: SSE Live Source Badge

**As a** developer, **I want** a small live-source indicator in the Monitor header, **so that** I know immediately whether the monitor is receiving live SSE events or polling via file-watch.

**Acceptance Criteria:**
- [ ] `● live` (cyan dot, 11px, muted text) shown when SSE connected
- [ ] `○ polling` shown when SSE unavailable and monitor falls back to chokidar
- [ ] Badge visible in the Monitor header alongside flow/state info

**Edge Cases:**
- SSE reconnects after failure: badge switches back to `● live`

**Delivered by:** Phase 3 → Conversation 1

---

### Story S4: Monitor Tabs for Concurrent Flows

**As a** developer, **I want** a tab bar in the Monitor when multiple flows are active, **so that** I can watch and switch between concurrent pipelines without losing context.

**Acceptance Criteria:**
- [ ] Tab bar appears above monitor content when ≥1 active session exists
- [ ] Each tab shows flow filename + cyan `●` when running
- [ ] CLI-originated sessions show `>_` badge next to their name
- [ ] Clicking a tab switches the monitor display to that flow's state/trace
- [ ] No tab bar when only one flow is monitored (single-flow mode stays clean)

**Edge Cases:**
- >4 tabs: show `...` overflow menu
- Flow session ends: tab closes and monitor returns to remaining active flow

**Delivered by:** Phase 4 → Conversation 2

---

### Story S5: Running-Flow Entry Banner

**As a** developer, **I want** a non-blocking banner on the canvas when a flow is actively running, **so that** I don't miss an in-progress session when opening Studio or switching flows.

**Acceptance Criteria:**
- [ ] Banner shows: `[flow.yaml] is running ● cycle N / STATE`
- [ ] Cyan `●` dot for the running indicator
- [ ] "View in Monitor →" button switches bottom panel to Monitor tab
- [ ] Banner auto-dismisses after 8s if not interacted with
- [ ] `[dismiss]` button closes it immediately

**Edge Cases:**
- Multiple active flows: banner shows the most recently active one

**Delivered by:** Phase 5 → Conversation 2

---

### Story S6: Plan Conversation Cards Enhancement

**As a** developer reviewing a plan, **I want** conversation cards that show active pulsing, failure indicators, and cost data, **so that** I can assess plan progress at a glance without opening the event log.

**Acceptance Criteria:**
- [ ] Active card: pulsing cyan left border (3px, CSS animation)
- [ ] Failed card: red `✗` icon and red left border
- [ ] Pending card: muted `○` outline border
- [ ] Token/cost row shown when EVENTS.jsonl has AGENT_DONE cost data
- [ ] Relative timestamp shown (e.g., "2h ago", "running now")
- [ ] 52px min-height per card maintained

**Edge Cases:**
- No cost data in events: cost row hidden
- Active conv with no events yet: pulsing border but no cost row

**Delivered by:** Phase 6 → Conversation 2
