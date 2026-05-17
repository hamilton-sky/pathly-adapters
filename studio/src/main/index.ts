import { app, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'

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
  registerIpcHandlers()
  createWindow()

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

function registerIpcHandlers(): void {
  ipcMain.handle('fs:pickFolder', async () => {
    const result = await dialog.showOpenDialog({ properties: ['openDirectory'] })
    return result.filePaths[0] ?? null
  })

  ipcMain.handle('shell:openWindow', async (_event, projectPath: string) => {
    createWindow(projectPath)
  })

  // Stubs — full implementation in Conv 2
  ipcMain.handle('fs:read', async (_event, _path: string): Promise<string | null> => {
    return null
  })

  ipcMain.handle('fs:write', async (_event, _path: string, _content: string): Promise<void> => {
    // no-op stub
  })

  ipcMain.handle('fs:list', async (_event, _dir: string): Promise<string[]> => {
    return []
  })
}
