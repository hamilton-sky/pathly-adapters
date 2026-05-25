import { ipcMain, BrowserWindow, app } from 'electron'
import { join } from 'path'
import * as fs from 'fs'
import * as path from 'path'

let pty: typeof import('node-pty') | null = null
try {
  pty = require('node-pty')
} catch {
  console.warn('[terminal] node-pty not available')
}

const ALLOWED_SHELLS = new Set(['bash', 'zsh', 'sh', 'pwsh', 'powershell.exe', 'cmd.exe'])

const activePtys = new Map<string, import('node-pty').IPty>()
// Maps tabId → the BrowserWindow that should receive PTY data for that tab
const ptyWindows = new Map<string, BrowserWindow>()
// Maps tabId → webContentsId of the sender that spawned it
const ptyOwners = new Map<string, number>()

function sendToWindow(tabId: string, channel: string, ...args: unknown[]): void {
  const win = ptyWindows.get(tabId)
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, ...args)
  }
}

function isValidCwd(dir: string): boolean {
  try {
    const real = fs.realpathSync(dir)
    const home = path.resolve(app.getPath('home'))
    return real.startsWith(home + path.sep) || real === home
  } catch {
    return false
  }
}

export function killAllPtys(): void {
  activePtys.forEach((p) => { try { p.kill() } catch { /* ignore */ } })
  activePtys.clear()
  ptyWindows.clear()
  ptyOwners.clear()
}

export function registerTerminalHandlers(win: BrowserWindow): void {
  ipcMain.handle('terminal:spawn', (event, tabId: string, cwd: string, command?: string) => {
    if (!pty) throw new Error('node-pty is not available')
    if (activePtys.has(tabId)) return

    // Phase 1: validate command against allowlist
    if (command !== undefined && !ALLOWED_SHELLS.has(command)) {
      event.sender.send('terminal:error', tabId, 'Shell not allowed')
      return
    }

    const resolvedCwd = cwd || app.getAppPath()

    // Phase 2: validate cwd is within the user's home directory
    if (!isValidCwd(resolvedCwd)) {
      event.sender.send('terminal:error', tabId, 'Invalid working directory')
      return
    }

    // Phase 1: on Windows always use powershell.exe with no user-supplied args
    const shell = process.platform === 'win32' ? 'powershell.exe' : (command ?? 'bash')
    const shellArgs: string[] = []

    const ptyProcess = pty.spawn(shell, shellArgs, {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: resolvedCwd,
      env: process.env as Record<string, string>,
    })

    // Default target window is the main window
    ptyWindows.set(tabId, win)
    // Phase 2: record ownership
    ptyOwners.set(tabId, event.sender.id)

    ptyProcess.onData((data: string) => {
      sendToWindow(tabId, `terminal:data:${tabId}`, data)
    })

    ptyProcess.onExit(() => {
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      sendToWindow(tabId, 'terminal:exit', tabId)
      ptyWindows.delete(tabId)
    })

    activePtys.set(tabId, ptyProcess)
  })

  ipcMain.on('terminal:write', (event, tabId: string, data: string) => {
    // Phase 2: only allow the owning sender to write
    if (ptyOwners.get(tabId) !== event.sender.id) return
    activePtys.get(tabId)?.write(data)
  })

  ipcMain.handle('terminal:resize', (_event, tabId: string, cols: number, rows: number) => {
    activePtys.get(tabId)?.resize(cols, rows)
  })

  ipcMain.handle('terminal:kill', (_event, tabId: string) => {
    const p = activePtys.get(tabId)
    if (p) {
      p.kill()
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
    }
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
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
    })
  })
}
