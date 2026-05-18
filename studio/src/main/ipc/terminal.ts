import { ipcMain, BrowserWindow, app } from 'electron'
import { join } from 'path'

let pty: typeof import('node-pty') | null = null
try {
  pty = require('node-pty')
} catch {
  console.warn('[terminal] node-pty not available')
}

const activePtys = new Map<string, import('node-pty').IPty>()
// Maps tabId → the BrowserWindow that should receive PTY data for that tab
const ptyWindows = new Map<string, BrowserWindow>()

function sendToWindow(tabId: string, channel: string, ...args: unknown[]): void {
  const win = ptyWindows.get(tabId)
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, ...args)
  }
}

export function killAllPtys(): void {
  activePtys.forEach((p) => { try { p.kill() } catch { /* ignore */ } })
  activePtys.clear()
  ptyWindows.clear()
}

export function registerTerminalHandlers(win: BrowserWindow): void {
  ipcMain.handle('terminal:spawn', (_event, tabId: string, cwd: string, command?: string) => {
    if (!pty) throw new Error('node-pty is not available')
    if (activePtys.has(tabId)) return

    const shell = process.platform === 'win32' ? 'powershell.exe' : (command ?? 'bash')
    const shellArgs = process.platform === 'win32' && command ? ['-NoExit', '-Command', command] : []
    const resolvedCwd = cwd || app.getAppPath()

    const ptyProcess = pty.spawn(shell, shellArgs, {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: resolvedCwd,
      env: process.env as Record<string, string>,
    })

    // Default target window is the main window
    ptyWindows.set(tabId, win)

    ptyProcess.onData((data: string) => {
      sendToWindow(tabId, `terminal:data:${tabId}`, data)
    })

    ptyProcess.onExit(() => {
      activePtys.delete(tabId)
      sendToWindow(tabId, 'terminal:exit', tabId)
      ptyWindows.delete(tabId)
    })

    activePtys.set(tabId, ptyProcess)
  })

  ipcMain.on('terminal:write', (_event, tabId: string, data: string) => {
    activePtys.get(tabId)?.write(data)
  })

  ipcMain.handle('terminal:resize', (_event, tabId: string, cols: number, rows: number) => {
    activePtys.get(tabId)?.resize(cols, rows)
  })

  ipcMain.handle('terminal:kill', (_event, tabId: string) => {
    const p = activePtys.get(tabId)
    if (p) { p.kill(); activePtys.delete(tabId); ptyWindows.delete(tabId) }
  })

  ipcMain.handle('terminal:popout', (_event, tabId: string, label: string) => {
    const ptyProcess = activePtys.get(tabId)
    if (!ptyProcess) throw new Error(`No PTY for tab ${tabId}`)

    const popupWin = new BrowserWindow({
      width: 900,
      height: 600,
      title: label,
      backgroundColor: '#1e1e2e',
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    })

    // Route PTY data to popup window from now on
    ptyWindows.set(tabId, popupWin)

    // Load same app with a ?terminal=<tabId> param so renderer shows popup mode
    if (app.isPackaged) {
      void popupWin.loadFile(join(__dirname, '../../renderer/index.html'), {
        query: { terminal: tabId, label },
      })
    } else {
      const devUrl = process.env.ELECTRON_RENDERER_URL ?? 'http://localhost:5173'
      void popupWin.loadURL(`${devUrl}?terminal=${encodeURIComponent(tabId)}&label=${encodeURIComponent(label)}`)
    }

    popupWin.on('closed', () => {
      const p = activePtys.get(tabId)
      if (p) { try { p.kill() } catch { /* ignore */ } activePtys.delete(tabId) }
      ptyWindows.delete(tabId)
    })
  })
}
