# pathly-studio — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## What this feature is

An Electron desktop app for configuring and live-monitoring the Pathly pipeline.
Three core panels: **Sidebar** (file tree of all agents/skills/flows/templates),
**Editor** (config form + markdown editor with Edit/Preview tabs), and
**Flow Editor** (ReactFlow visual graph + YAML tab).
Live monitor shows real-time FSM state — auto-detects MCP server (Python-driven)
or falls back to file watching (LLM-driven).

**This is Part 1 of 2.** Part 1 covers scaffold + editor + flow editor + monitor.
Part 2 (`pathly-studio-part-2`) covers packaging, auto-update, and install wizard.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status |
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative |
| `EDGE_CASES.md` | Planner | Builder, Tester | Failure modes |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Architect, Builder | Design decisions |
| `FLOW_DIAGRAM.md` | Planner | All agents | Component interaction diagram |

### Optional plan files

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | Electron IPC design, MCP client, data flow |
| `EDGE_CASES.md` | yes | Failure modes and risk scenarios |
| `HAPPY_FLOW.md` | yes | Golden-path narrative |
| `FLOW_DIAGRAM.md` | yes | Multi-component interaction diagram |

---

## Codebase touchpoints

| Codebase file | Conversation | What changes |
|---|---|---|
| `studio/package.json` | Conv 1 | CREATE — Electron + React + Zustand + electron-vite deps |
| `studio/electron.vite.config.ts` | Conv 1 | CREATE — vite config for main + preload + renderer |
| `studio/src/main/index.ts` | Conv 1 | CREATE — main process: window creation, IPC registration |
| `studio/src/main/preload/index.ts` | Conv 1 | CREATE — contextBridge: safe API exposed to renderer |
| `studio/src/renderer/src/App.tsx` | Conv 1 | CREATE — root layout: sidebar + main panel |
| `studio/src/renderer/src/store/index.ts` | Conv 1 | CREATE — Zustand store: selectedItem, projectPath, sidebarCollapsed |
| `studio/src/renderer/src/types/index.ts` | Conv 1 | CREATE — shared types: PathlyItem, FlowYaml, FsmState, Event |
| `studio/src/renderer/src/components/Sidebar.tsx` | Conv 1 | CREATE — collapsible tree: Flows/Skills/Agents/Templates/Monitor |
| `studio/src/main/ipc/fs.ts` | Conv 2 | CREATE — IPC handlers: readFile, writeFile, listDir |
| `studio/src/renderer/src/components/Editor/index.tsx` | Conv 2 | CREATE — panel: config form + markdown editor, tab switcher |
| `studio/src/renderer/src/components/Editor/ConfigForm.tsx` | Conv 2 | CREATE — parses YAML frontmatter, renders form fields |
| `studio/src/renderer/src/components/Editor/MarkdownEditor.tsx` | Conv 2 | CREATE — CodeMirror with markdown syntax highlight + split pane |
| `studio/src/renderer/src/components/Editor/MarkdownPreview.tsx` | Conv 2 | CREATE — marked.js rendered output |
| `studio/src/renderer/src/components/FlowEditor/index.tsx` | Conv 3 | CREATE — tab switcher: Visual / YAML |
| `studio/src/renderer/src/components/FlowEditor/VisualView.tsx` | Conv 3 | CREATE — ReactFlow graph: states as nodes, transitions as edges |
| `studio/src/renderer/src/components/FlowEditor/YamlView.tsx` | Conv 3 | CREATE — CodeMirror YAML editor with js-yaml validation |
| `studio/src/renderer/src/components/Monitor/index.tsx` | Conv 4 | CREATE — monitor panel: topic selector + FSM view + event log |
| `studio/src/renderer/src/components/Monitor/FsmView.tsx` | Conv 4 | CREATE — progress bar showing states, active state highlighted |
| `studio/src/renderer/src/components/Monitor/EventLog.tsx` | Conv 4 | CREATE — scrollable event timeline from EVENTS.jsonl |
| `studio/src/renderer/src/components/TopBar.tsx` | Conv 4 | CREATE — topic selector, connection status badge, Publish button |
| `studio/src/main/ipc/watcher.ts` | Conv 4 | CREATE — chokidar watcher: STATE.json + EVENTS.jsonl → IPC events |
| `studio/src/main/ipc/mcp.ts` | Conv 4 | CREATE — MCP stdio client: ping, get_fsm_state, get_events |
| `studio/src/main/ipc/shell.ts` | Conv 4 | CREATE — runs pip install -e . subprocess, streams output |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.
> Note: all `studio/` paths are CREATE — the directory does not exist yet. Create it at project root alongside `src/`.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | Electron scaffold + sidebar | S1, S2 | TODO | `studio/package.json`, `main/index.ts`, `preload/index.ts`, `App.tsx`, `Sidebar.tsx`, `store/index.ts`, `types/index.ts` |
| 2 | Editor panel | S3 | TODO | `ipc/fs.ts`, `Editor/index.tsx`, `ConfigForm.tsx`, `MarkdownEditor.tsx`, `MarkdownPreview.tsx` |
| 3 | Flow editor | S4 | TODO | `FlowEditor/index.tsx`, `VisualView.tsx`, `YamlView.tsx` |
| 4 | Live monitor + Publish | S5, S6 | TODO | `Monitor/`, `TopBar.tsx`, `ipc/watcher.ts`, `ipc/mcp.ts`, `ipc/shell.ts` |

---

## Feedback files (transient — deleted after resolution)

Live in `plans/pathly-studio/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
