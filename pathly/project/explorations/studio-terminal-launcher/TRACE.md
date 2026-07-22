# Trace — studio-terminal-launcher

## Files visited

| File | Relevance |
|---|---|
| `studio/src/main/ipc/terminal.ts` | PTY spawn, ALLOWED_SHELLS, resolveShell() |
| `studio/src/main/ipc/shell.ts` | Detached process launchers (VS Code, wt, wsl) |
| `studio/src/main/preload/index.ts` | contextBridge — terminal IPC contract |
| `studio/src/main/index.ts` | FSM server spawn, app-ready logic |
| `studio/src/renderer/src/types/terminal.ts` | TerminalKind enum |
| `studio/src/renderer/src/lib/launchTerminal.ts` | Kind determination, prompt patterns |
| `studio/src/renderer/src/store/chatStore.ts` | TerminalKind union in store |
| `studio/src/renderer/src/components/topbar/TerminalLauncher.tsx` | Dropdown: Shell, Claude, Codex |
| `studio/src/renderer/src/components/Terminal/BrandIcons.tsx` | ShellIcon, ClaudeIcon, CodexIcon |
| `studio/src/renderer/src/lib/studioSchema.ts` | topbar-shell, topbar-claude-code, topbar-codex items |
| `studio/package.json` | node-pty v3.0.0, xterm v5.5.0, Electron 33 |

## Key code paths

### ALLOWED_SHELLS (terminal.ts line 13)
```
['bash', 'zsh', 'sh', 'pwsh', 'powershell.exe', 'cmd.exe', 'claude', 'codex']
```
Security allowlist — `agy` must be added here or it will be rejected.

### resolveShell() (terminal.ts lines 38–48)
```
if command === 'claude' or 'codex':
  non-Windows → bash -c exec <command>
  Windows     → powershell.exe -NoExit -Command <command>
else:
  return command as-is
```
`agy` needs the same Windows treatment.

### TerminalKind (types/terminal.ts line 6)
```typescript
type TerminalKind = 'shell' | 'claude' | 'codex'
```
Must add `'antigravity'`.

### Kind determination (launchTerminal.ts line 21)
```typescript
command === 'claude' ? 'claude' : command === 'codex' ? 'codex' : 'shell'
```
Must add `command === 'agy' ? 'antigravity' :` branch.

### Prompt patterns (launchTerminal.ts line 72)
```
shell:  ['$ ', '# ', '> ']
claude/codex: ['> ']
```
`agy` prompt pattern to be confirmed (likely `'> '` like other AI CLIs).

### chatStore TerminalKind (chatStore.ts line 20)
```typescript
TerminalKind = 'claude' | 'codex' | 'shell'
```
Must add `'antigravity'`.

### TerminalLauncher dropdown (TerminalLauncher.tsx)
Renders Shell / Claude / Codex options — add Antigravity.

### BrandIcons (BrandIcons.tsx)
Has `ShellIcon`, `ClaudeIcon`, `CodexIcon` — need `AntigravityIcon` (Google `agy` / Antigravity branding).

### studioSchema (studioSchema.ts lines 55–69)
```
'topbar-shell'        line 55
'topbar-claude-code'  line 62
'topbar-codex'        line 69
```
Must add `'topbar-antigravity'`.
