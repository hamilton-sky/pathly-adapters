## Review — send-to-agent-diff (conv 3)

**Result: PASS**

### Checks passed
- IPC triangle complete: `fs:moveToParent` handler in fs.ts, exposed in preload/index.ts:96, typed in global.d.ts:97
- CommentsPanel.tsx: `onDraftReady` correctly wired via `terminal.onExit` → `fs.read(.draft)` → callback
- Editor/index.tsx: `DraftDiffViewer` mounted conditionally, `handleDiffApply` + `handleDiffDiscard` correct
- commentUtils.ts: `buildSendPrompt` writes to `.draft` extension
- All `<button>` elements have explicit `type="button"`
- No inline `style={{}}` props
- ARIA attributes present (modal, tabs, expand buttons)
- All new components under 150 lines

### Issue fixed during review
- `DraftHunkCard.tsx:38` — CSS variant pattern: replaced `${styles[hunk.status]}` class lookup with `data-status={hunk.status}` attribute + CSS attribute selectors (studio/CLAUDE.md non-negotiable rule)

### Commit
`ea5adbd7` fix(studio): replace DraftHunkCard class variant with data-status attribute
