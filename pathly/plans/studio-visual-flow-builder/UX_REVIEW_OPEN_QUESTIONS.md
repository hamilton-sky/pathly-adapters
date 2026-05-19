# UX Review — Open Questions
> Pathly Studio · React + Electron + React Flow + CodeMirror
> Stack: Developer Tool / IDE → Dark Mode primary, Flat Design, dense operational surface
> Date: 2026-05-19

---

## Q1: Sidebar — Layout, Visual Style, and Section Behavior

### Recommendation

Keep the sidebar as a single scrollable column. Use **section headers with icon + label + count chip + collapse chevron + `+` action** on each row. Separate sections with 8px gap and a 1px `borderSubtle` divider, not a background fill.

Use the 6-dot grip icon (`⠿`, `GripVertical` in Lucide) instead of `::` — it reads as a drag affordance in any language and is smaller at small font sizes.

Item rows for draggable primitives (Skills, Agents): `grip | icon | name | type-badge`.
Items in Workspace (Plan, Monitor, Settings): `icon | label` — no grip, no badge. These are navigation destinations, not library primitives. Make them visually quieter: no drag cursor, slightly more padding.

Filter is **global** — one input at the top, collapses sections that have no hits. Per-section filters would fragment the scanning experience; the library is not large enough to need them.

Skills and Agents: **no sub-groupings in MVP**. A type badge (`skill` / `agent`) on each row is sufficient. Tags can be added in a follow-up once users request them.

### ASCII — Full Sidebar

```
+----------------------+
| 🔍  Filter...        |   ← global, collapses empty sections
+----------------------+
| ⬡ FLOWS          2 ∨ |   ← icon | label | count | chevron
|   debug.flow.yaml    |   ← no grip (not draggable), click = canvas load
|   team.flow.yaml     |
+- - - - - - - - - - - +   ← 1px borderSubtle + 8px gap
| ⚙ SKILLS         4 ∨ |
|  ⠿ ⚡ review.md  sk  |   ← grip | icon | name | badge
|  ⠿ ⚡ test.md    sk  |
|  ⠿ ⚡ write-doc  sk  |
+- - - - - - - - - - - +
| ◈ AGENTS          3 ∨ |
|  ⠿ ◈ planner.md  ag  |
|  ⠿ ◈ builder.md  ag  |
|  ⠿ ◈ reviewer.md ag  |
+- - - - - - - - - - - +
| ▦ TEMPLATES       2 ∧ |   ← collapsed by default
+- - - - - - - - - - - +
| ≡ WORKSPACE          |   ← collapsed by default, nav items only
|    Plan              |   ← no grip, no badge, lighter text
|    Monitor           |
|    Settings          |
+----------------------+
```

### Row anatomy (detail)

```
Draggable:  [ ⠿ ][ icon ][ name.md          ][ sk ]
            grip  type    file name            badge
            6px   16px    flex-1               28px pill

Nav only:   [      ][ icon ][ label            ]
            no grip  type    name
                     16px    flex-1
```

### Section header anatomy

```
[ icon ][ LABEL ][ count ]        [ + ][ ∨ ]
  16px   11px     muted chip     add  collapse
                  textMuted
```

### Behavior rules

| Rule | Detail |
|---|---|
| Collapse state | Persisted to localStorage per section |
| Section `+` button | Creates a new file of that type in the right directory |
| Drag affordance | Only on Skills and Agents rows. Flows, Workspace are click-only. |
| Item click | Skill/Agent → read-only preview in Editor. Flow → loads in canvas. Workspace → navigates. |
| Filter match | Highlights matching text; sections with zero hits auto-collapse |
| Empty section | Shows compact `+ add` inline, no large empty state illustration |
| Active flow indicator | Cyan `●` dot on any flow that is currently running (see Q6) |

---

## Q2: Entry Point — What Should Open First

### Recommendation: **Option A + D hybrid**

Load the **last-used flow in the canvas** (Option A). This is an operational IDE — users return to work in progress, not to browse. A home screen (Option C) is a marketing pattern and adds a click for no benefit.

**If a flow is already actively running when Studio opens**, automatically show the Monitor tab in the bottom panel and display a non-blocking banner on the canvas:

```
╔══════════════════════════════════════════════════════════╗
║  debug.flow.yaml is running  ●  conv 3 / BUILDING       ║
║  View in Monitor →                           [dismiss]  ║
╚══════════════════════════════════════════════════════════╝
```

This banner:
- Uses `runtime` cyan color (`#22D3EE`) for the `●` dot
- Auto-dismisses after 8s if the user doesn't interact
- Clicking "View in Monitor →" switches the bottom panel to the Monitor tab

### Decision table

| Scenario | Entry state |
|---|---|
| No active flows, last flow exists | Canvas with last-used flow loaded |
| No active flows, first launch | Canvas with empty state hint |
| Flow actively running | Canvas with last flow + running banner + Monitor auto-opened |
| Multiple flows running | Monitor tab shown; canvas shows last-edited flow |

---

## Q3: Monitor — Live Updates and Visual Design

### Architecture fix (technical)

The Monitor should subscribe to SSE/file-watcher events via `useEffect` with a cleanup function, NOT rely on re-renders:

```ts
useEffect(() => {
  const source = new EventSource('/api/flow-events');
  source.onmessage = (e) => dispatch(handleEvent(JSON.parse(e.data)));
  return () => source.close();
}, [flowId]);
```

The state rail must not re-mount on every event — only update the active node position. Use a ref-driven rail animation (CSS transition on `transform: translateX`), not a full re-render.

### Rail update behavior

When a transition fires:
1. The active dot slides along the rail (150ms ease-out CSS transform — no JS animation loop).
2. The previous state node changes color: active cyan → completed green (muted, `#16A34A` at 70% opacity).
3. The event is appended to the log below.

No full re-render. No flash. The rail is an SVG or a flex row of positioned elements — the dot moves, the nodes recolor in place.

### Loop / rework handling

**Do NOT try to show loops on the linear rail.** Loops break linear rail metaphors. Instead:

- The **rail shows the FSM topology** (fixed set of states from the YAML, left to right).
- The **execution trace** below the rail is a chronological list: each line is one state visit. When BUILDING is visited twice, it appears as two separate rows.
- The active dot on the rail snaps back to the earlier node when a loop occurs. This is correct — the rail shows WHERE we are now, not the full path history.

```
FSM topology (rail):
  ●─────────────●────────────●──────────●──────────●
PLANNING    BUILDING    REVIEWING    FIXING     DONE
                ↑ active (2nd visit)

Execution trace (log, below):
  ✓  PLANNING    conv 1    planner    2m ago
  ✓  BUILDING    conv 2    builder    1m ago
  ✗  REVIEWING   conv 3    reviewer   40s ago   → failed
  ✓  FIXING      conv 4    builder    20s ago
  ●  BUILDING    conv 5    builder    now        running
```

### ASCII — Monitor states

**(a) Empty state**
```
+---------------------------------------------------------------+
| Monitor                                    ○ No active flow  |
+---------------------------------------------------------------+
|                                                               |
|   ○ · · · · · · · · · ○                                      |
|                                                               |
|   Waiting for flow activity.                                  |
|   Start a flow with  pathly run team.flow.yaml               |
|   or open an existing session from the sidebar.              |
|                                                               |
+---------------------------------------------------------------+
```

**(b) Active flow mid-run**
```
+---------------------------------------------------------------+
| Monitor  [ team.flow.yaml ]        ● SSE live    conv 3 / 5  |
+---------------------------------------------------------------+
|                                                               |
|  ✓──────────✓────────────●──────────○──────────○             |
| PLAN     BUILD        REVIEW     FIX         DONE            |
|                          ↑                                   |
|              builder #3  ●  running                          |
|              waiting for: REVIEW_FAILURES.md                 |
+-------------------------------+-------------------------------+
| Execution trace               | Agent log                    |
| ✓ PLANNING   conv 1  1h ago   | builder #3                   |
| ✓ BUILDING   conv 2  45m ago  | 00:10  AGENT_DONE            |
| ● REVIEWING  conv 3  now      | 13.2k in  2.1k out  $0.03   |
+-------------------------------+-------------------------------+
```

**(c) Loop / rework state**
```
+---------------------------------------------------------------+
| Monitor  [ team.flow.yaml ]        ● SSE live    conv 5 / 5  |
+---------------------------------------------------------------+
|                                                               |
|  ✓──────────●────────────✗──────────✓                        |
| PLAN     BUILD        REVIEW      FIX          (DONE)        |
|              ↑ active (2nd visit)   ↺ reworked               |
|                                                               |
+---------------------------------------------------------------+
| ✓ PLANNING   conv 1                                           |
| ✓ BUILDING   conv 2   (1st)                                   |
| ✗ REVIEWING  conv 3   → failed, back to FIXING                |
| ✓ FIXING     conv 4                                           |
| ● BUILDING   conv 5   (2nd visit)  ← now                     |
+---------------------------------------------------------------+
```

### Source label

Keep it — but very small and muted (`textMuted`, 11px). Rename from `Source: SSE live` to just `● live` (cyan dot) or `○ polling`. It's diagnostic information that saves a lot of confusion when something isn't updating. Hide it by default in a future pass; for now keep it visible.

---

## Q4: Plan Section — Conversation Cards

### Recommendation: compact list-row cards with left status strip

Avoid large marketing cards. Use compact rows (~52px tall) with a 3px left border strip as the primary status indicator. This matches the graphite IDE aesthetic and fits more conversations in view without scrolling.

### Status encoding

| Status | Border color | Dot | Text treatment |
|---|---|---|---|
| Completed | `green #16A34A` (muted) | `✓` | `textSecondary`, normal weight |
| Active | `runtime #22D3EE` | `●` pulsing | `textPrimary`, medium weight |
| Pending | `borderSubtle` | `○` | `textMuted`, normal weight |
| Failed | `red #EF4444` | `✗` | `textPrimary`, red tint |

### ASCII — 3 conversation cards

```
+----------------------------------------------------------+
|                                                          |
|  ║ ✓  Conv 1 · Restore graph rendering          done     |
|  ║    planner + builder · Phase 1–3 · 2h ago             |
|  ║    18.4k in / 3.1k out · $0.047              [open]   |
|                                                          |
+----------------------------------------------------------+
|                                                          |
|  ║ ●  Conv 3 · Docked inspector + inspectors   active   |
|  ║    builder · Phase 8–10 · running now                 |
|  ║    12.1k in / 1.8k out · $0.031              [open]   |
|  (pulsing cyan left border)                              |
+----------------------------------------------------------+
|                                                          |
|  ║ ○  Conv 4 · YAML sync + export UI           pending  |
|  ║    Phase 12–14 · not started                          |
|  ║                                              [open]   |
|                                                          |
+----------------------------------------------------------+
```

### Card fields

| Field | Source | Display |
|---|---|---|
| Number + title | Plan metadata | `Conv N · Phase name` |
| Status | Plan progress state | Left border color + icon |
| Agent(s) | Conversation participants | Small muted label |
| Phase range | Which phases this conv covers | `Phase N–M` |
| Timestamp | Last activity | Relative time |
| Token cost | Accumulated cost | `Xk in / Yk out · $Z` |
| Open button | Navigation | Right-aligned, ghost button |

### Hover / selected states

- Hover: `bgSurface1` background fill, no border change
- Selected: `bgSurface1` + accent violet left border (replaces status border while selected)
- Never expand cards into a large accordion in the plan list — keep them scannable

---

## Q5: Debug and Exploration — Sidebar + Monitor

### Recommendation: YES — give them separate sidebar sections

Debug and Exploration are distinct workflow modes with different:
- Duration (debug = short loop, explore = discovery sprint)
- Agent count (debug = 1 agent, explore = 1 agent, team = N agents)
- Artifacts (debug produces NOTES.md loops, explore produces FINDINGS.md)

Mixing them under FLOWS creates confusion about what each item does when clicked.

### Proposed sidebar structure

```
+----------------------+
| ⬡ FLOWS           2 ∨ |   team workflows (multi-agent FSM)
|   team.flow.yaml     |
|   custom.flow.yaml   |
+- - - - - - - - - - - +
| ⬡ DEBUG           1 ∨ |   Bug icon (Lucide: `Bug`)
|   debug.flow.yaml  ● |   ← cyan dot = currently running
+- - - - - - - - - - - +
| ⬡ EXPLORE         1 ∨ |   Compass icon (Lucide: `Compass`)
|   explore.flow.yaml  |
+----------------------+
```

**Icon differentiation:**
- FLOWS → `GitBranch` or `Workflow` (multi-node graph)
- DEBUG → `Bug` (single-agent loop)
- EXPLORE → `Compass` or `Search` (discovery)

These three modes map to distinctly different runtime behaviors and should be first-class citizens in the sidebar, not sub-items.

### Monitor rail — debug vs team flow

Debug sessions do NOT have a multi-state FSM rail. They loop on a single state. Use a **loop counter display** instead:

```
+--------------------------------------------------------------+
| Monitor  [ debug.flow.yaml ]      ● SSE live    iter 4 / ?  |
+--------------------------------------------------------------+
|                                                              |
|  ↺ ──────────────────────────── ↺                           |
|     DEBUG LOOP · builder                                     |
|     iteration 4 · started 3m ago                            |
|     waiting for: NOTES.md                                    |
|                                                              |
+-------------------------------+------------------------------+
| Loop history                  | Log                         |
| ✓ iter 1  fixed typo  40s     | builder #4                  |
| ✓ iter 2  added test  35s     | 00:02  AGENT_DONE           |
| ✓ iter 3  refactor    28s     | 4.1k in  0.8k out  $0.008  |
| ● iter 4  running             |                             |
+-------------------------------+------------------------------+
```

For explore sessions, use the same loop display with `EXPLORE` label and `Compass` icon.

The **visual distinction** between flow types in the monitor:
- Team flow: linear state rail (FSM topology)
- Debug flow: loop spinner + iteration counter
- Explore flow: loop spinner + iteration counter + "discoveries" count

---

## Q6: Multiple Concurrent Flows

### Recommendation: Tabbed monitor + sidebar activity badges

This is the hardest problem. The right answer for an operational IDE is **tabs in the Monitor panel**, NOT split view (too cramped) and NOT single-flow-only (loses important runtime info).

### Monitor with tabs

```
+--------------------------------------------------------------+
| ┌ team.flow.yaml ●  ┐┌ debug.flow.yaml ● ┐                  |
| │ (active tab)      ││                   │                  |
| └────────────────────┘└───────────────────┘                  |
+--------------------------------------------------------------+
| (content of active tab — full-width rail or loop display)   |
+--------------------------------------------------------------+
```

Tab behavior:
- Each running flow gets a tab
- Tabs show flow name + a cyan `●` dot when running
- Clicking the sidebar flow item also switches to its monitor tab
- Non-running flows have no tab (tabs appear only for active sessions)
- Max ~4 tabs before overflow → `...` overflow menu

### CLI-originated flow discovery

If a CLI session starts a flow that Studio doesn't know about, the sidebar must surface it. Approach:

1. Studio watches the Pathly project directory for active session markers (a lock/pid file written by the CLI).
2. When a new session is detected, the relevant sidebar section shows a **`+ 1 CLI session`** notification row:

```
+----------------------+
| ⬡ DEBUG           2 ∨ |
|   debug.flow.yaml  ● |
|   ▸ 1 CLI session    |   ← muted discovery row, click to adopt
+----------------------+
```

3. Clicking "1 CLI session" attaches Studio to that session and opens a monitor tab for it.

### Visual language for CLI-originated flows

CLI-originated sessions get a `>_` terminal badge next to their name in the sidebar and in the monitor tab:

```
| ⬡ DEBUG           2 ∨ |
|   debug.flow.yaml  ● |         ← Studio-launched
|   my-script  >_  ●  |         ← CLI-launched (terminal badge)
```

In the monitor tab bar:
```
┌ team.flow.yaml ● ┐┌ debug >_ ● ┐
```

The `>_` badge means: "this session was not started from Studio; Studio is observing it."

### Sidebar with multiple active sessions

```
+----------------------+
| ⬡ FLOWS           2 ∨ |
|   team.flow.yaml   ● |   ← running (cyan dot)
|   custom.flow.yaml   |
+- - - - - - - - - - - +
| ⬡ DEBUG           2 ∨ |
|   debug.flow.yaml  ● |   ← running
|   explore.flow >_  ● |   ← CLI-launched, running
+----------------------+
```

Cyan dot rules:
- `●` (solid cyan) = actively running right now
- `◐` (half-filled) = paused / waiting for artifact
- `○` (empty) = not running

### Two concurrent flows in monitor (team + debug)

```
┌ team.flow.yaml ● ┐┌ debug.flow.yaml ● ┐
│                                         │
│  FSM Rail (team):                       │
│  ✓───────✓───────●───────○───────○      │
│  PLAN  BUILD  REVIEW  FIX   DONE        │
│                  ↑ reviewer #2          │
│                                         │
│  [switch to debug tab]                  │
└─────────────────────────────────────────┘
```

When debug tab is selected:
```
┌ team.flow.yaml ● ┐┌ debug.flow.yaml ● ┐
│                                         │
│  Debug loop:                            │
│  ↺ ───────────────── ↺                 │
│     iteration 7 · builder              │
│     running for 12s                    │
└─────────────────────────────────────────┘
```

---

## Summary — Decisions to Capture in IMPLEMENTATION_PLAN

| Area | Decision | Target phase |
|---|---|---|
| Sidebar | 6-dot grip icon (GripVertical), global filter, separate DEBUG + EXPLORE sections | Phase 4–6 |
| Sidebar | Workspace = nav-only rows (no grip, no badge) | Phase 4 |
| Entry point | Last-used flow + running banner if active | Phase 8 (or new entry phase) |
| Monitor live | useEffect + EventSource, no re-render on each event | Phase 12 |
| Monitor rail | FSM topology rail; execution trace below; loop = counter not extended rail | Phase 12 |
| Monitor tabs | Tabbed by flow; appears on first active session | Phase 12 |
| CLI discovery | pid/lock file watcher; "+ N CLI session" discovery row | Post-MVP (flag for later) |
| Plan cards | Compact 52px rows, 3px left status strip, left-to-right: status / title / meta / cost / open | Phase 8 (Plan section) |
| Debug/Explore | Own sidebar sections with Bug/Compass icons; loop counter in monitor, not FSM rail | Phase 4 + Phase 12 |
| Multi-flow | Monitor tabs; sidebar cyan dot `●` for running; `>_` badge for CLI-originated | Phase 12 |
