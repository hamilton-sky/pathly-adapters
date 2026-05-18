# REVIEW_FAILURES — studio-v2 — conversation 6

Generated: 2026-05-18

---

## Violations

### V1 — Type contract: `FsmEvent.result` missing from interface
- **File:** `studio/src/renderer/src/types/index.ts:55-63`
- **Rule:** Type-contract — components may not access fields undeclared on the shared interface
- **Detail:** `EventLog.tsx` reads `ev.result` at lines 10–12 (`ev.result === 'PASS'`, `ev.result === 'DONE'`), but `FsmEvent` does not declare a `result` field. TypeScript will reject this access. Fix: add `result?: 'PASS' | 'DONE' | string` to the `FsmEvent` interface.

### V2 — Error handling: `handleDelete()` silently swallows IPC errors
- **File:** `studio/src/renderer/src/components/Sidebar.tsx:172-179`
- **Rule:** Architecture convention — async errors must surface to user (not silently fail)
- **Detail:** `await window.pathly.fs.delete(item.path)` is not wrapped in try-catch. If the IPC call throws, the error is unhandled, `loadItems()` is never called, and the user receives no feedback.

### V3 — Error handling: `handleRename()` silently swallows IPC errors
- **File:** `studio/src/renderer/src/components/Sidebar.tsx:156-170`
- **Rule:** Architecture convention — async errors must surface to user (not silently fail)
- **Detail:** `window.pathly.fs.write()` and `window.pathly.fs.delete()` inside `handleRename()` are awaited without any catch. A partial failure (write succeeds, delete throws) can silently leave duplicate files and gives the user no error feedback.

### V4 — IPC handler: `fs:delete` missing `async` keyword
- **File:** `studio/src/main/ipc/fs.ts:68`
- **Rule:** IPC handler convention — all `ipcMain.handle` callbacks must use `async (_event, ...)`
- **Detail:** `ipcMain.handle('fs:delete', (_event, filePath: string) => {` — missing `async`. All other handlers in the same file use `async`. While functionally equivalent (Electron resolves the returned promise), this diverges from the established contract.

### V5 — IPC handler: `fs:delete` uses non-standard error message
- **File:** `studio/src/main/ipc/fs.ts:69`
- **Rule:** IPC security convention — path-safety error message must be `'Path outside home directory is not allowed'`
- **Detail:** `throw new Error('Path not allowed')` — all other path guards in `fs.ts` throw `'Path outside home directory is not allowed'`. This diverges from the documented project convention.

---

## Warnings (non-blocking)

- `studio/src/renderer/src/components/Monitor/EventLog.tsx:8` — `AGENT_SPAWNED` event type not handled in `eventColor()`; falls through to `textSecondary` default. Acceptable but noted.
- `studio/src/renderer/src/components/Sidebar.tsx:119-148` — `handleInlineCreate()` and `handleInlineCreatePlan()` also lack try-catch around `window.pathly.fs.write()` calls. Same silent-failure risk as V2/V3.

---

## Pass

- Layer dependency direction: clean throughout renderer layer
- IPC channel naming: `domain:action` pattern followed consistently
- `makeStyles(t: Theme)` styling pattern: applied correctly in all changed files
- Zustand store: interface-driven, persist middleware, named hook export
- `projectPath` null-guard in `Monitor/index.tsx:125`: safe by control flow
- No hardcoded credentials or secrets detected
