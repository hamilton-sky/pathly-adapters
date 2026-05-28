import { ipcMain, app, BrowserWindow } from 'electron'
import { spawn } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'

function isValidProjectPath(dir: string): boolean {
  try {
    const real = fs.realpathSync(dir)
    const home = path.resolve(app.getPath('home'))
    return real.startsWith(home + path.sep) || real === home
  } catch {
    return false
  }
}

function findGitBash(): string | null {
  const roots = [
    process.env.PROGRAMFILES,
    process.env['PROGRAMFILES(X86)'],
    'C:\\Program Files',
    'C:\\Program Files (x86)',
  ]
  for (const root of roots) {
    if (!root) continue
    const candidate = path.join(root, 'Git', 'git-bash.exe')
    try { fs.accessSync(candidate); return candidate } catch { /* not here */ }
  }
  return null
}

const LAUNCHERS: Record<string, (dir: string) => void> = {
  vscode: (dir) => spawn('code', [dir], { detached: true, stdio: 'ignore', shell: true }).unref(),
  explorer: (dir) => spawn('explorer', [dir], { detached: true, stdio: 'ignore', shell: true }).unref(),
  terminal: (dir) => {
    // Windows Terminal; fall back to PowerShell if not installed
    const child = spawn('wt', ['-d', dir], { detached: true, stdio: 'ignore', shell: true })
    child.on('error', () =>
      spawn('powershell', ['-NoExit', '-Command', `Set-Location '${dir}'`], { detached: true, stdio: 'ignore' }).unref()
    )
    child.unref()
  },
  gitbash: (dir) => {
    const exe = findGitBash()
    if (exe) {
      spawn(exe, [`--cd=${dir}`], { detached: true, stdio: 'ignore' }).unref()
    } else {
      // Fallback: open bash via Git's sh.exe if on PATH
      spawn('sh', ['--login'], { cwd: dir, detached: true, stdio: 'ignore', shell: true }).unref()
    }
  },
  wsl: (dir) => spawn('wsl', ['--cd', dir], { detached: true, stdio: 'ignore', shell: true }).unref(),
  pycharm: (dir) => {
    // JetBrains Toolbox puts 'pycharm' in PATH; older installs use 'charm'
    const child = spawn('pycharm', [dir], { detached: true, stdio: 'ignore', shell: true })
    child.on('error', () =>
      spawn('charm', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
    )
    child.unref()
  },
}

export function registerShellHandlers(win: BrowserWindow): void {
  ipcMain.handle('shell:openVsCode', async (_event, dir: string) => {
    if (!isValidProjectPath(dir)) throw new Error('Invalid project path')
    spawn('code', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
  })

  ipcMain.handle('shell:openInApp', async (_event, dir: string, appType: string) => {
    if (!isValidProjectPath(dir)) throw new Error('Invalid project path')
    const launcher = LAUNCHERS[appType]
    if (!launcher) throw new Error(`Unknown app type: ${appType}`)
    launcher(dir)
  })

  ipcMain.handle('shell:publish', (_event, cwd: string) => {
    if (!isValidProjectPath(cwd)) {
      throw new Error('Invalid project path')
    }
    const proc = spawn('pip', ['install', '-e', '.'], { cwd, stdio: 'pipe' })
    proc.stdout?.on('data', (d: Buffer) => win.webContents.send('shell:output', d.toString()))
    proc.stderr?.on('data', (d: Buffer) => win.webContents.send('shell:output', d.toString()))
    return new Promise((resolve) => proc.on('close', resolve))
  })
}
