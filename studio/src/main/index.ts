import { app, BrowserWindow, ipcMain, dialog, clipboard, Menu, globalShortcut } from 'electron'
import { join } from 'path'
import { registerFsHandlers } from './ipc/fs'
import { registerWatcherHandlers } from './ipc/watcher'
import { registerFsmHandlers } from './ipc/fsm'
import { registerShellHandlers } from './ipc/shell'
import { registerTerminalHandlers, killAllPtys } from './ipc/terminal'
import { spawn, ChildProcess, execSync } from 'child_process'
import net from 'net'
import { getPythonPath } from './python'
import { registerSetupHandlers } from './setup'
import { registerAutomationHandlers } from './ipc/automation'
import { registerLlmHandlers } from './ipc/llm'
import { registerBrightskyHandlers } from './ipc/brightsky'
import { autoUpdater } from 'electron-updater'

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let fsmServer: ChildProcess | null = null

const FSM_BASE = `http://127.0.0.1:${process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765'}`

function isFsmRunning(): Promise<boolean> {
  return new Promise((resolve) => {
    const port = parseInt(process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765', 10)
    const s = net.connect(port, '127.0.0.1', () => { s.destroy(); resolve(true) })
    s.on('error', () => resolve(false))
  })
}

async function shutdownExistingFsm(): Promise<void> {
  try {
    await fetch(`${FSM_BASE}/shutdown`, { method: 'POST', signal: AbortSignal.timeout(800) })
    await new Promise((r) => setTimeout(r, 400))
  } catch {
    // Server didn't respond — already gone or too old to have /shutdown
  }
}

function forceKillPort(port: number): void {
  try {
    if (process.platform === 'win32') {
      const out = execSync('netstat -ano', { encoding: 'utf8' })
      const match = out.split('\n').find((l) => l.includes(`:${port}`) && l.includes('LISTENING'))
      const pid = match?.trim().split(/\s+/).pop()
      if (pid && /^\d+$/.test(pid)) execSync(`taskkill /PID ${pid} /F`, { stdio: 'ignore' })
    } else {
      execSync(`lsof -ti:${port} | xargs kill -9`, { stdio: 'ignore' })
    }
  } catch { /* already gone */ }
}

function startFsmServer(): void {
  fsmServer = spawn(getPythonPath(), ['-m', 'pathly_orchestrator.http_server'], {
    env: { ...process.env },
    stdio: 'pipe'
  })
  fsmServer.stdout?.on('data', (d: Buffer) => console.log('[FSM]', d.toString().trim()))
  fsmServer.stderr?.on('data', (d: Buffer) => console.log('[FSM]', d.toString().trim()))
  fsmServer.on('exit', (code) => {
    console.log(`[FSM] server exited (code ${code})`)
    fsmServer = null
  })
}

function createWindow(projectPath?: string): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 640,
    minHeight: 420,
    title: 'Pathly Studio',
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#0B0F1A',       // darkTheme.bgMantle
      symbolColor: '#E2E8F0', // darkTheme.textPrimary
      height: 36,
    },
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      experimentalFeatures: true
    }
  })
  Menu.setApplicationMenu(null)

  if (isDev) {
    const devServerUrl = process.env['ELECTRON_RENDERER_URL'] ?? 'http://localhost:5173'
    const url = projectPath
      ? `${devServerUrl}?PROJECT_PATH=${encodeURIComponent(projectPath)}`
      : devServerUrl
    win.loadURL(url)
  } else {
    const indexPath = join(__dirname, '../renderer/index.html')
    if (projectPath) {
      win.loadFile(indexPath, { query: { PROJECT_PATH: projectPath } })
    } else {
      win.loadFile(indexPath)
    }
  }

  return win
}

app.whenReady().then(async () => {
  const alreadyRunning = await isFsmRunning()
  if (alreadyRunning) {
    console.log('[FSM] server already running — shutting down stale instance')
    await shutdownExistingFsm()
    const stillRunning = await isFsmRunning()
    if (stillRunning) {
      console.log('[FSM] graceful shutdown failed — force-killing port')
      const port = parseInt(process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765', 10)
      forceKillPort(port)
      await new Promise((r) => setTimeout(r, 300))
    }
  }
  startFsmServer()

  const mainWin = createWindow()
  registerIpcHandlers(mainWin)

  // Check for updates in production (silent — notifies user only when update is ready)
  if (!isDev) {
    autoUpdater.checkForUpdatesAndNotify()
  }

  if (isDev) {
    mainWin.webContents.openDevTools({ mode: 'detach' })
    globalShortcut.register('F12', () => {
      const focused = BrowserWindow.getFocusedWindow()
      if (focused) focused.webContents.toggleDevTools()
    })
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  killAllPtys()
  if (fsmServer) {
    fsmServer.kill()
    fsmServer = null
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

function registerIpcHandlers(win: BrowserWindow): void {
  ipcMain.handle('fs:pickFolder', async () => {
    const result = await dialog.showOpenDialog({ properties: ['openDirectory'] })
    return result.filePaths[0] ?? null
  })

  ipcMain.handle('shell:openWindow', async (_event, projectPath: string) => {
    createWindow(projectPath)
  })

  ipcMain.handle('window:setTitleBarOverlay', (_e, opts: { color: string; symbolColor: string }) => {
    win.setTitleBarOverlay({ ...opts, height: 36 })
  })

  ipcMain.handle('clipboard:read', () => clipboard.readText())
  ipcMain.handle('clipboard:write', (_event, text: string) => { clipboard.writeText(text) })
  ipcMain.handle('clipboard:readImagePath', async () => {
    const img = clipboard.readImage()
    if (img.isEmpty()) return null
    const os = await import('os')
    const fsSync = await import('fs')
    const { join } = await import('path')
    const tmpPath = join(os.tmpdir(), `pathly-img-${Date.now()}.png`)
    fsSync.writeFileSync(tmpPath, img.toPNG())
    return tmpPath
  })

  registerFsHandlers()
  registerWatcherHandlers(win)
  registerFsmHandlers()
  registerShellHandlers(win)
  registerTerminalHandlers(win)
  registerSetupHandlers()
  registerAutomationHandlers(win)
  registerLlmHandlers()
  registerBrightskyHandlers(win)
}
