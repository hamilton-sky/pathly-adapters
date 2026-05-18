import { app, BrowserWindow, ipcMain, dialog, clipboard } from 'electron'
import { join } from 'path'
import { registerFsHandlers } from './ipc/fs'
import { registerWatcherHandlers } from './ipc/watcher'
import { registerMcpHandlers } from './ipc/mcp'
import { registerShellHandlers } from './ipc/shell'
import { registerTerminalHandlers, killAllPtys } from './ipc/terminal'
import { spawn, ChildProcess } from 'child_process'
import net from 'net'
import { getPythonPath } from './python'
import { registerSetupHandlers } from './setup'

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let fsmServer: ChildProcess | null = null

function isFsmRunning(): Promise<boolean> {
  return new Promise((resolve) => {
    const port = parseInt(process.env['PATHLY_FSM_HTTP_PORT'] ?? '8765', 10)
    const s = net.connect(port, '127.0.0.1', () => { s.destroy(); resolve(true) })
    s.on('error', () => resolve(false))
  })
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
    title: 'Pathly Studio',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

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
  if (!alreadyRunning) {
    startFsmServer()
  } else {
    console.log('[FSM] server already running, skipping spawn')
  }

  const mainWin = createWindow()
  registerIpcHandlers(mainWin)

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

  ipcMain.handle('clipboard:read', () => clipboard.readText())
  ipcMain.handle('clipboard:write', (_event, text: string) => { clipboard.writeText(text) })

  registerFsHandlers()
  registerWatcherHandlers(win)
  registerMcpHandlers()
  registerShellHandlers(win)
  registerTerminalHandlers(win)
  registerSetupHandlers()
}
