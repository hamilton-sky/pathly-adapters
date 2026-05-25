# ARCHITECTURE_PROPOSAL.md — pathly-studio

---

## Process model

Electron runs two processes. All filesystem and subprocess access is in main.
Renderer is a sandboxed React app — it can only call what the preload exposes.

> **Persistence note:** Use `electron-store` (not `localStorage`) for persisting
> `projects[]` and `sidebarCollapsed`. `electron-store` writes to the OS user-data
> directory, survives app updates, and is accessible from the main process without
> IPC. `localStorage` is renderer-only and can be wiped by Electron on origin change.
> Install: `npm install electron-store`.

```
Main process (Node.js)
  ├── window management
  ├── ipc/fs.ts       — readFile, writeFile, listDir
  ├── ipc/watcher.ts  — chokidar STATE.json + EVENTS.jsonl
  ├── ipc/http.ts      — stdio HTTP client (ping, get_fsm_state, get_events)
  └── ipc/shell.ts    — pip install subprocess

Preload (contextBridge)
  └── exposes window.pathly = { fs, watch, http, shell }
      all handlers are typed — no raw ipcRenderer.invoke in renderer

Renderer (React + Zustand)
  ├── Sidebar
  ├── Editor (ConfigForm + MarkdownEditor + MarkdownPreview)
  ├── FlowEditor (VisualView + YamlView)
  └── Monitor (FsmView + EventLog)
```

---

## IPC contract

Every IPC channel is defined once in `types/index.ts` and imported by both
preload and renderer. No magic strings anywhere.

```ts
// types/index.ts (excerpt)
export type IpcChannels = {
  'fs:read':    { path: string } → string
  'fs:write':   { path: string; content: string } → void
  'fs:list':    { dir: string } → string[]
  'watch:start':{ path: string } → void
  'watch:event':{ path: string; content: string } → void  // pushed to renderer
  'http:ping':   {} → boolean
  'http:state':  { topic: string } → FsmState | null
  'shell:publish': { cwd: string } → void
  'shell:output':  { line: string } → void  // streamed to renderer
}
```

---

## Zustand store shape

```ts
interface StudioStore {
  // navigation
  selectedItem:      PathlyItem | null
  activePanel:       'editor' | 'flow' | 'monitor'
  sidebarCollapsed:  boolean

  // project
  projectPath:       string
  activeTopic:       string | null

  // monitor
  fsmState:          FsmState | null
  events:            FsmEvent[]
  monitorSource:     'http' | 'filewatch' | 'detecting'

  // publish
  publishing:        boolean
  publishLog:        string[]
}
```

---

## HTTP client (ipc/http.ts)

The HTTP server (`pathly-http-server`) runs as a separate stdio process, launched
by Claude/Codex. Studio connects as a second HTTP client on the same server.

> **Risk — stdio is single-client.** HTTP over stdio is point-to-point: one process
> writes to stdin, one reads from stdout. A second client attaching to the same stdio
> pipe will corrupt the framing. Two options:
> 1. **(Recommended for Part 1)** Don't attach to the running server — run a separate
>    read-only `pathly-http-server` instance as a child process of Studio's main process.
>    Pass `--read-only` (or equivalent) so it doesn't mutate FSM state.
> 2. **(Part 2+)** Add a TCP/named-pipe transport to `pathly-http-server` so multiple
>    clients can connect.
>
> For now: treat the HTTP path as best-effort. The file-watch fallback is the reliable
> path and must always work correctly.

Connection sequence:
1. On monitor open: spawn `pathly-http-server` in stdio mode (or attach if already running)
2. Send `ping` tool call — if response within 500ms: set source = `http`
3. On timeout/error: fall back to chokidar file watch, set source = `filewatch`
4. On HTTP: poll `get_fsm_state(topic)` every 2 seconds while monitor is open

HTTP tools the studio calls (must be added to http_server.py in http-fsm-driver):
- `get_fsm_state(topic: str)` → `{ state, flow, engine, conv_count }`
- `get_events(topic: str, limit: int)` → `FsmEvent[]`

These two tools are read-only additions — they do not affect pipeline execution.

---

## File format assumptions

**Skill/Agent/Template markdown:**
Files may have a YAML frontmatter block delimited by `---` at the top.
ConfigForm reads the frontmatter; MarkdownEditor shows everything after the
closing `---`. If no frontmatter exists, ConfigForm shows empty fields and
saving adds frontmatter.

```markdown
---
name: go
description: Continue active pipeline feature
adapters: [claude, codex, copilot]
tools: [Bash, Read, Glob, Grep, TodoWrite, Agent]
---

# Go
...
```

**Flow YAML:** standard `src/pathly_data/core/flows/*.flow.yaml` format.
ReactFlow maps: `states[]` → nodes, `transitions{}` → edges,
`agent_map{}` → node labels, `transition_rules{}` → edge labels.

---

## Security

- `contextIsolation: true`, `nodeIntegration: false` — enforced in BrowserWindow options
- `contextBridge` only exposes the typed IPC channels above — no raw Node APIs in renderer
- File write is restricted to paths under `projectPath` — main process validates before writing
- Subprocess (pip install) runs with inherited env, no shell injection (args passed as array, not string)
