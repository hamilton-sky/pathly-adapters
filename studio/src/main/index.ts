import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import { registerFsHandlers } from './ipc/fs'
import { registerWatcherHandlers } from './ipc/watcher'
import { registerMcpHandlers } from './ipc/mcp'
import { registerShellHandlers } from './ipc/shell'

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

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
    win.webContents.openDevTools()
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

app.whenReady().then(() => {
  const mainWin = createWindow()
  registerIpcHandlers(mainWin)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })

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

  registerFsHandlers()
  registerWatcherHandlers(win)
  registerMcpHandlers()
  registerShellHandlers(win)
}
