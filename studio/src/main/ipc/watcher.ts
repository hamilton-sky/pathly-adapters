import { ipcMain, BrowserWindow } from 'electron'
import { join } from 'path'
import { readFileSync } from 'fs'
import chokidar, { FSWatcher } from 'chokidar'

let workspaceWatcher: FSWatcher | null = null
let workspaceRoot: string | null = null
// Debounce timer for workspace:changed. Module-scoped so it can be cancelled when the
// watcher is torn down (pause) or the window closes — otherwise a timer armed by a
// last-moment file change fires after the window is gone and crashes the main process
// with "Object has been destroyed" (win.webContents no longer exists).
let debounceTimer: ReturnType<typeof setTimeout> | null = null
// Per-feature STATE.json/EVENTS.jsonl watchers, keyed by topic. Kept in a registry so
// each can be closed: a bare chokidar.watch() with no reference leaked an FSWatcher on
// every call, and on Windows those open handles block renaming/archiving the feature
// folder the watched files live under (rename fails with EPERM).
const featureWatchers = new Map<string, FSWatcher>()

// Tear down the recursive pathly/ watcher and cancel any pending debounce.
function stopWorkspaceWatcher(): void {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  if (workspaceWatcher) {
    void workspaceWatcher.close()
    workspaceWatcher = null
  }
}

function startWorkspaceWatcher(win: BrowserWindow, projectPath: string): void {
  stopWorkspaceWatcher()
  workspaceRoot = projectPath
  const notify = (): void => {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      // The debounce can outlive the window (close/reload within 300ms of a file change
      // during a board run writing STATE.json/BOARD.json/EVENTS.jsonl). Guard the send —
      // mirrors the win.isDestroyed() check used in terminal.ts.
      if (win.isDestroyed() || win.webContents.isDestroyed()) return
      win.webContents.send('workspace:changed')
    }, 300)
  }
  workspaceWatcher = chokidar
    .watch(join(projectPath, 'pathly'), {
      ignoreInitial: true,
      ignored: /(^|[/\\])\../,
      depth: 4,
    })
    .on('add', notify)
    .on('unlink', notify)
    .on('addDir', notify)
    .on('unlinkDir', notify)
}

export function registerWatcherHandlers(win: BrowserWindow): void {
  // When the window goes away, cancel a pending workspace:changed debounce and drop every
  // watcher so no timer or fs event fires against destroyed webContents.
  win.once('closed', () => {
    stopWorkspaceWatcher()
    for (const w of featureWatchers.values()) void w.close()
    featureWatchers.clear()
  })

  ipcMain.handle('watch:start', (_event, projectPath: string, topic: string) => {
    const send = (filePath: string): void => {
      if (win.isDestroyed() || win.webContents.isDestroyed()) return
      try {
        const content = readFileSync(filePath, 'utf-8')
        win.webContents.send('watch:event', { path: filePath, content })
      } catch {
        // file may be transiently locked during write
      }
    }
    // Close any prior watcher for this topic first — otherwise each call leaked an
    // FSWatcher (none were ever referenced), and on Windows those open handles block
    // archiving the feature folder the watched files live under.
    const existing = featureWatchers.get(topic)
    if (existing) void existing.close()
    // Feature-centric layout keeps STATE.json/EVENTS.jsonl directly under pathly/features/<topic>/.
    const base = join(projectPath, 'pathly/features', topic)
    featureWatchers.set(
      topic,
      chokidar
        .watch([join(base, 'STATE.json'), join(base, 'EVENTS.jsonl')])
        .on('add', send)
        .on('change', send),
    )
  })

  // Close the per-feature watcher for a topic, releasing its handle on
  // pathly/features/<topic>/ so the folder can be renamed/archived on Windows.
  ipcMain.handle('watch:stopFeature', async (_event, topic: string) => {
    const w = featureWatchers.get(topic)
    if (w) {
      await w.close()
      featureWatchers.delete(topic)
    }
  })

  ipcMain.handle('watch:workspace', (_event, projectPath: string) => {
    startWorkspaceWatcher(win, projectPath)
  })

  // Release the recursive pathly/ watcher's handles (e.g. right before archiving a
  // feature folder). On Windows an open handle anywhere under a directory blocks
  // renaming that directory, so the recursive watcher must be dropped for the rename.
  ipcMain.handle('watch:pauseWorkspace', async () => {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (workspaceWatcher) {
      await workspaceWatcher.close()
      workspaceWatcher = null
    }
  })

  // Re-arm the workspace watcher after a pause. Uses the last-watched root when no
  // path is passed, so callers can pause/resume without re-plumbing the project path.
  ipcMain.handle('watch:resumeWorkspace', (_event, projectPath?: string) => {
    const root = projectPath ?? workspaceRoot
    if (root) startWorkspaceWatcher(win, root)
  })
}
