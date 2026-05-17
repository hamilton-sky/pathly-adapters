import { ipcMain, BrowserWindow } from 'electron'
import { join } from 'path'
import { readFileSync } from 'fs'
import chokidar from 'chokidar'

export function registerWatcherHandlers(win: BrowserWindow): void {
  ipcMain.handle('watch:start', (_event, projectPath: string, topic: string) => {
    const base = join(projectPath, 'pathly/plans', topic)
    chokidar
      .watch([join(base, 'STATE.json'), join(base, 'EVENTS.jsonl')])
      .on('change', (filePath) => {
        try {
          const content = readFileSync(filePath, 'utf-8')
          win.webContents.send('watch:event', { path: filePath, content })
        } catch {
          // file may be transiently locked during write
        }
      })
  })
}
