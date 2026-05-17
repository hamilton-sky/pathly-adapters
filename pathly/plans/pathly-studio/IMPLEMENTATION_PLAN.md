# IMPLEMENTATION_PLAN.md — pathly-studio

> Pre-flight: before Conv 1, run `node --version` and `npm --version` to record baseline.
> If either is missing, stop and report to user before proceeding.

---

## Phase 1 — Electron scaffold + home screen   ← Conversation: 1

**File:** `studio/package.json`
**Done when:** `npm run dev` inside `studio/` opens an Electron window with a white screen (no errors in terminal or DevTools console).

### 1.1 Init the studio package

Create `studio/` at the repo root (alongside `src/`). Initialize with:

```json
{
  "name": "pathly-studio",
  "version": "0.1.0",
  "main": "out/main/index.js",
  "scripts": {
    "dev": "electron-vite dev",
    "build": "electron-vite build",
    "preview": "electron-vite preview"
  }
}
```

Install deps:
```
npm install electron electron-vite react react-dom zustand electron-store
npm install -D @types/react @types/react-dom typescript vite @vitejs/plugin-react
```

**File:** `studio/electron.vite.config.ts`
**Done when:** vite resolves main/preload/renderer entry points without error.

### 1.2 Main process

**File:** `studio/src/main/index.ts`
**Done when:** window opens at 1280×800, DevTools open in dev mode, `contextIsolation: true`, `nodeIntegration: false`.

```ts
import { app, BrowserWindow } from 'electron'
import { join } from 'path'

function createWindow() {
  const win = new BrowserWindow({
    width: 1280, height: 800,
    title: 'Pathly Studio',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    }
  })
  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL)
    win.webContents.openDevTools()
  } else {
    win.loadFile(join(__dirname, '../../renderer/index.html'))
  }
}

app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
```

### 1.3 Preload / contextBridge

**File:** `studio/src/main/preload/index.ts`
**Done when:** `window.pathly` exists in renderer DevTools console.

Expose only:
```ts
contextBridge.exposeInMainWorld('pathly', {
  fs: {
    read:  (path: string) => ipcRenderer.invoke('fs:read', path),
    write: (path: string, content: string) => ipcRenderer.invoke('fs:write', { path, content }),
    list:  (dir: string) => ipcRenderer.invoke('fs:list', dir),
  }
})
```
(watcher, mcp, shell added in Conv 4)

### 1.4 Types + multi-project store

**File:** `studio/src/renderer/src/types/index.ts`
**Done when:** all shared types exported — `PathlyItem`, `ProjectEntry`, `FlowYaml`, `FsmState`, `FsmEvent`.

Add `ProjectEntry`:
```ts
export interface ProjectEntry {
  path: string        // absolute path to repo root
  name: string        // basename of path
  lastOpened: number  // Date.now() timestamp
  activeTopic?: string
  fsmState?: string   // read from STATE.json at load time
}
```

**File:** `studio/src/renderer/src/store/index.ts`
**Done when:** store imports without error; `projects` persists via electron-store IPC; `selectedItem` defaults to null; `projectPath` defaults to `''`.

Use `electron-store` (main process) instead of localStorage for persistence. Add IPC channels:
- `store:get(key)` → value
- `store:set(key, value)` → void

Expose via preload as `window.pathly.store.get` / `window.pathly.store.set`.
Persist via electron-store: `projects`, `sidebarCollapsed`. Do NOT persist `selectedItem` or `activePanel`.

Store shape additions for multi-project:
```ts
projects: ProjectEntry[]
addProject:    (p: ProjectEntry) => void
removeProject: (path: string) => void
updateProject: (path: string, patch: Partial<ProjectEntry>) => void
```

Add to preload (`preload/index.ts`):
```ts
fs: { read, write, list, pickFolder }   // pickFolder added here
shell: { openWindow }                   // openWindow added here
```

Add IPC handlers:
- `fs:pickFolder` → `dialog.showOpenDialog({ properties: ['openDirectory'] })` → returns path string or null
- `shell:openWindow(path)` → spawns new `BrowserWindow` with `PROJECT_PATH=path` in env

### 1.5 Home screen

**File:** `studio/src/renderer/src/components/HomeScreen.tsx`
**Done when:** app shows home screen when `store.projectPath === ''`; clicking `[→]` sets `projectPath` and transitions to main layout; `[+ Open project folder]` opens native picker and adds project to list.

On mount: for each entry in `store.projects`, read `<entry.path>/pathly/plans/` via IPC, find the most recently modified topic folder, read its `STATE.json`, call `store.updateProject(entry.path, { activeTopic, fsmState })`. Run in parallel.

Row layout: project name (bold) + truncated path + FSM state badge + time since `lastOpened` + `[→]` + `[×]`.
- `[→]` click: `store.setProjectPath(entry.path)`, `store.updateProject(entry.path, { lastOpened: Date.now() })`
- Cmd/Ctrl+click `[→]`: call `window.pathly.shell.openWindow(entry.path)`
- `[×]` click: `store.removeProject(entry.path)` — no file deletion, no confirmation needed

### 1.6 App.tsx routing + back button

**File:** `studio/src/renderer/src/App.tsx`
**Done when:** renders `<HomeScreen />` when `projectPath === ''`; renders TopBar + Sidebar + MainPanel when `projectPath !== ''`.

TopBar gets a `[← Projects]` button at the far left — clicking it calls `store.setProjectPath('')`, returning to the home screen without closing the window.

### 1.7 Sidebar

**File:** `studio/src/renderer/src/components/Sidebar.tsx`
**Done when:**
- Reads `src/pathly_data/core/` subdirs via `window.pathly.fs.list`
- Renders four collapsible sections: Flows / Skills / Agents / Templates
- Clicking any item calls `store.setSelectedItem(item)`
- `[◄]` button sets `sidebarCollapsed = true`; main panel expands to full width
- Collapsed state saved to localStorage on change

Add a search/filter input at the top of the sidebar:
- Controlled input, placeholder "Filter…"
- On change: filter `items` in all sections to those whose `name.toLowerCase().includes(query)`
- Sections with zero matches collapse automatically; sections with matches expand and show only matched items
- Clearing the input restores full tree state

Add global keyboard shortcut:
- In `App.tsx` effect: `window.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); store.triggerSave() } })`
- Add `triggerSave: () => void` to store — sets `savePending = true`; Editor/FlowEditor observe and call their save logic when `savePending` flips

**Verify:** `npm run dev` → home screen lists any previously opened projects → clicking `[→]` enters the project → sidebar shows at least 3 flows and 10+ skills → typing "go" in filter shows only items matching "go".

**Purpose:** navigation layer — all other panels depend on item selection.

---

## Phase 2 — Editor panel   ← Conversation: 2

### 2.1 IPC filesystem handlers

**File:** `studio/src/main/ipc/fs.ts`
**Done when:** `ipcMain.handle('fs:read', ...)` returns file content; `fs:write` writes atomically (tmp + rename); `fs:list` returns filenames in directory.

Register all handlers in `main/index.ts` before `createWindow()`.

Path guard: reject any path not under `app.getPath('home')` — prevents write outside project.

### 2.2 Editor panel

**File:** `studio/src/renderer/src/components/Editor/index.tsx`
**Done when:** selecting a skill/agent/template in sidebar shows the editor panel with the file's content split into config form (top) and markdown area (bottom).

### 2.3 Config form

**File:** `studio/src/renderer/src/components/Editor/ConfigForm.tsx`
**Done when:**
- Parses YAML frontmatter between opening and closing `---`
- Renders known fields: name (text), description (text), adapters (checkboxes: claude/codex/copilot), tools (comma-separated text)
- Unknown frontmatter keys (e.g. `version`, `model`) rendered as read-only `key: value` rows under a collapsed `▶ Additional fields` section — these keys must be round-tripped exactly on save (see E3)
- If no frontmatter: all fields empty, saving adds frontmatter block

### 2.4 Markdown editor

**File:** `studio/src/renderer/src/components/Editor/MarkdownEditor.tsx`
**Done when:** CodeMirror instance loads with markdown language support, shows file content below frontmatter, syntax highlighted.

Install: `npm install @codemirror/lang-markdown @codemirror/view @codemirror/state`

### 2.5 Preview + tab switcher

**File:** `studio/src/renderer/src/components/Editor/MarkdownPreview.tsx`
**Done when:** `marked(content)` output rendered as HTML in a styled div — headings, code blocks, and lists visually match GitHub README style.

Install: `npm install marked`

Tab switcher in `Editor/index.tsx`:
- `[ Edit ]` tab: shows MarkdownEditor
- `[ Preview ]` tab: shows MarkdownPreview
- `[⊟ Split]` button: side-by-side flex layout, editor left (50%) + preview right (50%)

Save button: merges config form values back into frontmatter + markdown body → writes via `window.pathly.fs.write`. Unsaved changes: dot on sidebar item (store tracks `dirtyItems: Set<string>`).

**Verify:** open `src/pathly_data/core/skills/go.md` → edit a word in Edit tab → click Preview → word appears rendered → click Save → file on disk updated.

**Purpose:** core editing workflow — enables all config + prompt editing without leaving the app.

---

## Phase 3 — Flow editor   ← Conversation: 3

### 3.1 Flow editor shell

**File:** `studio/src/renderer/src/components/FlowEditor/index.tsx`
**Done when:** selecting a flow in sidebar shows the flow editor panel with `[ Visual ]` and `[ YAML ]` tabs.

### 3.2 Visual view

**File:** `studio/src/renderer/src/components/FlowEditor/VisualView.tsx`
**Done when:**
- Parses flow YAML (`states`, `transitions`, `agent_map`, `transition_rules`)
- Renders states as rectangular nodes (state name + agent name below)
- Renders transitions as directed edges; label = artifact name or "default"
- ReactFlow auto-layout positions nodes left-to-right

Install: `npm install reactflow`

Each node renders a ReactFlow source handle (right side) and target handle (left side).
Dragging from a source handle to a target handle creates a new edge:
- New edge label defaults to "default"
- Edge panel slides in immediately on creation so the user can set the artifact trigger

Click node → slide-in panel on right:
- Edit agent name (text input)
- Add/remove transition_rules entries (artifact filename → target state)

Click edge → slide-in panel:
- Edit artifact trigger
- Add/remove transition_actions (skill name + message)

Undo/redo for graph operations:
- Maintain a `history: FlowYaml[]` stack in the store (max 50 entries)
- Push to history on every node add/remove, edge add/remove, or agent name change
- `Cmd/Ctrl+Z` pops the stack and re-renders the graph; `Cmd/Ctrl+Shift+Z` redoes
- Note: CodeMirror handles undo independently inside the YAML tab — do not intercept its keydown events

### 3.3 YAML view

**File:** `studio/src/renderer/src/components/FlowEditor/YamlView.tsx`
**Done when:** CodeMirror loads with YAML language support; js-yaml parse runs on every change; parse error shows red banner at top; Save disabled when error present.

Install: `npm install @codemirror/lang-yaml js-yaml`

Switching Visual → YAML: serialize current graph state back to YAML string.
Switching YAML → Visual: parse YAML and re-render graph.

Save: writes YAML to `src/pathly_data/core/flows/<name>.flow.yaml` via IPC.

**Verify:** open `team.flow.yaml` in Visual tab → 6 nodes visible (STORMING through DONE) → switch to YAML tab → raw YAML visible → edit one state name → red error appears → fix → Save → file on disk updated.

**Purpose:** visual FSM editing — the defining feature of the app for flow authoring.

---

## Phase 4 — Live monitor + Publish   ← Conversation: 4

### 4.1 Top bar

**File:** `studio/src/renderer/src/components/TopBar.tsx`
**Done when:** top bar renders: app title left, topic selector dropdown center, connection status badge + Publish button right.

Topic selector scans `pathly/plans/` via `window.pathly.fs.list` on mount and on 5-second interval. Excludes `.archive/`.

### 4.2 Monitor panel

**File:** `studio/src/renderer/src/components/Monitor/index.tsx`
**Done when:** clicking Monitor in sidebar shows the monitor panel with FsmView + EventLog.

### 4.3 FSM progress bar

**File:** `studio/src/renderer/src/components/Monitor/FsmView.tsx`
**Done when:** renders states as horizontal pills; active state has blue border; completed states show `✓`; blocked state shows `⚠ BLOCKED: <filename>`.

State data flows from Zustand `fsmState` — either from MCP or file watch (both set the same store field).

### 4.4 Event log

**File:** `studio/src/renderer/src/components/Monitor/EventLog.tsx`
**Done when:** renders events as `HH:MM:SS  EVENT_TYPE  detail` rows; scrollable; newest event at bottom; auto-scrolls on new event.

### 4.5 File watcher IPC

**File:** `studio/src/main/ipc/watcher.ts`
**Done when:** `ipcMain.handle('watch:start', path)` starts chokidar watch on that path; on file change, pushes `watch:event` to renderer with new file content.

Install: `npm install chokidar`

Watch both `STATE.json` and `EVENTS.jsonl` for the active topic.
Parse STATE.json → dispatch to `store.setFsmState`.
Parse EVENTS.jsonl (last 50 lines) → dispatch to `store.setEvents`.

### 4.6 MCP client IPC

**File:** `studio/src/main/ipc/mcp.ts`
**Done when:** `ipcMain.handle('mcp:ping')` attempts to call the MCP server and returns `true` within 500ms or `false` on timeout; `mcp:state` returns parsed FsmState or null.

On monitor open: call `mcp:ping` → if true set `monitorSource = 'mcp'`; else set `monitorSource = 'filewatch'` and start watcher.
Poll `mcp:state` every 2 seconds when source = mcp.

Connection status badge: `● MCP live` (green) or `○ File watch` (grey).

### 4.7 Publish IPC

**File:** `studio/src/main/ipc/shell.ts`
**Done when:** `ipcMain.handle('shell:publish', cwd)` spawns `pip install -e .` with args array (no shell), streams stdout/stderr lines to renderer via `shell:output` push event; resolves with exit code.

Renderer: log panel slides up on Publish click, streams lines, shows success/error banner on exit, auto-hides on success after 3 seconds.

**Verify:** click Publish → log panel opens → pip output streams → "Published successfully" banner appears.

**Purpose:** closes the edit-publish loop entirely within the app.
