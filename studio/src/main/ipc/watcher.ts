import { ipcMain, BrowserWindow } from 'electron'
import { join } from 'path'
import { readFileSync } from 'fs'
import chokidar from 'chokidar'

export function registerWatcherHandlers(win: BrowserWindow): void {
  ipcMain.handle('watch:start', (_event, projectPath: string, topic: string) => {
    const base = join(projectPath, 'pathly/plans', topic)
    const send = (filePath: string): void => {
      try {
        const content = readFileSync(filePath, 'utf-8')
        win.webContents.send('watch:event', { path: filePath, content })
      } catch {
        // file may be transiently locked during write
      }
    }
    chokidar
      .watch([join(base, 'STATE.json'), join(base, 'EVENTS.jsonl')])
      .on('add', send)
      .on('change', send)
  })
}
