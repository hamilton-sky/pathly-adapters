---
name: Flow Diagram
---
# antigravity-studio — Flow Diagram

## Terminal launch: click → PTY

```
  [Topbar]
  TerminalLauncher.tsx
    Shell | Claude | Codex | Antigravity  ← new button
               |
               | onClick: launchTerminal('agy')
               v
  [lib/launchTerminal.ts]
    command === 'agy' ? 'antigravity'       ← new branch
    → kind = 'antigravity'
    → tab created with AntigravityIcon      ← new icon
               |
               | window.pathly.terminal.spawn(tabId, cwd, 'agy')
               v
  [preload/index.ts]  (contextBridge — unchanged)
               |
               | ipcRenderer.invoke('terminal:spawn', ...)
               v
  [main/ipc/terminal.ts]
    ALLOWED_SHELLS.includes('agy') ✓        ← new entry
    resolveShell('agy')
      Windows  → powershell.exe -NoExit -Command agy  ← new case
      !Windows → bash -c exec agy                     ← new case
               |
               | pty.spawn(shell, args, { cwd, env })
               v
  [node-pty]
    agy process running in PTY
               |
               | PTY output → ipcMain → 'terminal:data'
               v
  [renderer/xterm]
    "> _"  (agy prompt)
```

## Kind system across renderer files

```
  types/terminal.ts
    TerminalKind = 'shell'|'claude'|'codex'|'antigravity'  ← add
          ↓ imported by
  chatStore.ts          launchTerminal.ts      BrandIcons.tsx
  (store target kind)   (kind → tab)           (kind → icon)
          ↓                    ↓                      ↓
  'antigravity' stored   prompt: ['> ']        AntigravityIcon
  in output map          command: 'agy'        (Google G, #1967D2)
          ↓
  studioSchema.ts
    'topbar-antigravity'  ← new item
```
