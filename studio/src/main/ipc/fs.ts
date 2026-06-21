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
      const text = fs.readFileSync(filePath, 'utf-8')
      // Strip a leading UTF-8 BOM (U+FEFF). PowerShell 5.1's `Set-Content -Encoding UTF8` (which a
      // spawned agent may use to write a draft) prepends one; Node's utf-8 decode keeps it, which
      // would otherwise surface as an invisible char and a phantom "changed" first diff section.
      return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text
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

  // Copy a file (e.g. a dropped document) into a feature's artifacts/ dir. Source
  // must be readable (under home or the packaged library); destination must be in
  // home. Binary-safe — copyFileSync, not a utf-8 read/write.
  ipcMain.handle('fs:copy', async (_event, srcPath: string, destPath: string): Promise<void> => {
    if (!isReadablePathSafe(srcPath)) throw new Error('Source path outside allowed directories is not allowed')
    if (!isPathSafe(destPath)) throw new Error('Destination path outside home directory is not allowed')
    fs.mkdirSync(path.dirname(destPath), { recursive: true })
    fs.copyFileSync(srcPath, destPath)
  })

  ipcMain.handle('fs:userHome', async (): Promise<string> => {
    return path.join(app.getPath('home'), '.pathly')
  })

  ipcMain.handle('fs:appRoot', async (): Promise<string> => {
    return libraryRoot()
  })
}
