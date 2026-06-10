import { ipcMain, app, BrowserWindow } from 'electron'
import { spawn } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'
import { getPythonPath } from '../python'

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

// Check if a command is resolvable via Windows `where.exe` (handles .cmd, .exe, etc.)
function inPath(cmd: string): Promise<boolean> {
  return new Promise((resolve) => {
    const child = spawn('where', [cmd], { stdio: 'ignore' })
    child.once('close', (code) => resolve(code === 0))
    child.once('error', () => resolve(false))
  })
}

const LAUNCHERS: Record<string, (dir: string) => Promise<void>> = {
  vscode: async (dir) => {
    if (!await inPath('code')) throw new Error('VS Code not found — install it and ensure the `code` command is in your PATH')
    spawn('code', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
  },

  // explorer.exe is always present on Windows — fire and forget
  explorer: (dir) => {
    spawn('explorer', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
    return Promise.resolve()
  },

  // Windows Terminal with PowerShell fallback; both are always available
  terminal: (dir) => {
    const escaped = dir.replace(/'/g, "''")
    const child = spawn('wt', ['-d', dir], { detached: true, stdio: 'ignore', shell: true })
    child.on('error', () =>
      spawn(
        'powershell',
        ['-NoExit', '-Command', `Set-Location '${escaped}'`],
        { detached: true, stdio: 'ignore' }
      ).unref()
    )
    child.unref()
    return Promise.resolve()
  },

  gitbash: async (dir) => {
    const exe = findGitBash()
    if (exe) {
      spawn(exe, [`--cd=${dir}`], { detached: true, stdio: 'ignore' }).unref()
      return
    }
    if (!await inPath('sh')) throw new Error('Git Bash not found — install Git for Windows')
    spawn('sh', ['--login'], { cwd: dir, detached: true, stdio: 'ignore', shell: true }).unref()
  },

  wsl: async (dir) => {
    if (!await inPath('wsl')) throw new Error('WSL not found — enable Windows Subsystem for Linux in Windows Features')
    spawn('wsl', ['--cd', dir], { detached: true, stdio: 'ignore', shell: true }).unref()
  },

  pycharm: async (dir) => {
    if (await inPath('pycharm')) {
      spawn('pycharm', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
      return
    }
    if (await inPath('charm')) {
      spawn('charm', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
      return
    }
    throw new Error('PyCharm not found — install it via JetBrains Toolbox and enable the `pycharm` shell script')
  },
}

export function registerShellHandlers(win: BrowserWindow): void {
  ipcMain.handle('shell:openVsCode', async (_event, dir: string) => {
    if (!isValidProjectPath(dir)) throw new Error('Invalid project path')
    if (!await inPath('code')) throw new Error('VS Code not found — install it and ensure the `code` command is in your PATH')
    spawn('code', [dir], { detached: true, stdio: 'ignore', shell: true }).unref()
  })

  ipcMain.handle('shell:openInApp', async (_event, dir: string, appType: string) => {
    if (!isValidProjectPath(dir)) throw new Error('Invalid project path')
    const launcher = LAUNCHERS[appType]
    if (!launcher) throw new Error(`Unknown app type: ${appType}`)
    await launcher(dir)
  })

  ipcMain.handle('shell:publish', (_event, cwd: string) => {
    if (!isValidProjectPath(cwd)) throw new Error('Invalid project path')
    const proc = spawn('pip', ['install', '-e', '.'], { cwd, stdio: 'pipe' })
    proc.stdout?.on('data', (d: Buffer) => win.webContents.send('shell:output', d.toString()))
    proc.stderr?.on('data', (d: Buffer) => win.webContents.send('shell:output', d.toString()))
    return new Promise((resolve) => proc.on('close', resolve))
  })

  ipcMain.handle('shell:upgrade', (_event) => {
    const python = getPythonPath()
    const send = (d: Buffer): void => win.webContents.send('shell:output', d.toString())

    return new Promise<number | null>((resolve) => {
      const pip = spawn(python, ['-m', 'pip', 'install', '--upgrade', 'pathly-adapters'], { stdio: 'pipe' })
      pip.stdout?.on('data', send)
      pip.stderr?.on('data', send)
      pip.on('close', (code) => {
        if (code !== 0) { resolve(code); return }
        win.webContents.send('shell:output', '\nDeploying agents, skills and templates to adapters…\n')
        const deploy = spawn(python, ['-m', 'install_cli', '--apply', '--repair'], { stdio: 'pipe' })
        deploy.stdout?.on('data', send)
        deploy.stderr?.on('data', send)
        deploy.on('close', resolve)
      })
    })
  })
}
