# USER_STORIES — studio-v2

---

## S1 — Fix pipeline display in Monitor

**Delivered by:** Conv 1

**As** a developer monitoring a running flow,
**I want** the PIPELINE section to show state names like `STORMING`, `PLANNING`,
**so that** I can read them at a glance without manual string parsing.

**Root cause (from scout findings):**
The regex `/states:\s*\n((?:[ \t]+-[ \t]+\S+\n?)+)/` captures the `- ` bullet prefix
as part of each state name. On Windows, CRLF line endings may also prevent the regex
from matching at all.

**Acceptance criteria:**
- [ ] Each state in the PIPELINE section displays in UPPERCASE with no leading `- `.
- [ ] The regex correctly matches state blocks on both LF and CRLF line endings.
- [ ] Completed states show a `✓` prefix; the current state is highlighted; future states are dimmed.
- [ ] No regression on existing YAML fixtures that previously parsed correctly.

**Edge cases:**
- YAML file uses CRLF (Windows default): strip `\r` before regex application.
- State name contains a number or hyphen (e.g., `phase-2`): display as-is after stripping bullet.
- States block is empty or missing: PIPELINE section shows "(no states)" — no crash.

---

## S7 — EVENTS.jsonl timestamp field standardization

**Delivered by:** Conv 1

**As** a developer reading event logs in the EventLog panel,
**I want** every event in EVENTS.jsonl to carry a `"ts"` field,
**so that** the display code never silently drops timestamps.

**Root cause (from scout findings):**
`runner.py` writes AGENT_DONE events with a `"timestamp"` key directly (bypassing
`append_event()`). EventLog.tsx reads `ev.ts`. The two are inconsistent.

**Acceptance criteria:**
- [ ] All AGENT_DONE events written by `runner.py` use `"ts"` (not `"timestamp"`).
- [ ] `_patch_last_agent_done` in `runner.py` also writes `"ts"`.
- [ ] EventLog.tsx still reads `ev.ts` — no change needed there (already correct).
- [ ] Existing EVENTS.jsonl files with `"timestamp"` are not retroactively broken
      (log_cli.py fallback already handles old files — no change needed there).

**Edge cases:**
- Multiple AGENT_DONE events in a single run: all must use `"ts"`.
- Runner crashes mid-write: partial event line must not contain `"timestamp"` key.

---

## S2 — Monitor supports all flow types

**Delivered by:** Conv 2

**As** a developer running a debug or exploration flow,
**I want** the Monitor panel to resolve the correct base path for my topic,
**so that** I see my actual STATE.json and events — not a 404 or wrong topic.

**Root cause (from scout findings):**
Monitor hardcodes `pathly/plans/${activeTopic}`. `fsmState.flow` field already
holds the flow type. The correct mapping is:
- `team` → `pathly/plans/`
- `debug` → `pathly/debugs/`
- `explore` → `pathly/explorations/`

**Acceptance criteria:**
- [ ] Monitor reads `fsmState.flow` to pick the base directory.
- [ ] All three flow types (`team`, `debug`, `explore`) resolve to the correct base path.
- [ ] The correct flow YAML is also loaded per flow type (e.g., `debug.flow.yaml` for debug).
- [ ] Changing the active topic while Monitor is open refreshes to the new path.
- [ ] If `fsmState.flow` is absent, Monitor falls back to `team` (existing behavior preserved).

**Edge cases:**
- `fsmState.flow` contains an unrecognized string: fall back to `team`, log a console warning.
- Topic directory exists but STATE.json is missing: show "no state" — no crash.

---

## S6 — Contextual panel header in Monitor

**Delivered by:** Conv 2

**As** a developer watching the Monitor,
**I want** a header bar showing flow, topic, current state, conversation number, and active agent,
**so that** I can understand the FSM context without scanning the event log.

**Acceptance criteria:**
- [ ] Header renders at the top of the Monitor panel in this exact format:
  ```
  ─────────────────────────────────────────────────────────
    Pathly  ·  <flow>  ·  <topic>
    State : <current_state>    Conv : <N>
    Agent : <agent from last AGENT_SPAWNED event>
  ─────────────────────────────────────────────────────────
  ```
- [ ] `<flow>`, `<topic>`, `<current_state>`, `<N>` are read from `fsmState` Zustand store.
- [ ] `<agent>` is the `agent` field of the most recent `AGENT_SPAWNED` event in the events array.
- [ ] If no AGENT_SPAWNED event exists, Agent row shows `—`.
- [ ] If `fsmState` is empty (no active topic), all fields show `—`.
- [ ] Header updates live as `fsmState` changes (reactive to Zustand).

**Edge cases:**
- Events array is empty: Agent shows `—`, no crash.
- `current_conversation` is `0` or absent: Conv shows `0` or `—` respectively.
- Very long topic name: truncate with ellipsis at 32 chars.

---

## S3 — Sidebar: always show Pathly-installed sections

**Delivered by:** Conv 3

**As** a developer without a project open,
**I want** to see the Flows, Skills, Agents, and Templates sections in the Sidebar,
**so that** I can browse installed Pathly content without needing to open a project first.

**Root cause (from scout findings):**
`useProjectFiles` returns early on `!projectPath`, making all four sections invisible
until a project is open.

**Acceptance criteria:**
- [ ] Flows, Skills, Agents, Templates sections always render in the Sidebar.
- [ ] When no project is open, each installed section shows an item "(no project open)" or
      is empty with a placeholder — it does not crash or disappear.
- [ ] When a project is open, items load from `${projectPath}/src/pathly_data/core/{flows,skills,agents,templates}`.
- [ ] Plans section moves from its hardcoded position into the Workspace section (see S4).

**Edge cases:**
- Project path set but `src/pathly_data/core/flows` directory does not exist: section shows empty, no crash.
- Hook is called with `projectPath` that changes mid-session: sections re-render with new items.

---

## S4 — Sidebar: two-section structure

**Delivered by:** Conv 3

**As** a developer using Pathly Studio,
**I want** the Sidebar organized into a Pathly section (installed content) and a Workspace
section (my project's files),
**so that** I always know where to find things and the sidebar isn't a flat undifferentiated list.

**Root cause (from scout findings):**
Sidebar has Plans hardcoded at top, then SECTIONS with 6 items (Flows, Skills, Agents,
Templates, Debugs, Explorations) — Plans missing from SECTIONS, no visual grouping.

**Acceptance criteria:**
- [ ] Section A — labeled "Pathly" (or a faint rule with label): Flows, Skills, Agents, Templates.
- [ ] Section B — labeled "Workspace" (or a faint rule with label): Plans, Debugs, Explorations.
- [ ] Section A items source from `${projectPath}/src/pathly_data/core/{flows,skills,agents,templates}`.
- [ ] Section B items source from `${projectPath}/pathly/{plans,debugs,explorations}`.
- [ ] Plans in Section B shows conversations exactly as the current hardcoded PLAN block does.
- [ ] A visible separator (faint horizontal rule or section label) divides the two sections.
- [ ] Section B is hidden (or shows "(no project)") when no project is open; Section A is always visible.

**Edge cases:**
- Both sections present: separator is always visible between them.
- Only Section A visible (no project): no orphaned separator rendered below it.
- Workspace folder exists but is empty: show section header with empty list, no crash.

---

## S5 — HomeScreen scans all three workspace roots

**Delivered by:** Conv 4

**As** a developer opening Pathly Studio,
**I want** the HomeScreen to show all my topics — plans, debugs, and explorations —
**so that** I can navigate to any topic from a single view.

**Root cause (from scout findings):**
HomeScreen only scans `pathly/plans/`. `pathly/debugs/` and `pathly/explorations/`
are never surfaced.

**Acceptance criteria:**
- [ ] HomeScreen scans all three roots: `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/`.
- [ ] `.archive/` subdirectory is skipped in all three roots.
- [ ] Each topic row shows a flow type badge: `team` for plans, `debug` for debugs, `explore` for explorations.
- [ ] State badge reads FSM state from `STATE.json` in each topic directory.
- [ ] Topics from all three roots are displayed in the same list or clearly grouped.
- [ ] If a root directory does not exist, it is skipped silently — no crash, no empty error panel.

**Edge cases:**
- All three roots are empty: HomeScreen shows a "no topics yet" empty state.
- `STATE.json` is missing for a topic: state badge shows `—`.
- Topic directory name contains spaces or special characters: displays correctly.
- Two topics across different roots share the same name: both appear, distinguished by badge.

---

## S8 — Terminal panel (VS Code-style)

**Delivered by:** Conv 5

**As** a developer using Pathly Studio,
**I want** an embedded terminal at the bottom of the app,
**so that** I can run commands without switching to another application.

**Acceptance criteria:**
- [ ] Terminal panel is fixed-height (260px default) at the bottom of the app layout.
- [ ] Panel toggles open/closed with `Ctrl+\`` keyboard shortcut.
- [ ] A drag handle on the top border lets the user resize the panel height.
- [ ] A "⌨" button in TopBar also toggles terminal visibility.
- [ ] Panel collapses without killing running PTY processes; reopening reconnects to the same session.
- [ ] Multi-tab: `+` button creates a new tab; each tab label reads e.g. "powershell 1"; `×` closes a tab.
- [ ] Each tab runs an independent PTY process (PowerShell on Windows) spawned at the project root.
- [ ] Full xterm.js rendering: ANSI colors, scrollback buffer, cursor blink.
- [ ] IPC bridge: main process manages PTY via `node-pty`; renderer communicates via `window.pathly.terminal.*`.
- [ ] Closing the last tab shows an empty terminal area (no crash); `+` creates a new one.

**Edge cases:**
- Project root is not set when terminal opens: spawn PTY at the app's working directory.
- PTY process exits unexpectedly: tab shows "[process exited]" message; tab is not auto-closed.
- User resizes panel below 80px: clamp to 80px minimum height.
- User opens 10+ tabs: tabs overflow with horizontal scroll or a `v` overflow menu — no layout breakage.
- `node-pty` native module not available (missing rebuild): show an error message in the terminal area
  instead of crashing the renderer.
