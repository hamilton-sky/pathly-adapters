# ARCHITECTURE_PROPOSAL.md — pathly-studio

---

## Process model

Electron runs two processes. All filesystem and subprocess access is in main.
Renderer is a sandboxed React app — it can only call what the preload exposes.

```
Main process (Node.js)
  ├── window management
  ├── ipc/fs.ts       — readFile, writeFile, listDir
  ├── ipc/watcher.ts  — chokidar STATE.json + EVENTS.jsonl
  ├── ipc/mcp.ts      — stdio MCP client (ping, get_fsm_state, get_events)
  └── ipc/shell.ts    — pip install subprocess

Preload (contextBridge)
  └── exposes window.pathly = { fs, watch, mcp, shell }
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
  'mcp:ping':   {} → boolean
  'mcp:state':  { topic: string } → FsmState | null
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
  monitorSource:     'mcp' | 'filewatch' | 'detecting'

  // publish
  publishing:        boolean
  publishLog:        string[]
}
```

---

## MCP client (ipc/mcp.ts)

The MCP server (`pathly-mcp-server`) runs as a separate stdio process, launched
by Claude/Codex. Studio connects as a second MCP client on the same server.

Connection sequence:
1. On monitor open: spawn `pathly-mcp-server` in stdio mode (or attach if already running)
2. Send `ping` tool call — if response within 500ms: set source = `mcp`
3. On timeout/error: fall back to chokidar file watch, set source = `filewatch`
4. On MCP: poll `get_fsm_state(topic)` every 2 seconds while monitor is open

MCP tools the studio calls (must be added to mcp_server.py in mcp-fsm-driver):
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
