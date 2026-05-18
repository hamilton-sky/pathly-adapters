import { ipcMain, BrowserWindow } from 'electron'
import { app } from 'electron'

let pty: typeof import('node-pty') | null = null
try {
  pty = require('node-pty')
} catch {
  console.warn('[terminal] node-pty not available')
}

const activePtys = new Map<string, import('node-pty').IPty>()

export function registerTerminalHandlers(win: BrowserWindow): void {
  ipcMain.handle('terminal:spawn', (_event, tabId: string, cwd: string) => {
    if (!pty) throw new Error('node-pty is not available')
    if (activePtys.has(tabId)) return

    const shell = process.platform === 'win32' ? 'powershell.exe' : 'bash'
    const resolvedCwd = cwd || app.getAppPath()

    const ptyProcess = pty.spawn(shell, [], {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: resolvedCwd,
      env: process.env as Record<string, string>
    })

    ptyProcess.onData((data: string) => {
      if (!win.isDestroyed()) {
        win.webContents.send(`terminal:data:${tabId}`, data)
      }
    })

    ptyProcess.onExit(() => {
      activePtys.delete(tabId)
    })

    activePtys.set(tabId, ptyProcess)
  })

  ipcMain.handle('terminal:write', (_event, tabId: string, data: string) => {
    const ptyProcess = activePtys.get(tabId)
    if (ptyProcess) {
      ptyProcess.write(data)
    }
  })

  ipcMain.handle('terminal:resize', (_event, tabId: string, cols: number, rows: number) => {
    const ptyProcess = activePtys.get(tabId)
    if (ptyProcess) {
      ptyProcess.resize(cols, rows)
    }
  })

  ipcMain.handle('terminal:kill', (_event, tabId: string) => {
    const ptyProcess = activePtys.get(tabId)
    if (ptyProcess) {
      ptyProcess.kill()
      activePtys.delete(tabId)
    }
  })
}
