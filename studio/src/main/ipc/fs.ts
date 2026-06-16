import { ipcMain, app } from 'electron'
import * as fs from 'fs'
import * as path from 'path'

function resolvePath(filePath: string): string {
  let resolved: string
  try {
    resolved = fs.realpathSync(filePath)
  } catch {
    try {
      const parent = fs.realpathSync(path.dirname(filePath))
      resolved = path.join(parent, path.basename(filePath))
    } catch {
      // Parent doesn't exist either — use normalized absolute path
      resolved = path.resolve(filePath)
    }
  }
  return resolved
}

function isWithin(filePath: string, rootPath: string): boolean {
  // Windows paths are case-insensitive; normalize before comparing
  const norm = (p: string): string => process.platform === 'win32' ? p.toLowerCase() : p
  const resolved = norm(resolvePath(filePath))
  const root = norm(path.resolve(rootPath))
  return resolved.startsWith(root + path.sep) || resolved === root
}

function isPathSafe(filePath: string): boolean {
  return isWithin(filePath, app.getPath('home'))
}

function libraryRoot(): string {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'pathly-library')
    : path.resolve(app.getAppPath(), '..')
}

function isReadablePathSafe(filePath: string): boolean {
  return isPathSafe(filePath) || (app.isPackaged && isWithin(filePath, libraryRoot()))
}

export function registerFsHandlers(): void {
  ipcMain.handle('fs:read', async (_event, filePath: string): Promise<string | null> => {
    if (!isReadablePathSafe(filePath)) {
      throw new Error('Path outside home directory is not allowed')
    }
    try {
      return fs.readFileSync(filePath, 'utf-8')
    } catch (err: unknown) {
      if ((err as NodeJS.ErrnoException).code === 'ENOENT') return null
      throw err
    }
  })

  ipcMain.handle('fs:write', async (_event, filePath: string, content: string): Promise<void> => {
    if (!isPathSafe(filePath)) {
      throw new Error('Path outside home directory is not allowed')
    }
    fs.mkdirSync(path.dirname(filePath), { recursive: true })
    const tmpPath = filePath + '.tmp'
    fs.writeFileSync(tmpPath, content, 'utf-8')
    fs.renameSync(tmpPath, filePath)
  })

  ipcMain.handle('fs:list', async (_event, dir: string): Promise<string[]> => {
    if (!isReadablePathSafe(dir)) {
      throw new Error('Path outside home directory is not allowed')
    }
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true })
      return entries.filter((e) => e.isFile()).map((e) => e.name)
    } catch {
      return []   // directory doesn't exist — not an error
    }
  })

  ipcMain.handle('fs:listDirs', async (_event, dir: string): Promise<string[]> => {
    if (!isReadablePathSafe(dir)) {
      throw new Error('Path outside home directory is not allowed')
    }
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true })
      return entries
        .filter((e) => e.isDirectory() && !e.name.startsWith('.'))
        .map((e) => e.name)
    } catch {
      return []
    }
  })

  ipcMain.handle('fs:delete', async (_event, filePath: string) => {
    if (!isPathSafe(filePath)) throw new Error('Path outside home directory is not allowed')
    return fs.promises.rm(filePath, { recursive: true, force: true })
  })

  ipcMain.handle('fs:moveToParent', async (_event, filePath: string): Promise<string> => {
    if (!isPathSafe(filePath)) throw new Error('Path outside home directory is not allowed')
    const parentDir = path.dirname(path.dirname(filePath))
    const fileName = path.basename(filePath)
    const destPath = path.join(parentDir, fileName)
    if (!isPathSafe(destPath)) throw new Error('Destination outside home directory is not allowed')
    if (filePath === destPath) throw new Error('File is already at root of section')
    const content = fs.readFileSync(filePath, 'utf-8')
    const tmpPath = destPath + '.tmp'
    fs.mkdirSync(path.dirname(destPath), { recursive: true })
    fs.writeFileSync(tmpPath, content, 'utf-8')
    fs.renameSync(tmpPath, destPath)
    fs.rmSync(filePath, { force: true })
    return destPath
  })

  ipcMain.handle('fs:move', async (_event, srcPath: string, destPath: string): Promise<void> => {
    if (!isPathSafe(srcPath)) throw new Error('Source path outside home directory is not allowed')
    if (!isPathSafe(destPath)) throw new Error('Destination path outside home directory is not allowed')
    fs.mkdirSync(path.dirname(destPath), { recursive: true })
    fs.renameSync(srcPath, destPath)
  })

  ipcMain.handle('fs:userHome', async (): Promise<string> => {
    return path.join(app.getPath('home'), '.pathly')
  })

  ipcMain.handle('fs:appRoot', async (): Promise<string> => {
    return libraryRoot()
  })
}
