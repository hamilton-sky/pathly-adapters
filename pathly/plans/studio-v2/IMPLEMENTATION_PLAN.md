# IMPLEMENTATION_PLAN — studio-v2

---

## Phasing rationale

Stories are grouped to keep each conversation independently shippable and to respect
natural architectural seams: bug fixes first, then component-level changes, then
cross-layer IPC work last.

---

## Conv 1 — Quick fixes

**Stories:** S1, S7
**Goal:** Fix the two known bugs (pipeline display, timestamp field) so the codebase
is clean before any structural changes are layered on.

**Files:**
- `studio/src/renderer/src/components/Monitor/index.tsx` — regex fix + CRLF stripping
- `src/pathly_orchestrator/runner.py` — AGENT_DONE events and `_patch_last_agent_done`

**Deliverables:**
- Pipeline states render without `- ` prefix and in uppercase.
- Regex matches on both LF and CRLF line endings.
- All AGENT_DONE events in runner.py write `"ts"` not `"timestamp"`.

**Verification:**
- Open Studio with a team flow topic; PIPELINE shows `STORMING`, `PLANNING`, etc.
- Search runner.py: zero occurrences of `"timestamp"` key in event-writing code.

---

## Conv 2 — Monitor improvements

**Stories:** S2, S6
**Goal:** Make Monitor useful for all flow types and add contextual header.
**Depends on:** Conv 1 (clean Monitor baseline)

**Files:**
- `studio/src/renderer/src/components/Monitor/index.tsx` — dynamic base path + header bar
- `studio/src/renderer/src/store/fsmStore.ts` (or equivalent) — verify `flow` field is present

**Deliverables:**
- Monitor resolves base path from `fsmState.flow` (`team`/`debug`/`explore`).
- Correct flow YAML loaded per flow type.
- Header bar renders with flow, topic, state, conv number, and last AGENT_SPAWNED agent.

**Verification:**
- Switch active topic to a debug topic; Monitor shows content from `pathly/debugs/`.
- Header bar updates live when FSM transitions state.

---

## Conv 3 — Sidebar restructure

**Stories:** S3, S4
**Goal:** Split Sidebar into Pathly (always visible) and Workspace (project-dependent) sections.
**Depends on:** Conv 1 (stable baseline)

**Files:**
- `studio/src/renderer/src/components/Sidebar/index.tsx` — two-section layout
- `studio/src/renderer/src/hooks/useProjectFiles.ts` — split early-return logic

**Deliverables:**
- Section A (Pathly): Flows, Skills, Agents, Templates — always renders.
- Section B (Workspace): Plans, Debugs, Explorations — renders only when project open.
- Visual separator between sections.
- Plans moved from hardcoded position into Section B.

**Verification:**
- Launch Studio with no project open: Section A renders; Section B shows "(no project)" or hides.
- Open a project: Section B renders with Plans, Debugs, Explorations.

---

## Conv 4 — HomeScreen all flows

**Stories:** S5
**Goal:** HomeScreen lists topics from all three workspace roots.
**Depends on:** Conv 3 (sidebar restructure establishes scan conventions)

**Files:**
- `studio/src/renderer/src/components/HomeScreen/index.tsx` — scan all three roots
- `studio/src/renderer/src/hooks/useProjectFiles.ts` — may need scan helper extension

**Deliverables:**
- Topics from plans, debugs, and explorations all appear on HomeScreen.
- Flow type badge on each topic row.
- `.archive/` directories skipped.
- Missing STATE.json handled gracefully.

**Verification:**
- With topics in all three roots: all appear on HomeScreen with correct badges.
- Remove STATE.json from one topic: its row shows `—` for state, no crash.

---

## Conv 5 — Terminal panel

**Stories:** S8
**Goal:** Add a VS Code-style embedded terminal to Studio.
**Depends on:** Conv 3 (App.tsx layout is stable before adding new panel sibling)

**Files:**
- `studio/package.json` — add `node-pty`, `xterm`, `xterm-addon-fit` dependencies
- `studio/src/main/index.ts` — PTY lifecycle management (spawn, write, resize, kill)
- `studio/src/preload/index.ts` — expose `window.pathly.terminal.*` IPC bridge
- `studio/src/renderer/src/App.tsx` — terminal panel as collapsible flex sibling below body
- `studio/src/renderer/src/components/TopBar/index.tsx` — "⌨" toggle button
- `studio/src/renderer/src/components/Terminal/index.tsx` — new component (xterm.js, tabs, resize handle)
- `studio/src/renderer/src/store/terminalStore.ts` — new Zustand store (open state, tabs)
- `studio/electron.vite.config.ts` — ensure node-pty is marked as external for main process

**Deliverables:**
- Terminal panel toggles with `Ctrl+\`` and TopBar button.
- Multi-tab: create/close tabs; each tab is an independent PTY.
- Panel resizes via drag handle (min 80px).
- Processes survive panel collapse; reconnect on reopen.
- ANSI colors, scrollback, cursor blink via xterm.js.

**Verification:**
- Open terminal, type `echo hello`: output renders with correct color.
- Close panel and reopen: PTY session still alive (shell prompt returns).
- `Ctrl+C` kills a running process inside the tab — tab shows "[process exited]".
- Open 3 tabs, close middle tab: remaining tabs are unaffected.
