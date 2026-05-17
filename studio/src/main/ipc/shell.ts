import { ipcMain, app, BrowserWindow } from 'electron'
import { spawn } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'

function isValidProjectPath(dir: string): boolean {
  try {
    const real = fs.realpathSync(dir)
    const home = path.resolve(app.getPath('home'))
    return real.startsWith(home + path.sep) || real === home
  } catch {
    return false
  }
}

export function registerShellHandlers(win: BrowserWindow): void {
  ipcMain.handle('shell:publish', (_event, cwd: string) => {
    if (!isValidProjectPath(cwd)) {
      throw new Error('Invalid project path')
    }
    const proc = spawn('pip', ['install', '-e', '.'], { cwd, stdio: 'pipe' })
    proc.stdout?.on('data', (d: Buffer) => win.webContents.send('shell:output', d.toString()))
    proc.stderr?.on('data', (d: Buffer) => win.webContents.send('shell:output', d.toString()))
    return new Promise((resolve) => proc.on('close', resolve))
  })
}
