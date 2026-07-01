# FLOW_DIAGRAM.md — pathly-studio

---

## Component interaction

```
  Developer
     │
     ▼
  Electron Renderer (React + Zustand)
  ┌─────────────────────────────────────────────┐
  │  TopBar: topic selector / badge / Publish   │
  ├───────────────┬─────────────────────────────┤
  │  Sidebar      │  Main Panel                 │
  │  (Flows,      │  ┌──────────────────────┐   │
  │  Skills,      │  │ Editor               │   │
  │  Agents,      │  │  ConfigForm          │   │
  │  Templates,   │  │  MarkdownEditor      │   │
  │  Monitor)     │  │  MarkdownPreview     │   │
  │               │  ├──────────────────────┤   │
  │               │  │ FlowEditor           │   │
  │               │  │  VisualView          │   │
  │               │  │  YamlView            │   │
  │               │  ├──────────────────────┤   │
  │               │  │ Monitor              │   │
  │               │  │  FsmView             │   │
  │               │  │  EventLog            │   │
  │               │  └──────────────────────┘   │
  └───────┬───────┴──────────────┬──────────────┘
          │ window.pathly.*      │ window.pathly.*
          ▼                      ▼
  contextBridge (preload/index.ts)
          │
          ▼
  Electron Main Process (Node.js)
  ┌─────────────────────────────────────────────┐
  │  ipc/fs.ts     read / write / list          │
  │  ipc/watcher.ts  chokidar → push events     │
  │  ipc/http.ts    stdio HTTP client             │
  │  ipc/shell.ts  pip install subprocess       │
  └────┬──────────────────────────┬─────────────┘
       │                          │
       ▼                          ▼
  src/pathly_data/          pathly/plans/<topic>/
  core/agents/              STATE.json
  core/skills/              EVENTS.jsonl
  core/templates/           feedback/*.md
  core/flows/
       │
       ▼
  pathly-http-server (stdio)
  [Python process — optional]
```

---

## Monitor auto-detect flow

```
  Monitor panel opens
         │
         ▼
  http:ping ──── timeout >500ms ──► monitorSource = filewatch
         │                                │
  response OK                      chokidar watches
         │                         STATE.json + EVENTS.jsonl
         ▼                                │
  monitorSource = http               on change: parse + push
         │                         to Zustand store
  poll http:state every 2s
         │
         ▼
  store.fsmState updated
         │
         ▼
  FsmView + EventLog re-render
```

---

## Save flow (editor)

```
  Developer clicks Save
         │
         ▼
  Editor merges frontmatter + body
  into single string
         │
         ▼
  window.pathly.fs.write(path, content)
         │
         ▼
  Main: path guard check
         │
    ┌────┴────────┐
   pass          reject
    │              │
    ▼              ▼
  write to       error pushed
  path.tmp       to renderer
    │
    ▼
  rename to path (atomic)
    │
    ▼
  store.clearDirty(path)
  ● dot removed from sidebar
```

---

## Publish flow

```
  Developer clicks [↑ Publish]
         │
         ▼
  store.publishing = true
  log panel slides up
         │
         ▼
  shell:publish IPC call
         │
         ▼
  Main: spawn(['pip','install','-e','.'])
         │
  stdout/stderr ──► shell:output push ──► publishLog appended
         │
    exit code 0?
    ┌────┴──────────┐
   yes             no
    │               │
    ▼               ▼
  "Published      "Publish failed"
  successfully"   banner stays
  banner, log     log stays open
  hides in 3s
```
