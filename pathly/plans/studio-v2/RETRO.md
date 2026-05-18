# Retrospective — studio-v2

**Delivered:** 2026-05-18
**Total conversations:** 7

---

## What was delivered

| ID | Title | Summary |
|----|-------|---------|
| S1 | Fix pipeline display in Monitor | Regex fix to strip `- ` bullet prefix and handle CRLF line endings; state names now render correctly. |
| S2 | Monitor supports all flow types | Monitor resolves base path from `fsmState.flow`, supporting team, debug, and explore flows. |
| S3 | Sidebar: always show Pathly-installed sections | Flows, Skills, Agents, Templates sections always render regardless of whether a project is open. |
| S4 | Sidebar: two-section structure | Sidebar split into a "Pathly" section (installed content) and a "Workspace" section (project files). |
| S5 | HomeScreen scans all three workspace roots | HomeScreen now lists topics from plans, debugs, and explorations with flow-type badges. |
| S6 | Contextual panel header in Monitor | Header bar shows flow, topic, FSM state, conversation number, and last active agent. |
| S7 | EVENTS.jsonl timestamp standardization | All AGENT_DONE events in runner.py now write `"ts"` consistently, matching what EventLog.tsx reads. |
| S8 | Terminal panel | Embedded VS Code-style terminal with multi-tab PTY, drag-to-resize, xterm.js rendering, and Ctrl+` toggle. |
| S9 | Sidebar: create + rename/delete (no drag/drop) | Per-section `+` button and right-click context menu for create, rename, and delete operations. |
| S10 | Design system | Seven shared `ui/` components (Button, IconButton, Input, Tooltip, Badge, Separator, ContextMenu) with consistent focus-visible rings and Lucide chevrons replacing all arrow entities. |
| S11 | Monitor: raw log view + SSE fix + cost tracking | Raw JSON event log view, SSE null-guard for missing project path, and real token/cost values from runner.py. |

---

## What worked well

- **Story sizing was right.** Pairing two stories per conversation (except S5 and S8) gave each session a clear, independently-shippable goal without over-scoping.
- **Layering order paid off.** Starting with bug fixes (Conv 1) before structural changes meant later conversations built on a clean baseline, with no regressions from the early work.
- **Design system last.** Deferring the `ui/` component library to Conv 7 meant components were designed around real usage patterns seen in Convs 3–6, avoiding premature abstraction.

---

## What was tricky

- **xterm blank screen.** xterm.js requires the `Terminal` instance to be attached to a mounted DOM node before `fit()` is called; the initial render would show a blank panel until a resize event fired. Fix: call `fit()` inside a `useEffect` with a short `requestAnimationFrame` delay after attach.
- **`focus-visible` review cycles.** The focus ring spec (2px solid accent, 2px offset) triggered multiple review rounds because some interactive elements used `onMouseDown` to handle activation, which caused the ring to appear on click as well as keyboard. Required explicit `onMouseDown` + `e.preventDefault()` in IconButton to suppress the ring on pointer interactions.
- **S9/S11 left pending.** Convs 6 and 7 overlapped in scope (S9 needed Tooltip from S10; S10 assumed S9 file-ops UI existed), so both stories are marked pending in PROGRESS.md pending a follow-up pass to wire everything together.
- **PTY IPC surface.** Exposing `window.pathly.terminal.*` through the preload required careful allowlisting in the contextBridge; missing an event name caused silent failures in the renderer that were hard to distinguish from xterm render bugs.

---

## Numbers

- 7 conversations, 11 stories scoped, 11 delivered (S9 + S11 completed in follow-up Conv 6 pass).
- Files touched across main, preload, renderer, and Python orchestrator layers.

---

## Conv 6 follow-up (2026-05-19)

**S9 and S11 delivered and verified.**

- EventLog.tsx: raw `JSON.stringify` per-event display with color-coding by type
- runner.py: `tool_uses` count patched into AGENT_DONE events
- TypeScript typecheck clean (ES2021 target, clipboard types, CSS module declarations)
- FSM git automation workaround: CRLF warnings misread as hard errors — committed manually

**Lessons extracted:**
- Validate git CRLF/commit automation early, not at delivery
- Lock TypeScript target/lib matrix at feature start to catch ES version mismatches in planning
- Establish cosmetic acceptance criteria before coding to reduce review noise
