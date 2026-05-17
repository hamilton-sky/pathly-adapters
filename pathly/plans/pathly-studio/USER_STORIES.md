# USER_STORIES.md — pathly-studio

---

## S7 — Multi-project home screen

**As a** developer working on several repos that each use Pathly,
**I want** a home screen that lists all my known projects with their live pipeline
state,
**so that** I can see at a glance what is running and open any project in one click.

**Acceptance criteria:**
- App opens to home screen when no project is loaded (first launch or all windows closed)
- Home screen lists all previously opened projects (persisted in localStorage)
- Each row shows: project name (folder name), path, active topic name, current FSM state badge, time since last activity
- FSM state badge is read from `pathly/plans/*/STATE.json` at load time — no file watching on home screen
- `[→]` button opens the project in the current window; Cmd/Ctrl+click opens in a new Electron window
- `[+ Open project folder]` button opens a native folder picker dialog — adds the chosen path to the list
- Projects with no `pathly/plans/` folder show "— nothing in progress"
- Removing a project from the list does not delete any files

---

## S1 — Electron app launches and displays the shell

**As a** Pathly developer,
**I want** to open Pathly Studio as a native desktop app,
**so that** I can configure and monitor the pipeline without a browser or terminal.

**Acceptance criteria:**
- `npm run dev` inside `studio/` opens an Electron window
- Window shows sidebar on the left and an empty main panel on the right
- App reads `projectPath` from an env var or prompts on first launch
- Window title shows "Pathly Studio"

---

## S2 — Sidebar shows the Pathly content tree

**As a** developer,
**I want** a collapsible sidebar listing every agent, skill, template, and flow,
**so that** I can navigate to any file without opening a file browser.

**Acceptance criteria:**
- Sidebar sections: Flows / Skills / Agents / Templates / Monitor
- Each section lists items read from `src/pathly_data/core/` subdirectories
- Clicking a section header collapses or expands it
- Clicking an item in Flows/Skills/Agents/Templates opens it in the editor panel
- Clicking Monitor opens the monitor panel
- Sidebar collapse button (`[◄]`) hides the sidebar; `[►]` restores it
- Collapsed state persists across app restarts (stored in Zustand + localStorage)

---

## S3 — Editor: config form + markdown with Edit/Preview tabs

**As a** developer editing a skill or agent,
**I want** a config form at the top and a markdown editor below with Edit and Preview tabs,
**so that** I can update metadata and content without touching raw YAML or leaving the app.

**Acceptance criteria:**
- Config form parses YAML frontmatter (or a `## Config` section) from the file and renders fields: name, type, description, adapters (checkboxes: claude / codex / copilot), tools (comma list)
- Markdown area below the form shows raw content in Edit tab (CodeMirror, markdown syntax highlight)
- Preview tab renders markdown as HTML using marked.js — same output as GitHub README view
- Split pane button (`[⊟ Split]`) shows editor left + live preview right simultaneously
- Save button writes the updated file back via IPC — config form changes update the frontmatter, markdown changes update the body
- Unsaved changes show a dot indicator on the item in the sidebar

---

## S4 — Flow editor: visual graph + YAML tab

**As a** developer creating or editing a flow,
**I want** to see the FSM as a visual node/edge graph and toggle to raw YAML,
**so that** I can understand the flow structure at a glance and edit it precisely.

**Acceptance criteria:**
- Visual tab renders states as nodes and transitions as directed edges using ReactFlow
- Each node shows: state name, agent name
- Each edge shows: artifact trigger (if any) or "default"
- Clicking a node opens an inline edit panel: change agent name, add/remove transition_rules
- Clicking an edge opens an inline edit panel: change artifact trigger, add/remove transition_actions
- YAML tab shows the raw flow YAML in a CodeMirror editor with YAML syntax highlight
- Switching from YAML tab to Visual tab re-parses the YAML and re-renders the graph
- Save button writes YAML back to `src/pathly_data/core/flows/` via IPC
- Invalid YAML shows a red error banner — Save is disabled until fixed

---

## S5 — Live monitor: real-time FSM state and event log

**As a** developer running the pipeline,
**I want** to see the current FSM state and event history update in real time,
**so that** I know what is happening without opening any file.

**Acceptance criteria:**
- Topic selector in the top bar lists all folders under `pathly/plans/` (excluding `.archive/`)
- FSM progress bar shows all states in order; active state is highlighted; completed states are checked
- Event log shows entries from EVENTS.jsonl: `HH:MM:SS  EVENT_TYPE  detail`, newest at bottom
- Monitor auto-detects data source:
  - If MCP server responds to ping within 500ms → reads state via `get_fsm_state` MCP tool call
  - Otherwise → watches `pathly/plans/<topic>/STATE.json` and `EVENTS.jsonl` with chokidar
- Connection status badge in top bar: `● MCP live` (green) or `○ File watch` (grey)
- New events appear without manual refresh

---

## S6 — Publish: reinstall Python package

**As a** developer who edited skills or flows in the studio,
**I want** a Publish button that reinstalls the Python package,
**so that** my changes take effect in Claude/Codex immediately.

**Acceptance criteria:**
- Publish button in the top bar triggers `pip install -e .` run in the project root
- A log panel slides up showing streaming subprocess output line by line
- On success: "Published successfully" banner, log panel auto-hides after 3 seconds
- On failure: "Publish failed" banner, log panel stays open showing the error
- Publish button is disabled while a publish is already running
