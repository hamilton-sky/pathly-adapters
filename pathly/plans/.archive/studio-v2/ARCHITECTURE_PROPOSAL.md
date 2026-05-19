# ARCHITECTURE_PROPOSAL — studio-v2

This document covers the cross-layer architectural decisions required for Conv 5
(Terminal panel). It is the one story that touches main process, preload, and renderer
in a way that requires explicit design up-front.

All other conversations (1–4) are single-layer renderer changes or minor Python fixes
and do not require an architecture proposal.

---

## Scope

Story S8 — Terminal panel (VS Code-style, bottom of Studio).

---

## Layer map

```
┌─────────────────────────────────────────────────────────────┐
│  Renderer process (xterm.js, React, Zustand)                │
│                                                             │
│  Terminal/index.tsx          terminalStore.ts               │
│  - Tab bar UI                - open: boolean                │
│  - xterm.js instances        - tabs: Tab[]                  │
│  - Drag-to-resize            - activeTabId                  │
│  - Keyboard shortcut         - toggle/add/close/setActive   │
│                                                             │
│  window.pathly.terminal.*  (calls via contextBridge)        │
└────────────────────┬────────────────────────────────────────┘
                     │ IPC (contextBridge / ipcRenderer)
┌────────────────────▼────────────────────────────────────────┐
│  Preload process                                            │
│                                                             │
│  preload/index.ts                                           │
│  - Extends window.pathly with window.pathly.terminal.*      │
│  - Methods: spawn, write, resize, kill, onData              │
│  - onData uses ipcRenderer.on(channel, callback)            │
└────────────────────┬────────────────────────────────────────┘
                     │ ipcMain.handle / webContents.send
┌────────────────────▼────────────────────────────────────────┐
│  Main process (Node.js, node-pty)                           │
│                                                             │
│  main/index.ts                                              │
│  - ptyMap: Map<tabId, IPty>                                 │
│  - terminal:spawn → pty.spawn("powershell.exe", [], opts)   │
│  - terminal:write → ptyMap.get(tabId).write(data)           │
│  - terminal:resize → ptyMap.get(tabId).resize(cols, rows)   │
│  - terminal:kill → ptyMap.get(tabId).kill(); map.delete     │
│  - PTY onData → webContents.send("terminal:data", tabId, d) │
└─────────────────────────────────────────────────────────────┘
```

---

## IPC channel design

All channels prefixed `terminal:` to avoid collision with existing Pathly IPC.

| Channel | Direction | Payload | Handler |
|---------|-----------|---------|---------|
| `terminal:spawn` | renderer → main | `{ tabId, cwd }` | `ipcMain.handle` → returns `tabId` |
| `terminal:write` | renderer → main | `{ tabId, data: string }` | `ipcMain.handle` or `ipcMain.on` |
| `terminal:resize` | renderer → main | `{ tabId, cols, rows }` | `ipcMain.handle` |
| `terminal:kill` | renderer → main | `{ tabId }` | `ipcMain.handle` |
| `terminal:data` | main → renderer | `{ tabId, data: string }` | `webContents.send` → `ipcRenderer.on` |

`terminal:write` can be fire-and-forget (`ipcMain.on`) rather than a `handle` to
avoid blocking the renderer on every keystroke.

---

## PTY process management

- One `Map<string, IPty>` in main process scope (module-level singleton).
- `tabId` is a `crypto.randomUUID()` generated in the renderer before `spawn` is called.
- PTY exit handler: main sends `terminal:exit` event to renderer; renderer shows
  "[process exited]" in the xterm instance but does not close the tab.
- On app quit: iterate ptyMap and call `.kill()` on each to avoid orphaned processes.

---

## xterm.js integration

- One `Terminal` instance (xterm.js) per tab, stored in a React ref map keyed by tabId.
- `FitAddon` from `xterm-addon-fit` auto-sizes xterm to its container; call
  `fitAddon.fit()` on panel resize and on tab switch.
- xterm `onData` callback (user keystrokes) → `window.pathly.terminal.write(tabId, data)`.
- `window.pathly.terminal.onData(tabId, callback)` → xterm `terminal.write(data)`.
- Each xterm instance must be disposed on tab close to prevent memory leaks.

---

## App.tsx layout change

Current layout (inferred from scout findings):
```
flex-column
  TopBar
  body (flex-row)
    Sidebar
    main content
```

New layout:
```
flex-column
  TopBar
  body (flex-row, flex: 1, overflow: hidden)
    Sidebar
    main content
  Terminal panel (flex-shrink: 0, height: terminalHeight px)
```

- `terminalHeight` lives in local App state (initialized to 260, clamped 80–800).
- Drag handle: `onMouseDown` on the top border starts a global `mousemove` listener
  that updates `terminalHeight`. `onMouseUp` cleans up the listener.
- Terminal panel renders unconditionally in the DOM (to keep PTY sessions alive)
  but has `display: none` when `terminalStore.open === false`. This preserves the
  xterm.js instances without unmounting.

---

## native module rebuild

`node-pty` is a native Node.js addon. In Electron it must be rebuilt against the
Electron Node ABI, not the system Node ABI.

- Add `electron-rebuild` as a dev dependency (or use `@electron/rebuild`).
- Add a `postinstall` script in `studio/package.json`:
  `"postinstall": "electron-rebuild -f -w node-pty"`
- In `electron.vite.config.ts`, add `node-pty` to `build.rollupOptions.external`
  for the main process target so Vite does not try to bundle the native `.node` file.

---

## Error handling

| Failure mode | Behavior |
|---|---|
| node-pty not rebuilt / missing | `terminal:spawn` IPC throws; renderer catches and renders error message in panel |
| PTY process exits unexpectedly | Main sends `terminal:exit`; renderer shows "[process exited]" in tab |
| Renderer calls `write` after `kill` | Main silently ignores (tabId not in ptyMap) |
| Panel resized below 80px | Clamped in drag handler; xterm `fit()` called after clamp |
| Tab closed with running process | `terminal:kill` sent before removing from store |

---

## Open questions (resolved)

All architectural questions for this feature have been resolved by the scout findings
and the analysis above. No ARCH_QUESTION blocks are needed.

If the builder encounters a conflict between `node-pty` ABI versions and the installed
Electron version, direct the user to `/meet architect` for dependency resolution.
