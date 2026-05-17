# CONVERSATION_PROMPTS.md — pathly-studio

---

## Conversation 1 — Electron scaffold + home screen + sidebar

Read `pathly/plans/pathly-studio/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.
Read `pathly/plans/pathly-studio/UX_DIAGRAMS.md` — diagrams 1, 2, 3, and 17 show the layouts you must match.

You are building the Electron scaffold, multi-project home screen, and sidebar for Pathly Studio — a desktop app for configuring and monitoring the Pathly pipeline. This is a brand new Node.js/Electron project in a `studio/` directory at the repo root (alongside the existing `src/` Python package). Nothing in `studio/` exists yet.

**Stack:** Electron + electron-vite + React + Zustand + TypeScript.
**Security requirements (non-negotiable):** `contextIsolation: true`, `nodeIntegration: false`, all Node access via `contextBridge` only.

### What to build

**Phase 1.1 — Init**
Create `studio/` at the repo root. Initialize `package.json`, `electron.vite.config.ts`, and TypeScript config. Install all deps in one `npm install` command:
```
electron electron-vite react react-dom zustand
@types/react @types/react-dom typescript vite @vitejs/plugin-react
```

**Phase 1.2 — Main process** (`studio/src/main/index.ts`)
Create the Electron main process. Window: 1280×800, title "Pathly Studio", `contextIsolation: true`, `nodeIntegration: false`. Load renderer URL in dev, `index.html` in production. Open DevTools in dev only.

**Phase 1.3 — Preload** (`studio/src/main/preload/index.ts`)
Expose `window.pathly.fs` via contextBridge:
- `read(path: string): Promise<string>`
- `write(path: string, content: string): Promise<void>`
- `list(dir: string): Promise<string[]>`

Do NOT implement IPC handlers yet — just the preload stubs. IPC handlers come in Conv 2.

**Phase 1.4 — Types** (`studio/src/renderer/src/types/index.ts`)
Export these types:
```ts
export type PathlyItemType = 'flow' | 'skill' | 'agent' | 'template'
export interface PathlyItem { name: string; path: string; type: PathlyItemType }
export interface ProjectEntry {
  path: string; name: string; lastOpened: number
  activeTopic?: string; fsmState?: string
}
export interface FlowYaml { version: number; flow: string; states: string[]; transitions: Record<string, string[]>; agent_map: Record<string, string>; transition_rules?: Record<string, unknown>; transition_actions?: Record<string, unknown> }
export interface FsmState { state: string; flow: string; engine: string; conv_count: number }
export interface FsmEvent { ts: string; type: string; detail: string }
```

**Phase 1.5 — Zustand store** (`studio/src/renderer/src/store/index.ts`)
```ts
interface StudioStore {
  selectedItem: PathlyItem | null
  activePanel: 'editor' | 'flow' | 'monitor'
  sidebarCollapsed: boolean
  projectPath: string
  projects: ProjectEntry[]
  activeTopic: string | null
  dirtyItems: Set<string>
  setSelectedItem: (item: PathlyItem | null) => void
  setActivePanel: (panel: StudioStore['activePanel']) => void
  setSidebarCollapsed: (v: boolean) => void
  setProjectPath: (p: string) => void
  setActiveTopic: (t: string | null) => void
  markDirty: (path: string) => void
  clearDirty: (path: string) => void
  addProject: (p: ProjectEntry) => void
  removeProject: (path: string) => void
  updateProject: (path: string, patch: Partial<ProjectEntry>) => void
}
```
`projectPath` defaults to `''` (not from env — home screen handles project selection).
Persist to localStorage: `sidebarCollapsed`, `projects`. Do NOT persist `selectedItem`, `activePanel`, or `projectPath`.

**Phase 1.6 — App shell + home screen routing** (`studio/src/renderer/src/App.tsx`)
- When `store.projectPath === ''`: render `<HomeScreen />`
- When `store.projectPath !== ''`: render TopBar (with `[← Projects]` button) + two-column layout (Sidebar 240px + MainPanel flex-1)

**Phase 1.6b — Home screen** (`studio/src/renderer/src/components/HomeScreen.tsx`)
Match UX_DIAGRAMS.md diagram 17. On mount: for each project in `store.projects`, call `window.pathly.fs.list(project.path + '/pathly/plans/')` then read the newest topic's `STATE.json` — update store with `activeTopic` and `fsmState`. Render rows sorted by `lastOpened` desc.

Row: `[project name]  [truncated path]  [FSM badge]  [time ago]  [→]  [×]`
- `[→]` click: `store.setProjectPath(p.path)`, update `lastOpened`
- Cmd/Ctrl+click `[→]`: `window.pathly.shell.openWindow(p.path)`
- `[×]` click: `store.removeProject(p.path)` — no file deletion
- `[+ Open project folder]`: `window.pathly.fs.pickFolder()` → if path returned, add to `store.projects`

Add to preload:
- `window.pathly.fs.pickFolder()` → `ipcRenderer.invoke('fs:pickFolder')`
- `window.pathly.shell.openWindow(path)` → `ipcRenderer.invoke('shell:openWindow', path)`

Add IPC handlers in main:
- `fs:pickFolder` → `dialog.showOpenDialog({ properties: ['openDirectory'] })` → return `filePaths[0] ?? null`
- `shell:openWindow(path)` → create new `BrowserWindow` with same webPreferences, load renderer URL with `PROJECT_PATH=path`

**Phase 1.7 — Sidebar** (`studio/src/renderer/src/components/Sidebar.tsx`)
On mount: call `window.pathly.fs.list` on each of these dirs relative to `projectPath`:
- `src/pathly_data/core/flows` → type: flow
- `src/pathly_data/core/skills` → type: skill
- `src/pathly_data/core/agents` → type: agent
- `src/pathly_data/core/templates` → type: template (list subdirs)

Render four collapsible sections (Flows / Skills / Agents / Templates). Each item is a clickable row — `onClick` calls `store.setSelectedItem(item)` and `store.setActivePanel(item.type === 'flow' ? 'flow' : 'editor')`.

Add a fifth section "Monitor" — clicking it calls `store.setActivePanel('monitor')`.

Collapse button `[◄]` at sidebar bottom sets `store.setSidebarCollapsed(true)`.
When collapsed, render only a `[►]` button at the left edge of the main panel.

Dirty items: if `store.dirtyItems.has(item.path)`, show a `●` dot after the item name.

### Constraints
- Do NOT implement the editor, flow editor, or monitor panels yet — main panel shows "Select an item" placeholder text.
- Do NOT touch any existing Python source files in `src/`.

### Verify
```
cd studio && npm run dev
```
Window opens to home screen → `[+ Open project folder]` picker works → selecting the repo root adds it as a row → `[→]` enters the project → sidebar shows at least 3 flows and 5+ skills → `[← Projects]` returns to home screen → collapse button hides sidebar.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, run `git checkout` on affected files and retry.

---

## Conversation 2 — Editor panel

Read `pathly/plans/pathly-studio/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

Conv 1 is complete: Electron window opens, sidebar lists all Pathly content items, clicking an item sets `selectedItem` in Zustand. The main panel shows a placeholder. Your job is to replace that placeholder with a working editor panel.

### What to build

**Phase 2.1 — IPC filesystem handlers** (`studio/src/main/ipc/fs.ts`)
Create IPC handlers and register them in `main/index.ts` before `createWindow()`:
- `fs:read` — reads file at `path`, returns utf-8 string. Rejects paths outside `app.getPath('home')`.
- `fs:write` — writes atomically: write to `path.tmp`, then rename to `path`. Rejects paths outside `app.getPath('home')`.
- `fs:list` — returns `fs.readdirSync(dir)` filtered to filenames only (no subdirs for skills/agents; subdirs OK for templates).

**Phase 2.2 — Editor index** (`studio/src/renderer/src/components/Editor/index.tsx`)
When `store.activePanel === 'editor'` and `store.selectedItem !== null`:
1. Load file content via `window.pathly.fs.read(item.path)`
2. Parse frontmatter (split on first and second `---` delimiter)
3. Render `<ConfigForm>` with frontmatter values at top
4. Render tab switcher (`[ Edit ]` / `[ Preview ]` / `[⊟ Split]`) below config form
5. Render `<MarkdownEditor>` or `<MarkdownPreview>` depending on active tab

**Phase 2.3 — Config form** (`studio/src/renderer/src/components/Editor/ConfigForm.tsx`)
Props: `{ values: FrontmatterValues; onChange: (v: FrontmatterValues) => void }`
```ts
interface FrontmatterValues {
  name?: string
  description?: string
  adapters?: string[]   // ['claude', 'codex', 'copilot']
  tools?: string[]
  [key: string]: unknown
}
```
Render: name (text), description (text), adapters (three checkboxes), tools (comma-separated text input). Unknown keys rendered as plain `key: value` text — do not discard them.

**Phase 2.4 — Markdown editor** (`studio/src/renderer/src/components/Editor/MarkdownEditor.tsx`)
Install: `npm install @codemirror/lang-markdown @codemirror/view @codemirror/state @codemirror/commands`
CodeMirror 6 instance with markdown language, line numbers, basic setup. Calls `onChange(value)` on every change.

**Phase 2.5 — Markdown preview** (`studio/src/renderer/src/components/Editor/MarkdownPreview.tsx`)
Install: `npm install marked`
Renders `marked(content)` as `dangerouslySetInnerHTML`. Content is local markdown from the user's own files — not external input — so this is acceptable. Add basic prose CSS: `max-width: 720px`, sensible `h1-h3` sizes, `code` background.

**Phase 2.6 — Save + dirty tracking**
Save button in `Editor/index.tsx`:
- Merges frontmatter back: `---\n<yaml>\n---\n<markdown body>`
- Calls `window.pathly.fs.write(item.path, merged)`
- On success: `store.clearDirty(item.path)`
- On error: show inline error message, do not close editor

Dirty tracking: call `store.markDirty(item.path)` on any config form or markdown editor change.

**Split pane:** `[⊟ Split]` button sets `splitMode = true` — flex row, MarkdownEditor left 50%, MarkdownPreview right 50%, live-synced.

### Constraints
- Do NOT touch Flow editor or Monitor — those come in Conv 3 and Conv 4.
- Do NOT change any files outside `studio/`.

### Verify
```
cd studio && npm run dev
```
Click `go.md` in sidebar → config form shows name/adapters fields → Edit tab shows raw markdown → Preview tab shows rendered output → edit a word → `●` dot appears on sidebar item → click Save → `●` disappears → file on disk has the change.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, run `git checkout` on affected files and retry.

---

## Conversation 3 — Flow editor

Read `pathly/plans/pathly-studio/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

Conv 2 is complete: clicking skills/agents/templates opens the editor with config form + markdown Edit/Preview tabs. The flow panel still shows a placeholder. Your job is to implement the flow editor for `.flow.yaml` files.

### What to build

**Phase 3.1 — Flow editor shell** (`studio/src/renderer/src/components/FlowEditor/index.tsx`)
When `store.activePanel === 'flow'` and `store.selectedItem !== null`:
1. Load YAML content via `window.pathly.fs.read(item.path)`
2. Parse with `js-yaml` → typed as `FlowYaml`
3. Render tab switcher: `[ Visual ]` / `[ YAML ]`
4. Render `<VisualView>` or `<YamlView>` depending on active tab

**Phase 3.2 — Visual view** (`studio/src/renderer/src/components/FlowEditor/VisualView.tsx`)
Install: `npm install reactflow`

Map `FlowYaml` to ReactFlow nodes and edges:
- Each state in `states[]` → one node. Node label: state name (top) + agent from `agent_map` (bottom, smaller text). Position: evenly spaced left-to-right (x = index * 200, y = 100).
- Each entry in `transitions{}` → one or more edges. Edge label: artifact from `transition_rules` if present, else "default".

Click node → right-side slide-in panel (200px width):
- Text input: agent name (updates `agent_map[state]`)
- List of transition_rules entries: artifact filename → target state dropdown. `[+ Add rule]` button.

Click edge → right-side slide-in panel:
- Text input: artifact trigger (or "default")
- List of transition_actions: skill name + message. `[+ Add action]` button.

Save button: serializes current nodes/edges back to `FlowYaml` using `js-yaml.dump`, writes via IPC.

**Phase 3.3 — YAML view** (`studio/src/renderer/src/components/FlowEditor/YamlView.tsx`)
Install: `npm install @codemirror/lang-yaml js-yaml @types/js-yaml`

CodeMirror 6 with YAML language. On every change: run `js-yaml.load(content)` — if it throws, show a red error banner at top of panel and disable Save. If valid: hide banner, enable Save.

Switching Visual → YAML: serialize current graph state to YAML string via `js-yaml.dump`.
Switching YAML → Visual: parse YAML and re-render graph nodes/edges.

Save: writes to `src/pathly_data/core/flows/<name>.flow.yaml` via `window.pathly.fs.write`.

### Constraints
- Do NOT touch the Monitor panel — that comes in Conv 4.
- Do NOT modify existing flow YAML files during development — test with a copy.

### Verify
```
cd studio && npm run dev
```
Click `team.flow.yaml` in sidebar → Visual tab shows 6+ nodes (STORMING through DONE) with edges → click BUILDING node → slide-in shows "builder" agent → switch to YAML tab → raw YAML visible → change one state's agent → switch back to Visual → change reflected → click Save → file on disk updated.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, run `git checkout` on affected files and retry.

---

## Conversation 4 — Live monitor + Publish

Read `pathly/plans/pathly-studio/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

Conv 3 is complete: all three editor types work (skills, agents, flows). Your job is to add the live monitor panel and the Publish button. This conv also adds the TopBar component and wires up the MCP client + chokidar file watcher in the main process.

**Important:** The MCP tools `get_fsm_state` and `get_events` must be added to `src/pathly_orchestrator/mcp_server.py` as read-only tools. If `mcp_server.py` does not yet exist (mcp-fsm-driver plan not complete), implement the file-watch path only and log a warning when MCP ping fails — do NOT block this conversation on mcp-fsm-driver completion.

### What to build

**Phase 4.1 — Top bar** (`studio/src/renderer/src/components/TopBar.tsx`)
Fixed height bar at top of the window (above sidebar + main panel in App.tsx layout). Contains:
- Left: "Pathly Studio" text
- Center: topic selector `<select>` — options loaded from `pathly/plans/` subdirs (excluding `.archive/`). Calls `store.setActiveTopic(value)` on change. Refreshes every 5 seconds.
- Right: connection status badge (`● MCP live` green / `○ File watch` grey) + `[↑ Publish]` button

**Phase 4.2 — Monitor panel** (`studio/src/renderer/src/components/Monitor/index.tsx`)
When `store.activePanel === 'monitor'`:
1. On mount: call `window.pathly.mcp.ping()` — if true set `store.monitorSource = 'mcp'`; else set `store.monitorSource = 'filewatch'` and start file watch
2. Render `<FsmView>` + `<EventLog>` stacked vertically
3. If no `activeTopic`: show "Select a topic above to monitor"

**Phase 4.3 — FSM view** (`studio/src/renderer/src/components/Monitor/FsmView.tsx`)
Reads `store.fsmState`. Renders states as horizontal pill sequence. Active state: blue border. Completed states: `✓` prefix. If `feedback/` contains files: show `⚠ BLOCKED: <filename>` below the bar.

**Phase 4.4 — Event log** (`studio/src/renderer/src/components/Monitor/EventLog.tsx`)
Reads `store.events`. Renders rows: `HH:MM:SS  EVENT_TYPE  detail`. Fixed-height scrollable div. Auto-scrolls to bottom on new event. Shows last 50 events.

**Phase 4.5 — Chokidar watcher** (`studio/src/main/ipc/watcher.ts`)
Install: `npm install chokidar`

```ts
ipcMain.handle('watch:start', (_, topic: string, projectPath: string) => {
  const base = path.join(projectPath, 'pathly/plans', topic)
  chokidar.watch([
    path.join(base, 'STATE.json'),
    path.join(base, 'EVENTS.jsonl'),
  ]).on('change', (filePath) => {
    const content = fs.readFileSync(filePath, 'utf-8')
    win.webContents.send('watch:event', { path: filePath, content })
  })
})
```

Renderer listens for `watch:event` and dispatches to store:
- `STATE.json` change → `store.setFsmState(JSON.parse(content))`
- `EVENTS.jsonl` change → parse last 50 lines as JSON, `store.setEvents(events)`

**Phase 4.6 — MCP client** (`studio/src/main/ipc/mcp.ts`)
```ts
ipcMain.handle('mcp:ping', async () => { /* attempt tool call, return bool within 500ms */ })
ipcMain.handle('mcp:state', async (_, topic: string) => { /* call get_fsm_state(topic) */ })
```
Poll `mcp:state` every 2 seconds when `monitorSource === 'mcp'`. On error: fall back to `filewatch`.

Add to preload: `window.pathly.mcp = { ping, state }` and `window.pathly.watch = { start }`.

**Phase 4.7 — Publish** (`studio/src/main/ipc/shell.ts`)
```ts
ipcMain.handle('shell:publish', (_, cwd: string) => {
  const proc = spawn('pip', ['install', '-e', '.'], { cwd, stdio: 'pipe' })
  proc.stdout.on('data', d => win.webContents.send('shell:output', d.toString()))
  proc.stderr.on('data', d => win.webContents.send('shell:output', d.toString()))
  return new Promise(resolve => proc.on('close', resolve))
})
```

TopBar Publish button: disabled while `store.publishing`. On click: set `store.publishing = true`, open log slide-up panel, listen for `shell:output` events, append to `store.publishLog`. On exit code 0: show "Published successfully" banner, auto-hide log after 3s. On non-zero: show "Publish failed" banner, keep log open.

Add to preload: `window.pathly.shell = { publish, onOutput }`.

### Constraints
- Do NOT modify existing Python source files except adding two read-only tools to `mcp_server.py`.
- If `mcp_server.py` does not exist: skip Phase 4.6, note it as follow-up.

### Verify
```
cd studio && npm run dev
```
Select a topic with active STATE.json → Monitor panel shows correct current state highlighted → click Publish → log panel slides up → pip output streams → "Published successfully" appears.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, run `git checkout` on affected files and retry.
