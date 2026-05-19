# UX Review — Open Questions
> Pathly Studio · React + Electron + React Flow + CodeMirror
> Stack: Developer Tool / IDE → Dark Mode primary, Flat Design, dense operational surface
> Date: 2026-05-19
> Updated: 2026-05-19 — Q1 and Q5 revised after filesystem-tree sidebar model adopted

---

## Q1: Sidebar — Filesystem-Tree Model with Full CRUD

### Mental model correction (supersedes original Q1)

The sidebar is **not a static list of flat items** — it is a **filesystem-mirroring tree**, one per domain section. Each section maps directly to a directory on disk:

| Section | Directory | File types |
|---|---|---|
| SKILLS | `skills/` | `.md` files + category folders |
| AGENTS | `agents/` | `.md` files + category folders |
| FLOWS | `flows/` | `.flow.yaml` files + category folders |
| TEMPLATES | `templates/` | `.md` files + category folders |
| WORKSPACE | (nav only) | Plan, Monitor, Settings — not filesystem |

Users can create files, create category folders, rename, delete, and drag items within their section. **No cross-section operations** — a skill cannot be moved into agents.

Reference implementation: ZakaMurai sidebar (`Sidebar.js` + `TreeItem.js`) — same author, same stack. The Pathly sidebar adapts this pattern with domain constraints.

### Section header anatomy

Hover-reveal create actions. At rest: clean header. On hover: two action icons appear flush-right.

```
AT REST:
  ▼ SKILLS

ON HOVER:
  ▼ SKILLS                    [🔧+] [📁+]
                               new   new
                               file  category
```

Icon per section (replaces generic file icon):
- SKILLS: `Wrench` for new file
- AGENTS: `Bot` for new file
- FLOWS: `Workflow` (cyan) for new flow
- TEMPLATES: `FileText` for new file
- All sections: `Folder` for new category

The collapse chevron (`▸`/`▼`) is a separate click target from the label. Label text has no click behavior.

### Row anatomy — the dual-drag problem

Skills and Agents rows have **two drag behaviors that must be visually distinct**:

1. **Canvas drag** (`⠿` grip): drag onto the React Flow canvas to assign behavior to a state node
2. **Tree reorg drag** (row body): drag within the section to move into a category folder

```
SKILL ROW AT REST:
  ⠿  🔧  review.md

SKILL ROW ON HOVER:
  ⠿  🔧  review.md              [🔧+] [📁+]
  ↑                              ↑
  canvas-drag grip               section create actions
  always visible on skills/agents  hover-reveal only
```

- `⠿` grip: always visible on skill/agent rows. Color `textMuted #687588` at rest, violet `#8B5CF6` on grip-hover. Cursor `grab` → `grabbing`. Initiates **canvas drag**.
- Row body: draggable attribute for **tree reorg drag only**. Cursor `move` during drag initiation.
- FLOWS rows: no `⠿` grip (flows are not canvas-assignable). Row click = open flow in canvas editor. Row is still reorg-draggable within FLOWS section.

### Drag constraints — cross-section behavior

- When drag starts from `⠿` grip: `dragType = 'canvas'`. Tree reorg logic ignores it entirely. Canvas highlights as drop target.
- When drag starts from row body: `dragType = 'reorg'`. Drag payload carries `sectionId`. Drop handlers reject payloads with mismatched `sectionId`.
- Foreign sections during reorg drag: **no highlight, no red tint** — just inert. `cursor: not-allowed` from `dropEffect = 'none'`. Red would read as destructive; absence is the correct signal.
- Valid drop targets within own section: folder rows show `border-left: 2px solid #8B5CF6` + `rgba(139,92,246,0.08)` background tint.

### Inline create UX

When "New skill file" is triggered inside a folder:
- Inline input row appears as a child of that folder (or section root if no folder selected)
- Input is empty; ghost text shows the section-appropriate extension after the cursor: `.md` or `.flow.yaml`
- `Enter`: append ghost extension if user hasn't typed one → `review.md`
- If user types extension themselves: ghost disappears, name used as-is
- If user types wrong extension: inline error in `#EF4444` — "Skills must be .md files" — input stays open, no auto-rename
- `Escape`: cancel, remove input row
- Empty + `Enter`: no-op

```
INLINE INPUT (inside writing/ folder):
  ▼ 📁 writing/
    🔧 summarize.md
    [ research_____    .md ]    ← cursor, ghost ext dim after bracket
```

### Domain icon map

| Section | Folder icon | File icon | File icon color |
|---|---|---|---|
| SKILLS | `Folder` violet | `Wrench` | `textMuted #687588` |
| AGENTS | `Folder` violet | `Bot` | `textMuted #687588` |
| FLOWS | `Folder` violet | `Workflow` | `runtime #22D3EE` ← cyan signals runtime object |
| TEMPLATES | `Folder` violet | `FileText` | `textMuted #687588` |

Flow files use cyan because they are runtime objects (they execute on the canvas), not static content. This matches the cyan used elsewhere for runtime state.

### Context menus (right-click)

**Section root header:**
```
  🔧 New skill file
  📁 New category
```

**Category folder:**
```
  🔧 New skill file
  📁 New subcategory
  ─────────────────
  ✏  Rename
  ─────────────────
  🗑  Delete          ← always available; dialog shows file count
```

**Skill / Agent file:**
```
  👁  Open preview
  ─────────────────
  ✏  Rename
  →  Move to…        ← submenu: categories in section + "/ Root"
  ─────────────────
  🗑  Delete
```

**Flow file:**
```
  ⚡ Open in canvas
  👁  Open source (YAML)
  ─────────────────
  ✏  Rename
  →  Move to…
  ─────────────────
  🗑  Delete
```

### Empty section state

No auto-collapse. Two-line muted hint:

```
  ▼ SKILLS                    [🔧+] [📁+]
    No skills yet
    Click + to create one
```

### Full sidebar ASCII

**At rest:**
```
┌──────────────────────────────────────┐
│  🔍  Filter...                       │  ← global search
├──────────────────────────────────────┤
│  ▼ SKILLS                            │
│    ▼ 📁 writing/                     │
│      ⠿  🔧 summarize.md             │
│      ⠿  🔧 rewrite.md               │
│    ⠿  🔧 draft-email.md             │
│                                      │
│  ▶ AGENTS                            │
│                                      │
│  ▼ FLOWS                             │
│    ⚡ team.flow.yaml                 │
│    ⚡ debug.flow.yaml                │
│                                      │
│  ▶ TEMPLATES                         │
│                                      │
├──────────────────────────────────────┤
│  WORKSPACE                           │
│  📋 Plan                             │
│  📡 Monitor                          │
│  ⚙  Settings                         │
└──────────────────────────────────────┘
```

**Drag reorg state** — `rewrite.md` being moved into `writing/`:
```
│  ▼ SKILLS                            │
│    ▼ 📁 writing/  ◄─ drop target    │  ← violet left border + 8% violet bg
│      ⠿  🔧 summarize.md             │
│    [ghost: rewrite.md]               │  ← dragging
│                                      │
│  ▶ AGENTS                            │  ← inert, no highlight
```

---

## Q2: Entry Point — What Should Open First

### Recommendation: **Option A + D hybrid**

Load the **last-used flow in the canvas** (Option A). This is an operational IDE — users return to work in progress, not to browse. A home screen (Option C) is a marketing pattern and adds a click for no benefit.

**If a flow is already actively running when Studio opens**, automatically show the Monitor tab in the bottom panel and display a non-blocking banner on the canvas:

```
╔══════════════════════════════════════════════════════════╗
║  debug.flow.yaml is running  ●  cycle 3 / BUILDING      ║
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

## Q5: Debug and Exploration — Sidebar and Monitor

### Sidebar: all flows live in FLOWS section (corrected)

Debug and Explore flows are the same technical artifact as team flows — Pathly FSM YAMLs. The difference is convention, not structure. **No separate DEBUG / EXPLORE sidebar sections.**

Users organize flows with category folders inside the FLOWS section:

```
  ▼ FLOWS
    ▼ 📁 debug/
      ⚡ debug.flow.yaml
    ▼ 📁 team/
      ⚡ team.flow.yaml
    ⚡ explore.flow.yaml     ← uncategorized at root
```

### Monitor: ALL flows use the FSM topology rail (correction)

The "loop counter" concept was wrong. A debug flow like `debug.flow.yaml` is a real multi-state FSM — it has states like TESTING → BUILDING → REVIEWING → back to TESTING. That is not a single-state loop; it is a proper FSM that cycles. The FSM topology rail is correct for it.

```
debug.flow.yaml states:
  TESTING → BUILDING → REVIEWING → (loops back to TESTING if issues remain)
```

**All flows — team, debug, explore — use the same FSM topology rail.** The differences are:
- Fewer states (debug/explore typically have 3–4 vs team's 5–7)
- The loop-back edge is more frequent and expected (the dot snaps back to TESTING when REVIEWING finds issues)
- The flow file name in the monitor tab label tells the user which flow type they're watching

The loop-back behavior on the rail is already handled by the Q3 design: the active dot snaps back to the earlier state when a loop-back transition fires. The execution trace below the rail records each visit chronologically, so TESTING visited twice shows as two rows.

```
Monitor  [ debug.flow.yaml ]      ● SSE live    cycle 3

  ✓─────────────✗─────────────●
TESTING     BUILDING      REVIEWING
                ↑ active (3rd visit)   ↺ looped back from REVIEWING

Execution trace:
  ✓ TESTING    cycle 1   tester    2m ago
  ✓ BUILDING   cycle 1   builder   1m ago
  ✗ REVIEWING  cycle 1   reviewer  50s ago  → issues found, retry
  ✓ TESTING    cycle 2   tester    40s ago
  ✓ BUILDING   cycle 2   builder   25s ago
  ● REVIEWING  cycle 2   reviewer  now
```

The monitor tab shows `cycle N` instead of `conv N` for debug/explore flows, since those flows loop rather than advance linearly. This is a label-only change — the rail and trace work identically.

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
2. When a new session is detected, the FLOWS section shows a **`+ 1 CLI session`** notification row under the relevant folder (or at root if unknown):

```
+----------------------+
| ▼ FLOWS              |
|   ▼ 📁 debug/        |
|     ⚡ debug.flow.yaml ● |
|     ▸ 1 CLI session    |   ← muted discovery row, click to adopt
+----------------------+
```

3. Clicking "1 CLI session" attaches Studio to that session and opens a monitor tab for it.

### Visual language for CLI-originated flows

CLI-originated sessions get a `>_` terminal badge next to their name in the sidebar and in the monitor tab:

```
| ▼ FLOWS              |
|   ▼ 📁 debug/        |
|     ⚡ debug.flow.yaml ● |   ← Studio-launched
|     ⚡ my-script  >_  ● |   ← CLI-launched (terminal badge)
```

In the monitor tab bar:
```
┌ team.flow.yaml ● ┐┌ debug >_ ● ┐
```

The `>_` badge means: "this session was not started from Studio; Studio is observing it."

### Sidebar with multiple active sessions

All flows live in the single FLOWS section, organized by user-created category folders.

```
+----------------------+
| ▼ FLOWS              |
|   ▼ 📁 team/         |
|     ⚡ team.flow.yaml ● |   ← running (cyan dot)
|   ▼ 📁 debug/        |
|     ⚡ debug.flow.yaml ● |  ← running
|     ⚡ explore.flow >_ ● |  ← CLI-launched, running
|   ⚡ custom.flow.yaml   |
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

When debug tab is selected (same FSM topology rail — debug flows are real FSMs):
```
┌ team.flow.yaml ● ┐┌ debug.flow.yaml ● ┐
│                                         │
│  FSM Rail (debug):       cycle 7        │
│  ●──────────✓────────────●              │
│  TEST     BUILD       REVIEW            │
│   ↑ active (7th visit)  ↺ looped back  │
│                                         │
│  tester #7 · running for 12s           │
└─────────────────────────────────────────┘
```

---

## Summary — Decisions to Capture in IMPLEMENTATION_PLAN

| Area | Decision | Target phase |
|---|---|---|
| **Sidebar model** | Filesystem-mirror tree per section (skills/, agents/, flows/, templates/) | Phase 4–6 |
| **Sidebar CRUD** | Create file, create folder, rename (double-click inline), delete (dialog), move (drag within section) | Phase 4–6 — scope-expanding, see note |
| **Dual drag** | `⠿` grip = canvas drag; row body = tree reorg drag within section only | Phase 6 |
| **Cross-section drag** | Foreign sections inert (no tint, `not-allowed` cursor); `sectionId` on drag payload | Phase 6 |
| **Domain icons** | Wrench/Bot/Workflow/FileText per section; standard Folder for categories; cyan for flow files | Phase 4 |
| **Inline create** | Ghost extension after cursor; auto-append stem; warn on wrong extension | Phase 5–6 |
| **Context menu** | Per item type (section root / folder / skill+agent / flow) — see Q1 spec | Phase 6 |
| **Empty section** | Two-line muted hint; no auto-collapse | Phase 6 |
| **Debug/Explore sidebar** | All flows in FLOWS section; users organize with category folders — no separate sections | Phase 4 |
| **Monitor display** | All flows (team, debug, explore) use FSM topology rail + execution trace. Debug/explore show `cycle N` not `conv N`. Loop-back = dot snaps back on rail. | studio-monitor-live plan |
| **Workspace section** | Nav-only rows (Plan, Monitor, Settings) — not filesystem, no drag | Phase 4 |
| **Entry point** | Last-used flow + running banner if active | studio-monitor-live plan |
| **Monitor live** | useEffect + EventSource, no re-render on each event | studio-monitor-live plan |
| **Monitor rail** | FSM topology rail; execution trace below; loop-back = dot snaps back on rail; `cycle N` label for looping flows | studio-monitor-live plan |
| **Monitor tabs** | Tabbed by flow; appears on first active session | studio-monitor-live plan |
| **Plan cards** | Compact 52px rows, 3px left status strip | studio-monitor-live plan |
| **Multi-flow** | Monitor tabs; cyan `●` for running; `>_` badge for CLI-originated | studio-monitor-live plan |
| **CLI discovery** | pid/lock file watcher; "+ N CLI session" discovery row | Post-MVP |

### Note on scope impact

The filesystem-tree sidebar (CRUD + dual drag + context menu + inline create) is **significantly larger** than the original Phase 4–6 scope (which only covered drag metadata + canvas drop). This work needs either:
- **2–3 additional phases in Conversation 2**, pushing Conversation 2 from 4 phases to 6–7
- **Or a separate `studio-sidebar-tree` plan** (1–2 conversations) run before or after the flow builder

Recommendation: add the phases to Conversation 2. The sidebar is a prerequisite for the canvas drag behavior anyway, and keeping it in the same plan avoids coordination overhead. See plan update needed in IMPLEMENTATION_PLAN.md.
