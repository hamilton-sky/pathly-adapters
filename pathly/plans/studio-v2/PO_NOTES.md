# PO_NOTES — studio-v2

## Context

Pathly Studio is an Electron + React app for monitoring and managing Pathly FSM flows.
All UI code lives in `studio/`. All FSM/Python code lives in `src/pathly_orchestrator/`.

---

## Stories

### S1 — Fix pipeline display in Monitor
**Problem:** PIPELINE section shows `- storming` (with dash prefix) instead of `STORMING`.
The Monitor reads `team.flow.yaml` and parses states via regex, but the regex captures the
`- ` bullet prefix. States should display as `STORMING`, `PLANNING`, etc. with ✓ for completed.
**Scope:** `studio/src/renderer/src/components/Monitor/index.tsx` — fix the YAML states regex.

### S2 — Monitor supports all flow types (plans / debugs / explorations)
**Problem:** Monitor hardcodes `pathly/plans/${activeTopic}` as the base path.
Debug topics live in `pathly/debugs/`, exploration topics in `pathly/explorations/`.
**AC:**
- Read `flow` field from STATE.json to determine base path
- `team` flow → `pathly/plans/`
- `debug` flow → `pathly/debugs/`
- `explore` flow → `pathly/explorations/`
- Also load the correct flow YAML per flow type

### S3 — Sidebar: always show Pathly-installed sections
**Problem:** Flows / Skills / Agents / Templates sections only load when a project is open
because `useProjectFiles` returns early when `projectPath` is empty.
**AC:**
- These four sections always render with items from the installed `src/pathly_data/core/` paths
  relative to the project root (when a project is open) OR show "(no project)" when none is open
- Plans section (currently hardcoded at top of Sidebar) moves into the project section alongside Debugs and Explorations

### S4 — Sidebar: two-section structure
**Problem:** Sidebar mixes installed Pathly data (Flows/Skills/Agents/Templates) with
project workspace folders (Debugs/Explorations) and has Plans hardcoded separately.
**AC:**
- **Section A — Pathly** (always visible): Flows, Skills, Agents, Templates
- **Section B — Workspace** (project-dependent): Plans, Debugs, Explorations
- Section A items are read from `${projectPath}/src/pathly_data/core/{flows,skills,agents,templates}`
- Section B items are read from `${projectPath}/pathly/{plans,debugs,explorations}`
- Visual separator between sections (faint rule or label)
- Plans section in Section B shows conversations (same as current hardcoded PLAN block)

### S5 — HomeScreen scans all three workspace roots
**Problem:** HomeScreen only scans `pathly/plans/` to populate project cards.
Debug and exploration topics don't appear.
**AC:**
- Scan `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/` (skip `.archive/`)
- Each topic row shows flow type badge: `team` / `debug` / `explore`
- State badge uses FSM state from STATE.json

### S6 — Contextual panel in Monitor (state / conv / agent header)
**Problem:** Monitor shows PIPELINE and EVENT LOG but no summary header showing current
state, conversation number, and active agent.
**AC:** Add a header bar at the top of the Monitor panel:
```
─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>    Conv : <N>
  Agent : <agent from last AGENT_SPAWNED event>
─────────────────────────────────────────────────────────
```
Reads from `fsmState` (Zustand) + last AGENT_SPAWNED event in events array.

### S7 — EVENTS.jsonl timestamp field standardization
**Problem:** FSM server writes `"ts"` for STATE_TRANSITION events but AGENT_DONE events
use `"timestamp"`. EventLog.tsx uses `ev.ts` for display. Need one canonical field.
**Decision:** Standardize on `"ts"` everywhere (matches what the FSM server already writes).
**AC:**
- `EventLog.tsx` already reads `ev.ts` ✓
- `log_cli.py` already falls back from `"ts"` → `"timestamp"` ✓
- Fix `runner.py` AGENT_DONE events to use `"ts"` instead of `"timestamp"`
- Fix manual event logging in `runner.py` `_patch_last_agent_done` to write `"ts"`

### S8 — Terminal panel (VS Code-style, bottom of Studio)
**Problem:** No terminal in Studio — users must switch to another terminal app to run commands.
**AC:**
- Fixed-height panel at bottom (260px default), toggle with `Ctrl+\`` keyboard shortcut
- Drag handle on top border to resize
- Multi-tab: `+` New tab button, tab label (e.g. "powershell 1"), `×` close tab
- Each tab is an independent PTY process (PowerShell on Windows) spawned at project root
- Full xterm.js rendering: ANSI colors, scrollback, cursor blink
- IPC: main process handles pty via `node-pty`; renderer uses xterm.js
- Small "⌨" button in TopBar to toggle terminal visibility
- Panel collapses/shows without killing running processes

---

## Out of scope
- Cost telemetry from Agent tool invocations (architectural limitation — not fixable in Studio)
- `pathly-run` standalone CLI improvements
- Any changes to Python FSM engine or flow YAMLs

## Priority order
S1 (pipeline fix) → S3+S4 (sidebar) → S2 (monitor routing) → S5 (homescreen) → S6 (header) → S7 (ts field) → S8 (terminal)
