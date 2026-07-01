---
name: Happy Flow
---
# antigravity-studio — Happy Flow

## Ideal journey: opening an Antigravity terminal

### 1. User opens Pathly Studio
The topbar shows four terminal launcher buttons: **Shell**, **Claude**, **Codex**, **Antigravity**.

### 2. User clicks "Antigravity"
The `TerminalLauncher` dropdown (or direct button) fires `launchTerminal('agy')`.

### 3. Kind is determined
`launchTerminal.ts` evaluates:
```
command === 'agy' ? 'antigravity' : ...
```
Kind = `'antigravity'`. A new terminal tab is created with the Antigravity brand icon (Google G, blue).

### 4. IPC call to main process
`window.pathly.terminal.spawn(tabId, projectPath, 'agy')` is sent via the preload bridge.

### 5. Main process spawns PTY
`terminal.ts` validates `'agy'` against `ALLOWED_SHELLS` (passes), then:
- **Windows:** `pty.spawn('powershell.exe', ['-NoExit', '-Command', 'agy'], { cwd: projectPath })`
- **Linux/macOS:** `pty.spawn('bash', ['-c', 'exec agy'], { cwd: projectPath })`

### 6. Terminal is ready
The `agy` prompt appears in the xterm panel:
```
Antigravity CLI 2.0.x
> _
```
`launchTerminal.ts` detects the `'> '` prompt pattern and marks the terminal as ready.

### 7. User types a Pathly command
```
> Use Pathly go
```
The FSM routes the message and the Pathly workflow continues inside the Antigravity terminal.
