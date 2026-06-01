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

const ALLOWED_SHELLS = new Set(['bash', 'zsh', 'sh', 'pwsh', 'powershell.exe', 'cmd.exe', 'claude', 'codex', 'agy'])

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

function resolveShell(command: string | undefined): { shell: string; args: string[] } {
  if (process.platform !== 'win32') {
    if (command === 'claude' || command === 'codex' || command === 'agy') {
      return { shell: 'bash', args: ['-c', `exec ${command}`] }
    }
    return { shell: command ?? 'bash', args: [] }
  }
  if (command === 'claude') return { shell: 'powershell.exe', args: ['-NoExit', '-Command', 'claude'] }
  if (command === 'codex')  return { shell: 'powershell.exe', args: ['-NoExit', '-Command', 'codex'] }
  if (command === 'agy')    return { shell: 'powershell.exe', args: ['-NoExit', '-Command', 'agy'] }
  return { shell: 'powershell.exe', args: [] }
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
    if (activePtys.has(tabId)) {
      throw new Error('Tab already exists')
    }

    // Phase 1: validate command against allowlist
    if (command !== undefined && !ALLOWED_SHELLS.has(command)) {
      throw new Error('Shell not allowed: ' + command)
    }

    if (!cwd) {
      throw new Error('Working directory is required')
    }

    // Phase 2: validate cwd is within the user's home directory
    if (!isValidCwd(cwd)) {
      throw new Error('Invalid working directory: ' + cwd)
    }

    const { shell, args: shellArgs } = resolveShell(command)

    const ptyProcess = pty.spawn(shell, shellArgs, {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: cwd,
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
    const MAX_WRITE = 65536 // 64KB
    if (typeof data !== 'string' || data.length > MAX_WRITE) return
    activePtys.get(tabId)?.write(data)
  })

  ipcMain.handle('terminal:resize', (event, tabId: string, cols: number, rows: number) => {
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const safeCols = Math.max(1, Math.min(500, Math.floor(Number(cols))))
    const safeRows = Math.max(1, Math.min(500, Math.floor(Number(rows))))
    activePtys.get(tabId)?.resize(safeCols, safeRows)
  })

  ipcMain.handle('terminal:kill', (event, tabId: string) => {
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const p = activePtys.get(tabId)
    if (p) {
      p.kill()
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
    }
  })

  ipcMain.handle('terminal:popout', (event, tabId: string, label: string) => {
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const ptyProcess = activePtys.get(tabId)
    if (!ptyProcess) throw new Error(`No PTY for tab ${tabId}`)

    const safeLabel = String(label ?? '').replace(/[\x00-\x1F\x7F]/g, '').slice(0, 100) || 'Terminal'

    const popupWin = new BrowserWindow({
      width: 900,
      height: 600,
      title: safeLabel,
      backgroundColor: '#1e1e2e',
      show: false,
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    })

    popupWin.once('ready-to-show', () => {
      popupWin.show()
      popupWin.focus()
    })

    // Route PTY data to popup window and transfer ownership
    ptyWindows.set(tabId, popupWin)
    ptyOwners.set(tabId, popupWin.webContents.id)

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
