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
// Maps tabId → accumulated output lines for runner result reporting
const ptyOutput = new Map<string, string[]>()
// Maps tabId → runner metadata registered before spawn
const runnerTabMeta = new Map<string, { run_id: string; topic: string; spawnedAt: number; label: string }>()
// Tracks tabs killed by the user (not by the runner exiting naturally)
const ptyKilledByRunner = new Set<string>()
// Tracks runner tabs that have already shown the autonomous-mode warning
const runnerWarnShown = new Set<string>()

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

/** Resolve the absolute path to agy.exe — checks known install location first, falls back to PATH. */
function resolveAgyPath(): string {
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA ?? ''
    const knownPath = join(localAppData, 'agy', 'bin', 'agy.exe')
    if (fs.existsSync(knownPath)) return knownPath
    // Also check npm bin (our fallback copy)
    const appData = process.env.APPDATA ?? ''
    const npmPath = join(appData, 'npm', 'agy.exe')
    if (fs.existsSync(npmPath)) return npmPath
  }
  return 'agy'  // rely on PATH on non-Windows or if known paths don't exist
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
  if (command === 'agy') {
    const agyExe = resolveAgyPath()
    return { shell: 'powershell.exe', args: ['-NoExit', '-Command', `& '${agyExe}'`] }
  }
  return { shell: 'powershell.exe', args: [] }
}

/** Spawn a specific argv non-interactively — used by the runner so the PTY exits when the agent finishes. */
function resolveRunnerShell(argv: string[]): { shell: string; args: string[] } {
  if (process.platform !== 'win32') {
    return { shell: argv[0], args: argv.slice(1) }
  }
  // Windows: encode as base64 PowerShell command — handles any chars in the prompt (newlines, quotes, etc.)
  // Single-quoted PS strings are fully literal; '' is the only escape (a literal single quote).
  const psArgs = argv.map((a) => `'${a.replace(/'/g, "''")}'`).join(' ')
  const encoded = Buffer.from(`& ${psArgs}`, 'utf16le').toString('base64')
  return { shell: 'powershell.exe', args: ['-EncodedCommand', encoded] }
}

export function killAllPtys(): void {
  activePtys.forEach((p) => { try { p.kill() } catch { /* ignore */ } })
  activePtys.clear()
  ptyWindows.clear()
  ptyOwners.clear()
  ptyOutput.clear()
  runnerTabMeta.clear()
  ptyKilledByRunner.clear()
}

export function registerTerminalHandlers(win: BrowserWindow): void {
  ipcMain.handle('terminal:spawn', (event, tabId: string, cwd: string, command?: string, runnerArgv?: string[]) => {
    if (!pty) throw new Error('node-pty is not available')
    if (activePtys.has(tabId)) {
      throw new Error('Tab already exists')
    }

    if (!cwd) {
      throw new Error('Working directory is required')
    }

    if (!isValidCwd(cwd)) {
      throw new Error('Invalid working directory: ' + cwd)
    }

    let shell: string
    let shellArgs: string[]

    if (runnerArgv && runnerArgv.length > 0) {
      // Runner mode: use full argv so the agent exits when done (non-interactive)
      if (!ALLOWED_SHELLS.has(runnerArgv[0])) {
        throw new Error('Shell not allowed: ' + runnerArgv[0])
      }
      ;({ shell, args: shellArgs } = resolveRunnerShell(runnerArgv))
    } else {
      // Interactive mode: just the adapter name
      if (command !== undefined && !ALLOWED_SHELLS.has(command)) {
        throw new Error('Shell not allowed: ' + command)
      }
      ;({ shell, args: shellArgs } = resolveShell(command))
    }

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
      if (runnerTabMeta.has(tabId)) {
        const lines = ptyOutput.get(tabId) ?? []
        lines.push(data)
        if (lines.length > 500) lines.splice(0, lines.length - 500)
        ptyOutput.set(tabId, lines)
      }
    })

    ptyProcess.onExit(({ exitCode }) => {
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      sendToWindow(tabId, 'terminal:exit', tabId)
      const meta = runnerTabMeta.get(tabId)
      if (meta) {
        const userInitiated = ptyKilledByRunner.has(tabId)
        const stdoutTail = (ptyOutput.get(tabId) ?? []).join('')
        const wallSeconds = (Date.now() - meta.spawnedAt) / 1000
        runnerTabMeta.delete(tabId)
        ptyOutput.delete(tabId)
        ptyKilledByRunner.delete(tabId)
        const label = meta.label || tabId
        const banner = exitCode === 0
          ? `\r\n\x1b[2m──\x1b[0m \x1b[1;32m${label} DONE\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
          : `\r\n\x1b[2m──\x1b[0m \x1b[1;31m${label} ABORTED\x1b[0m \x1b[2m──────────────────────────────\x1b[0m\r\n`
        sendToWindow(tabId, `terminal:data:${tabId}`, banner)
        const postBody = JSON.stringify({
          run_id: meta.run_id,
          topic: meta.topic,
          exit_code: exitCode,
          stdout_tail: stdoutTail,
          wall_seconds: wallSeconds,
          user_initiated: userInitiated,
        })
        const doPost = () => fetch('http://127.0.0.1:8765/runner/terminal/result', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: postBody,
        })
        doPost().catch(() => setTimeout(() => doPost().catch(() => { /* give up */ }), 1000))
      }
      ptyWindows.delete(tabId)
    })

    activePtys.set(tabId, ptyProcess)
  })

  ipcMain.on('terminal:write', (event, tabId: string, data: string) => {
    // Phase 2: only allow the owning sender to write
    if (ptyOwners.get(tabId) !== event.sender.id) return
    const MAX_WRITE = 65536 // 64KB
    if (typeof data !== 'string' || data.length > MAX_WRITE) return
    if (tabId.startsWith('runner-') && !runnerWarnShown.has(tabId)) {
      runnerWarnShown.add(tabId)
      event.sender.send(`terminal:data:${tabId}`, '\r\n\x1b[33m[!] Autonomous mode active — input will be forwarded to the agent\x1b[0m\r\n')
    }
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
      if (runnerTabMeta.has(tabId)) {
        ptyKilledByRunner.add(tabId)
      }
      p.kill()
      activePtys.delete(tabId)
      ptyOwners.delete(tabId)
      ptyWindows.delete(tabId)
    }
  })

  ipcMain.handle('terminal:register-runner', (_event, tabId: string, topic: string, runId: string, label?: string) => {
    runnerTabMeta.set(tabId, { run_id: runId, topic, spawnedAt: Date.now(), label: label ?? tabId })
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
