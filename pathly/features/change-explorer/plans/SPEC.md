# ChangeExplorer — Project-Wide Live Diff Viewer

## Problem

When an agent runs a pipeline, it modifies files across the project. Today, the user must open VS Code or a terminal to see what changed. This breaks focus and forces a context switch out of Pathly Studio.

## Goal

A dedicated Pathly Studio panel that shows every file the agent has modified — with split or unified diff — updating live during a run. The user never needs to leave the studio to review agent changes.

---

## User Stories

| # | Story | Stage |
|---|---|---|
| 1 | As a developer, I can open ChangeExplorer at any time and see all uncommitted git changes across the project | Phase 1 |
| 2 | As a developer, I see +N / −N line-count stats per changed file at a glance | Phase 1 |
| 3 | As a developer, I click any file in the list to see its split or unified diff | Phase 1 |
| 4 | As a developer, I can toggle between Split and Unified view (reuses existing ViewToggle) | Phase 1 |
| 5 | As a developer, I can manually refresh the diff list | Phase 1 |
| 6 | As a developer, changes update automatically every 2 seconds while a pipeline run is active | Phase 2 |
| 7 | As a developer, I see a "LIVE" badge when auto-polling is active | Phase 2 |
| 8 | As a developer, polling pauses automatically when the run reaches `done` / `idle` | Phase 2 |

---

## Architecture

### Data flow

```
git diff HEAD (main process)
  → IPC: git:diff { projectRoot }
  → useGitDiff hook (renderer)
  → FileList (left) + FileDiffPane (right)
        ↑                 ↑
   changed file list   SplitDiff / UnifiedDiff
                       (reused from DraftDiffViewer)
```

### Polling strategy

| Runner status | Polling |
|---|---|
| `running` | every 2 s |
| `paused` / `blocked` | every 5 s |
| `idle` / `done` / `error` / `aborted` | none — manual refresh only |

---

## IPC Channel: `git:diff`

**New file:** `studio/src/main/ipc/git.ts`

### Request
```ts
ipcMain.handle('git:diff', async (_event, projectRoot: string): Promise<GitDiffResult>
```

### Implementation
1. Run `git diff HEAD --name-only` to get changed file list
2. For each file: `git show HEAD:<path>` → original content, `fs.readFile(<path>)` → current content
3. Return structured result

### Response shape
```ts
export interface GitDiffFile {
  path: string            // relative to projectRoot, forward slashes
  status: 'M' | 'A' | 'D' | 'R'  // Modified / Added / Deleted / Renamed
  additions: number       // lines added (from git diff --stat)
  deletions: number       // lines removed (from git diff --stat)
  originalContent: string | null   // content at HEAD (null for new files)
  currentContent: string | null    // working-tree content (null for deleted files)
}

export interface GitDiffResult {
  files: GitDiffFile[]
  error?: string          // human-readable, set only on hard failure
}
```

### Error handling
- If `projectRoot` has no git repo → return `{ files: [], error: 'Not a git repository' }`
- If git is not on PATH → return `{ files: [], error: 'git not found' }`
- Per-file read errors are skipped silently (file remains in list with `null` content)

---

## Preload & Type Registration

### `studio/src/main/preload/index.ts`
Add to contextBridge expose:
```ts
git: {
  diff: (projectRoot: string) => ipcRenderer.invoke('git:diff', projectRoot),
}
```

### `studio/src/renderer/src/types/global.d.ts`
Add to `window.pathly`:
```ts
git: {
  diff: (projectRoot: string) => Promise<GitDiffResult>
}
```
Add `GitDiffFile` and `GitDiffResult` interfaces.

---

## Panel Integration

### `App.tsx`
- Add `'change-explorer'` to the `activePanel` union type in `store.ts`
- Add branch to `MainPanel()`:
  ```ts
  if (activePanel === 'change-explorer') return <ChangeExplorer />
  ```
- Keyboard shortcut: **Ctrl+6** → `setActivePanel('change-explorer')`

### Sidebar
- Add nav button for ChangeExplorer (after db-explorer)
- Icon: `GitBranchIcon` or a diff/split icon from Lucide
- Tooltip: `"Change Explorer  Ctrl+6"`

---

## Component Tree

```
studio/src/renderer/src/components/ChangeExplorer/
  index.ts                         barrel export
  ChangeExplorer.tsx               panel shell — horizontal split: FileList + FileDiffPane
  ChangeExplorer.module.css

  FileList/
    FileList.tsx                   left panel — scrollable list of changed files
    FileList.module.css
    FileListItem.tsx               one row: status badge, filename, +N/-N stats
    FileListItem.module.css

  FileDiffPane/
    FileDiffPane.tsx               right panel — ViewToggle + SplitDiff or UnifiedDiff
    FileDiffPane.module.css

  hooks/
    useGitDiff.ts                  data hook — polls git:diff IPC, exposes files + refresh()
    useFileDiff.ts                 data hook — takes GitDiffFile, returns SplitRow[]/UnifiedRow[]

  EmptyState/
    EmptyState.tsx                 shown when files=[] (no changes) or error state
    EmptyState.module.css
```

**Reused from DraftDiffViewer (no duplication):**
- `SplitDiff` / `UnifiedDiff` — render rows
- `computeLineDiff` — line-level diff algorithm
- `toSplitRows` / `toUnifiedRows` from `fileDiffUtils.ts`
- `ViewToggle` — split/unified toggle button group

---

## Component Details

### `ChangeExplorer.tsx`
- Calls `useGitDiff(projectRoot)` where `projectRoot` comes from `useRunnerStore().projectRoot`
- Layout: two-column `flex` — `FileList` (fixed 240px left) + `FileDiffPane` (flex: 1 right)
- Tracks `selectedFile: GitDiffFile | null` in local state
- Header bar: "Changes" title + file count badge + "LIVE" badge (when polling) + refresh button
- Falls back to `EmptyState` when `files.length === 0`

### `FileList.tsx`
- Receives `files: GitDiffFile[]`, `selected: string | null`, `onSelect(path)`
- Renders a `<ul>` of `<FileListItem>` rows
- Selected item highlighted with `data-selected="true"`

### `FileListItem.tsx`
- Status badge: `M` (yellow) / `A` (green) / `D` (red) / `R` (blue) — `data-status` attribute
- Filename: basename bold, directory path muted
- Stats: `+{additions}` green, `−{deletions}` red (hidden when 0)

### `FileDiffPane.tsx`
- Receives `file: GitDiffFile | null`
- Calls `useFileDiff(file)` → `{ splitRows, unifiedRows, loading }`
- Renders `ViewToggle` (split/unified, persisted to localStorage key `ce-view-mode`)
- Renders `SplitDiff` or `UnifiedDiff` based on view mode
- Shows skeleton/spinner while loading
- Shows `EmptyState` when file is null

### `useGitDiff.ts`
```ts
interface UseGitDiff {
  files: GitDiffFile[]
  loading: boolean
  error: string | null
  isLive: boolean           // true when auto-polling
  refresh: () => void
}
function useGitDiff(projectRoot: string | null): UseGitDiff
```
- Gets `status` from `useRunnerStore()`
- Polls on interval when `status === 'running'` (2 s) or `'paused'|'blocked'` (5 s)
- Clears interval on `idle`/`done`/`error`/`aborted`

### `useFileDiff.ts`
```ts
interface UseFileDiff {
  splitRows: SplitRow[]
  unifiedRows: UnifiedRow[]
  loading: boolean
}
function useFileDiff(file: GitDiffFile | null): UseFileDiff
```
- Pure computation: calls `computeLineDiff(original, current)` → wraps into a single `DiffHunk`
- Calls `toSplitRows(hunk)` and `toUnifiedRows(hunk)` from `fileDiffUtils`
- Runs in a `useMemo` (no async needed — content already in the `GitDiffFile` object)

---

## CSS Tokens (no new tokens needed)

| Usage | Token |
|---|---|
| Added lines | `var(--green)` |
| Removed lines | `var(--red)` |
| Modified badge | `var(--yellow)` |
| Renamed badge | `var(--accent)` |
| "LIVE" badge | `var(--accent)` with pulse animation |
| Selected file row | `var(--bg-surface1)` |
| File path directory | `var(--text-muted)` |

---

## Files Changed Summary

### New files (11)
```
studio/src/main/ipc/git.ts
studio/src/renderer/src/components/ChangeExplorer/index.ts
studio/src/renderer/src/components/ChangeExplorer/ChangeExplorer.tsx
studio/src/renderer/src/components/ChangeExplorer/ChangeExplorer.module.css
studio/src/renderer/src/components/ChangeExplorer/FileList/FileList.tsx
studio/src/renderer/src/components/ChangeExplorer/FileList/FileList.module.css
studio/src/renderer/src/components/ChangeExplorer/FileList/FileListItem.tsx
studio/src/renderer/src/components/ChangeExplorer/FileList/FileListItem.module.css
studio/src/renderer/src/components/ChangeExplorer/FileDiffPane/FileDiffPane.tsx
studio/src/renderer/src/components/ChangeExplorer/FileDiffPane/FileDiffPane.module.css
studio/src/renderer/src/components/ChangeExplorer/hooks/useGitDiff.ts
studio/src/renderer/src/components/ChangeExplorer/hooks/useFileDiff.ts
studio/src/renderer/src/components/ChangeExplorer/EmptyState/EmptyState.tsx
studio/src/renderer/src/components/ChangeExplorer/EmptyState/EmptyState.module.css
```

### Modified files (5)
```
studio/src/main/ipc/git.ts               (new IPC handler — also register in main ipc index)
studio/src/main/preload/index.ts         add window.pathly.git
studio/src/renderer/src/types/global.d.ts  add GitDiffFile, GitDiffResult, window.pathly.git
studio/src/renderer/src/App.tsx          add 'change-explorer' panel branch + Ctrl+6 shortcut
studio/src/renderer/src/store/store.ts   add 'change-explorer' to activePanel union
[sidebar nav file]                       add nav button (exact file TBD)
```

---

## Open Questions

1. **Untracked files** — should `git diff HEAD` be supplemented with `git status --short` to also show new untracked files? (Probably yes for Phase 2.)
2. **Large files** — should diffs be truncated at N lines for binary or very large files?
3. **Scope** — diff the whole repo or just the feature's working path? Start with whole repo; filter later.
4. **Run-scoped diff** (Phase 3 idea) — snapshot `git stash` before run starts, restore after to show "exactly what this run changed" independently of manual edits. Deferred.

---

## Phase Plan

| Phase | Scope | Gate |
|---|---|---|
| **1 — Static** | IPC + panel + FileList + FileDiffPane + manual refresh | Typecheck passes, shows real diffs |
| **2 — Live** | Auto-poll tied to runnerStore.status, LIVE badge | End-to-end test: start a run, watch files appear |
| **3 — Run-scoped** | Snapshot before/after run, filter to "this run only" | Deferred — needs FSM cooperation |
