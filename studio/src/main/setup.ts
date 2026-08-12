import { app, ipcMain } from 'electron'
import { join } from 'path'
import { existsSync, writeFileSync, readdirSync } from 'fs'
import { spawn } from 'child_process'
import { getPythonPath } from './python'

function markerPath(): string {
  return join(app.getPath('userData'), `pathly-setup-${app.getVersion()}.done`)
}

function isSetupDone(): boolean {
  return existsSync(markerPath())
}

function getPreviousVersion(): string | null {
  const userData = app.getPath('userData')
  const current = app.getVersion()
  try {
    const prev = readdirSync(userData)
      .filter((f) => f.startsWith('pathly-setup-') && f.endsWith('.done'))
      .map((f) => f.slice('pathly-setup-'.length, -'.done'.length))
      .find((v) => v !== current)
    return prev ?? null
  } catch {
    return null
  }
}

export function registerSetupHandlers(): void {
  ipcMain.handle('setup:isNeeded', () => !isSetupDone())

  ipcMain.handle('setup:info', () => ({
    isNeeded: !isSetupDone(),
    isUpgrade: getPreviousVersion() !== null,
    fromVersion: getPreviousVersion(),
    toVersion: app.getVersion(),
  }))

  ipcMain.handle('setup:run', async (event) => {
    const send = (msg: string): void => { event.sender.send('setup:progress', msg) }
    try {
      await runSetup(send)
      return { ok: true }
    } catch (err) {
      return { ok: false, error: String(err) }
    }
  })
}

async function runSetup(onProgress: (msg: string) => void): Promise<void> {
  const python = getPythonPath()

  const wheelsDir = app.isPackaged
    ? join(process.resourcesPath, 'wheels')
    : join(__dirname, '../../resources/wheels')

  onProgress('Installing Python package…')
  await spawnLogged(python, [
    '-m', 'pip', 'install',
    '--no-index',
    '--find-links', wheelsDir,
    'pathly-adapters',
    '--quiet'
  ], onProgress)

  onProgress('Configuring Pathly for Claude Code…')
  await spawnLogged(python, ['-m', 'install_cli', '--apply'], onProgress)

  writeFileSync(markerPath(), app.getVersion())
  onProgress('Done.')
}

function spawnLogged(
  cmd: string,
  args: string[],
  onLine: (s: string) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, { stdio: 'pipe' })
    let lastLine = ''
    const emit = (d: Buffer): void => {
      d.toString().split('\n').filter(Boolean).forEach((line) => {
        lastLine = line
        onLine(line)
      })
    }
    proc.stdout?.on('data', emit)
    proc.stderr?.on('data', emit)
    proc.on('close', (code) =>
      code === 0 ? resolve() : reject(new Error(lastLine || `${cmd} exited ${code}`))
    )
    proc.on('error', reject)
  })
}
