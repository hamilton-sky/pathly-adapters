import { app } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'

function bundledPythonRelPath(): string {
  return process.platform === 'win32' ? 'python.exe' : 'bin/python3'
}

export function getBundledPythonPath(): string | null {
  if (!app.isPackaged) return null
  const p = join(process.resourcesPath, 'python', bundledPythonRelPath())
  return existsSync(p) ? p : null
}

export function getPythonPath(): string {
  return getBundledPythonPath() ?? (process.platform === 'win32' ? 'python' : 'python3')
}
