# REVIEW_FAILURES — antigravity-studio Conv 3 attempt 1

## Critical: Feature correctness (useChatPanel.tsx — from Conv 2 exhaustiveness fixes)

### RF1 — currentTabId / currentOutput missing 'antigravity' branch
File: `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` ~line 87
The ternary chains for `currentTabId` and `currentOutput` have no `'antigravity'` branch and fall through to `shellTabId`/`shellOutput`. Opening an Antigravity tab will silently use the Shell tab's ID and output.

### RF2 — terminalBuffers / idleTimers refs missing 'antigravity' key
File: `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` ~lines 105-106
`terminalBuffers.current` and `idleTimers.current` are initialized without an `'antigravity'` key. The subscription `useEffect` at ~line 132 only iterates `['claude', 'codex', 'shell'] as const` — Antigravity PTY output is never captured.

### RF3 — cleanup missing 'antigravity' key
File: `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` ~line 158
Cleanup resets `terminalBuffers.current` to `{ claude: '', codex: '', shell: '' }` — missing `antigravity`.

### RF4 — renderTerminalCard typed without 'antigravity'
File: `studio/src/renderer/src/components/ChatPanel/useChatPanel.tsx` ~line 504
`renderTerminalCard` is typed `kind: 'claude' | 'codex' | 'shell'` — no Antigravity mini-terminal card can ever be rendered.

## Studio CLAUDE.md violations

### RF5 — AntigravityIcon inline style
`BrandIcons.tsx` ~line 157: `style={{ flexShrink: 0 }}`

### RF6 — New Antigravity button missing type="button"
`TerminalLauncher.tsx` ~line 89
