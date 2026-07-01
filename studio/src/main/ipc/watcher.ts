import { ipcMain, BrowserWindow } from 'electron'
import { join } from 'path'
import { readFileSync } from 'fs'
import chokidar, { FSWatcher } from 'chokidar'

let workspaceWatcher: FSWatcher | null = null

export function registerWatcherHandlers(win: BrowserWindow): void {
  ipcMain.handle('watch:start', (_event, projectPath: string, topic: string) => {
    const send = (filePath: string): void => {
      try {
        const content = readFileSync(filePath, 'utf-8')
        win.webContents.send('watch:event', { path: filePath, content })
      } catch {
        // file may be transiently locked during write
      }
    }
    // Feature-centric layout keeps STATE.json/EVENTS.jsonl directly under
    // pathly/features/<topic>/; legacy features keep them under pathly/plans/<topic>/.
    // Watch both so the live FSM view updates wherever the feature lives.
    const bases = [
      join(projectPath, 'pathly/features', topic),
      join(projectPath, 'pathly/plans', topic),
    ]
    const targets = bases.flatMap((base) => [join(base, 'STATE.json'), join(base, 'EVENTS.jsonl')])
    chokidar
      .watch(targets)
      .on('add', send)
      .on('change', send)
  })

  ipcMain.handle('watch:workspace', (_event, projectPath: string) => {
    if (workspaceWatcher) {
      void workspaceWatcher.close()
      workspaceWatcher = null
    }
    let debounceTimer: ReturnType<typeof setTimeout> | null = null
    const notify = (): void => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
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
  })
}
