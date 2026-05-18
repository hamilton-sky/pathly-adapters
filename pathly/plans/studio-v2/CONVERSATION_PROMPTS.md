# CONVERSATION_PROMPTS — studio-v2

Copy the prompt for the current conversation and paste it to start a builder session.

---

## Conv 1 — Quick fixes (S1, S7)

```
Route to build studio-v2 Conv 1.
Plan root: pathly/plans/studio-v2/
Stories: S1, S7

## Goal
Fix two known bugs: (1) pipeline state display in Monitor, (2) AGENT_DONE timestamp field in runner.py.

## Files to edit

### studio/src/renderer/src/components/Monitor/index.tsx
- Current regex: /states:\s*\n((?:[ \t]+-[ \t]+\S+\n?)+)/
- Problems:
  - Captures "- " bullet prefix as part of state name — strip it
  - CRLF line endings on Windows break the match — strip \r before applying regex
- Fix: strip \r from YAML string before regex; strip leading "- " and trim from each captured group; uppercase each state name

### src/pathly_orchestrator/runner.py
- All AGENT_DONE event writes use "timestamp" key instead of "ts"
- _patch_last_agent_done() also writes "timestamp"
- Fix: replace every "timestamp" key in event-writing code with "ts"
- Do NOT touch log_cli.py (its fallback is intentional for old files)
- Do NOT touch append_event() — it already writes "ts" correctly

## Acceptance checks (run after build)
- S1: Open Studio with a team topic; PIPELINE shows "STORMING", "PLANNING" etc. with no "- " prefix
- S1: Test with a CRLF YAML file; states still parse correctly
- S7: grep runner.py for '"timestamp"' — zero hits in event-writing code
- S7: Run a flow; EVENTS.jsonl AGENT_DONE lines contain "ts" key, not "timestamp"
```

---

## Conv 2 — Monitor improvements (S2, S6)

```
Route to build studio-v2 Conv 2.
Plan root: pathly/plans/studio-v2/
Stories: S2, S6
Depends on: Conv 1 complete

## Goal
Make Monitor work for all three flow types and add a contextual header bar.

## Files to edit

### studio/src/renderer/src/components/Monitor/index.tsx

**S2 — Dynamic base path:**
- Currently hardcodes: pathly/plans/${activeTopic}
- fsmState shape: { current, flow?, feature?, rigor?, current_conversation?, updated_at? }
- Build a helper: getBasePath(flow) → "pathly/plans/" | "pathly/debugs/" | "pathly/explorations/"
- Unknown flow values fall back to "pathly/plans/" with a console.warn
- Also load the correct flow YAML filename per flow type:
  - team → team.flow.yaml
  - debug → debug.flow.yaml
  - explore → explore.flow.yaml

**S6 — Header bar:**
- Add a header bar at the very top of the Monitor panel
- Data sources:
  - flow, feature (topic), current_state, current_conversation — from fsmState Zustand store
  - agent — from last AGENT_SPAWNED event in events array (field: event.agent)
- Exact layout:
  ─────────────────────────────────────────────────────────
    Pathly  ·  <flow>  ·  <topic>
    State : <current_state>    Conv : <N>
    Agent : <agent>
  ─────────────────────────────────────────────────────────
- Topic name truncates at 32 chars with ellipsis
- All fields show "—" when fsmState is empty or field is absent

## Acceptance checks
- S2: Switch active topic to a debug topic; Monitor loads from pathly/debugs/
- S2: Switch to exploration topic; Monitor loads from pathly/explorations/
- S2: fsmState.flow = "unknown" → console.warn fired, falls back to plans/
- S6: Header renders with correct flow/topic/state/conv/agent values
- S6: Header updates when FSM transitions (reactive)
- S6: No AGENT_SPAWNED event → Agent shows "—"
```

---

## Conv 3 — Sidebar restructure (S3, S4)

```
Route to build studio-v2 Conv 3.
Plan root: pathly/plans/studio-v2/
Stories: S3, S4
Depends on: Conv 1 complete

## Goal
Split Sidebar into Section A (Pathly-installed, always visible) and Section B (Workspace, project-dependent).

## Files to edit

### studio/src/renderer/src/hooks/useProjectFiles.ts
- Current: returns early on !projectPath — this makes all sections invisible without a project
- Split the hook into two logical parts:
  - Pathly-installed items: always load from ${projectPath}/src/pathly_data/core/{flows,skills,agents,templates}
    When projectPath is empty, return empty arrays (not undefined) for these sections
  - Workspace items: only load when projectPath is set — plans, debugs, explorations from
    ${projectPath}/pathly/{plans,debugs,explorations}
- Keep existing return shape compatible (extend it, don't break callers)

### studio/src/renderer/src/components/Sidebar/index.tsx
- Remove Plans from its current hardcoded top position
- Define two section groups:
  - Section A "Pathly": Flows, Skills, Agents, Templates
    Sources: pathly_data/core/flows, /skills, /agents, /templates
  - Section B "Workspace": Plans, Debugs, Explorations
    Sources: pathly/plans, pathly/debugs, pathly/explorations
- Render Section A first, then a visual separator (faint <hr> or labeled divider), then Section B
- Section B hides (or shows "(no project open)" placeholder) when projectPath is empty
- Section A always renders, even with empty arrays
- Plans in Section B shows conversations the same way the current hardcoded PLAN block does

## Acceptance checks
- S3: Launch with no project; Flows/Skills/Agents/Templates sections are visible (possibly empty)
- S3: No crash when projectPath is empty
- S4: Open a project; Plans, Debugs, Explorations appear in Section B below the separator
- S4: Section separator is always visible when both sections render
- S4: No orphaned separator when Section B is hidden
- S4: Plans conversations render correctly in Section B
```

---

## Conv 4 — HomeScreen all flows (S5)

```
Route to build studio-v2 Conv 4.
Plan root: pathly/plans/studio-v2/
Stories: S5
Depends on: Conv 3 complete

## Goal
HomeScreen lists topics from pathly/plans/, pathly/debugs/, and pathly/explorations/.

## Files to edit

### studio/src/renderer/src/components/HomeScreen/index.tsx
- Currently scans only pathly/plans/
- Add scans for pathly/debugs/ and pathly/explorations/
- Skip .archive/ subdirectory in all three roots
- For each topic, read STATE.json to get FSM state (show "—" if missing)
- Add a flow type badge to each topic row:
  - plans/ topics → "team"
  - debugs/ topics → "debug"
  - explorations/ topics → "explore"
- Display all topics in a unified list (or grouped by type — pick whichever is cleaner)
- If a root directory does not exist, skip it silently

### studio/src/renderer/src/hooks/useProjectFiles.ts (if scan logic lives here)
- Extend or reuse any existing scan helpers for the new roots

## Acceptance checks
- S5: With topics in all three roots: all appear on HomeScreen
- S5: Flow type badge is correct for each topic
- S5: .archive/ topics are not listed
- S5: Missing STATE.json → state badge shows "—", no crash
- S5: Non-existent root directory → no crash, no error panel
- S5: Two topics with the same name in different roots: both appear, distinguished by badge
```

---

## Conv 5 — Terminal panel (S8)

```
Route to build studio-v2 Conv 5.
Plan root: pathly/plans/studio-v2/
Stories: S8
Depends on: Conv 3 complete (App.tsx layout stable)

## Goal
Add a VS Code-style embedded terminal at the bottom of Studio.

## Files to create / edit

### studio/package.json
- Add dependencies: node-pty, xterm, xterm-addon-fit
- node-pty is a native module — ensure it is marked as external for the main process bundle

### studio/electron.vite.config.ts
- Add node-pty to externals for the main process build
- Verify xterm is bundled with the renderer (not external)

### studio/src/main/index.ts
- Add PTY lifecycle IPC handlers under the window.pathly.terminal.* namespace:
  - terminal:spawn(tabId, cwd) → spawns PowerShell PTY, returns tabId
  - terminal:write(tabId, data) → writes to PTY stdin
  - terminal:resize(tabId, cols, rows) → resizes PTY
  - terminal:kill(tabId) → kills PTY process
  - terminal:onData(tabId, callback) → streams output to renderer
- Spawn path: cwd = projectRoot if set, else app working directory
- Store active PTYs in a Map<tabId, IPty>

### studio/src/preload/index.ts
- Expose window.pathly.terminal.* bridge using the existing window.pathly.* pattern:
  - spawn, write, resize, kill, onData

### studio/src/renderer/src/store/terminalStore.ts (new file)
- Zustand store:
  - open: boolean
  - tabs: Array<{ id: string, label: string }>
  - activeTabId: string | null
  - toggle(), addTab(), closeTab(id), setActiveTab(id)

### studio/src/renderer/src/components/Terminal/index.tsx (new file)
- Tab bar: renders tab labels, + button, × close button per tab
- xterm.js Terminal instance per tab (use xterm-addon-fit for auto-resize)
- Drag handle on top border: mousedown → mousemove → update panel height (min 80px)
- Keyboard shortcut: Ctrl+` → call terminalStore.toggle()
- On tab create: call window.pathly.terminal.spawn(tabId, projectRoot)
- On data from PTY: write to xterm Terminal instance
- On panel close: do NOT kill PTYs (they survive collapse)
- On tab × close: call window.pathly.terminal.kill(tabId), remove from store
- If node-pty unavailable: catch IPC error, render error message in panel

### studio/src/renderer/src/components/TopBar/index.tsx
- Add "⌨" icon button that calls terminalStore.toggle()
- No other TopBar changes

### studio/src/renderer/src/App.tsx
- Layout: flex-column → [TopBar] → [body: flex-row sidebar + main] → [Terminal panel]
- Terminal panel is a flex sibling below body, not inside body
- Panel height is controlled by terminalStore / local resize state
- Panel renders only when terminalStore.open === true (but component stays mounted to preserve PTY connections)

## Acceptance checks
- S8: Ctrl+` toggles terminal open/closed
- S8: TopBar "⌨" button also toggles
- S8: Open terminal, type `echo hello` → output renders with ANSI color support
- S8: Close panel, reopen — PTY session still alive (shell prompt returns without restart)
- S8: Create 3 tabs, close middle tab — other tabs unaffected
- S8: Drag top border to resize — panel height changes; cannot go below 80px
- S8: node-pty unavailable — error message shown, renderer does not crash
- S8: Process exits inside tab — "[process exited]" shown in that tab only
```
